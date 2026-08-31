"""MCP client — agent-first discovery (no Langfuse).

  python -m client.main --discover-only   # wire only: initialize → list → get
  python -m client.main --default         # LLM + tools (needs GROQ_API_KEY)
  python -m client.main --flat --default  # old path: tools/list
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp_types.extensions.agents import AGENTS_EXTENSION_IDENTIFIER

_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_ROOT / ".env")

if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

DEFAULT_QUESTION = (
    "We're shipping payments-service v2.4 tomorrow. Check failed pipelines and "
    "pending approvals, search for payment-API outages or CVEs, then give a "
    "release-risk insight with a chart."
)

_SYSTEM = """You answer SDLC release-readiness questions using MCP tools.

Rules for tool calling (required for Groq):
1. Call exactly ONE tool per assistant turn.
2. Wait for that tool's result before calling another tool.
3. Never emit multiple tools in one response.
4. Use native tool calling only — never invent XML like <function=...>.
5. Be concise and factual after you have enough tool results.
"""


def _build_llm():
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        from langchain_groq import ChatGroq

        model = os.getenv("MODEL", "llama-3.3-70b-versatile").strip()
        for prefix in ("openai:", "groq:", "langchain_groq:"):
            if model.startswith(prefix):
                model = model[len(prefix) :]
                break
        return ChatGroq(
            api_key=groq_key,
            model=model,
            temperature=0,
            model_kwargs={"parallel_tool_calls": False},
        )

    from langchain.chat_models import init_chat_model

    return init_chat_model(os.getenv("MODEL", "openai:gpt-4o-mini"), temperature=0)


def _tools_from_mcp(session: ClientSession, listed) -> list:
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field, create_model

    tools = []
    for t in listed.tools:
        schema = (
            getattr(t, "inputSchema", None)
            or getattr(t, "input_schema", None)
            or {"type": "object", "properties": {}}
        )
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])

        fields: dict[str, Any] = {}
        for key, prop in props.items():
            typ: type = str
            ptype = (prop or {}).get("type")
            if ptype == "integer":
                typ = int
            elif ptype == "number":
                typ = float
            elif ptype == "boolean":
                typ = bool
            default = ... if key in required else (prop or {}).get("default", None)
            desc = (prop or {}).get("description", "")
            if default is ...:
                fields[key] = (typ, Field(description=desc))
            else:
                fields[key] = (typ | None, Field(default=default, description=desc))

        ArgModel = (
            create_model(f"{t.name}_Args", **fields)
            if fields
            else create_model(f"{t.name}_Args")
        )

        def _bind(tool_name: str, description: str, arg_model: type[BaseModel]):
            async def _call(**kwargs: Any) -> str:
                args = {k: v for k, v in kwargs.items() if v is not None}
                result = await session.call_tool(tool_name, args)
                parts = []
                for block in result.content or []:
                    parts.append(getattr(block, "text", None) or str(block))
                return "\n".join(parts)

            return StructuredTool.from_function(
                coroutine=_call,
                name=tool_name,
                description=description or tool_name,
                args_schema=arg_model,
            )

        tools.append(_bind(t.name, t.description or t.name, ArgModel))
    return tools


def _is_groq_tool_fail(exc: BaseException) -> bool:
    text = str(exc).lower()
    return "tool_use_failed" in text or "failed to call a function" in text


class _ToolListing:
    def __init__(self, tools):
        self.tools = tools


async def _select_agents(question: str, roster, *, model) -> list[str]:
    cards = "\n".join(
        f"- {a.name}: {a.description} | capabilities={list(a.capabilities or [])}"
        for a in roster.agents
    )
    prompt = (
        "You are a supervisor. Pick which specialist agent(s) should handle the user question.\n"
        "Reply with a comma-separated list of agent names only (no other text).\n\n"
        f"Agents:\n{cards}\n\n"
        f"User question: {question}"
    )
    from langchain_core.messages import HumanMessage

    resp = await model.ainvoke([HumanMessage(content=prompt)])
    text = str(getattr(resp, "content", None) or resp).strip()
    known = {a.name for a in roster.agents}
    picked = []
    for token in text.replace("\n", ",").split(","):
        name = token.strip().strip("`").strip()
        if name in known and name not in picked:
            picked.append(name)
    if not picked:
        q = question.lower()
        if "cve" in q or "outage" in q or "search" in q:
            picked.append("research-agent")
        if "dora" in q or "risk" in q or "chart" in q or "insight" in q:
            picked.append("insights-agent")
        if "pipeline" in q or "approval" in q or "deploy" in q or not picked:
            picked.insert(0, "workflow-agent")
    return picked


async def discover(session: ClientSession) -> dict[str, Any]:
    init = await session.discover()
    server_info = session.server_info
    name = getattr(server_info, "name", None) if server_info else None
    print(
        f"mcp:server/discover → {name or 'server'} protocol={session.protocol_version}"
    )

    caps = getattr(init, "capabilities", None)
    extensions = getattr(caps, "extensions", None) or {}
    if AGENTS_EXTENSION_IDENTIFIER in extensions:
        roster = await session.list_agents()
        print(f"mcp:agents/list → {len(roster.agents)} agents (roster only)")
        for a in roster.agents:
            print(f"  - {a.name}: {a.description}")
        return {"init": init, "agents": roster, "mode": "agent-first"}

    listed = await session.list_tools()
    print(f"mcp:tools/list → {len(listed.tools)} tools")
    return {"init": init, "tools": listed, "mode": "flat-tools"}


async def ask(question: str, *, session: ClientSession, discovery: dict) -> str:
    model = _build_llm()
    mode = discovery.get("mode") or "flat-tools"

    if mode == "agent-first":
        roster = discovery["agents"]
        selected = await _select_agents(question, roster, model=model)
        print(f"supervisor selected agents: {selected}")

        scoped_tools = []
        instructions_bits = []
        for name in selected:
            detail = await session.get_agent(name)
            print(
                f"mcp:agents/get {name} → {len(detail.tools)} tools "
                f"({', '.join(t.name for t in detail.tools)})"
            )
            scoped_tools.extend(detail.tools)
            if detail.instructions:
                instructions_bits.append(f"[{name}] {detail.instructions}")

        seen: set[str] = set()
        unique = []
        for t in scoped_tools:
            if t.name in seen:
                continue
            seen.add(t.name)
            unique.append(t)

        listed = _ToolListing(unique)
        system = _SYSTEM
        if instructions_bits:
            system = _SYSTEM + "\n\nSpecialist notes:\n" + "\n".join(instructions_bits)
    else:
        listed = discovery["tools"]
        system = _SYSTEM

    lc_tools = _tools_from_mcp(session, listed)
    print(f"tool schemas loaded into LLM: {len(lc_tools)} (mode={mode})")

    from langchain.agents import create_agent

    agent = create_agent(model=model, tools=lc_tools, system_prompt=system)

    async def _invoke(q: str) -> str:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": q}]})
        messages = result.get("messages") or []
        last = messages[-1] if messages else None
        return str(getattr(last, "content", None) or last)

    try:
        return await _invoke(question)
    except Exception as exc:
        if not _is_groq_tool_fail(exc):
            raise
        print("[warn] Groq tool_use_failed — retrying one-tool-at-a-time")
        nudge = (
            question
            + "\n\nIMPORTANT: Call only ONE tool in your next response "
            "(start with list_failed_pipelines), then stop and wait."
        )
        return await _invoke(nudge)


def _server_params(server_module: str) -> StdioServerParameters:
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", server_module],
        cwd=str(_ROOT),
        env=os.environ.copy(),
    )


async def run_discover_only(*, server_module: str) -> None:
    async with stdio_client(_server_params(server_module)) as (read, write):
        async with ClientSession(
            read,
            write,
            extensions={AGENTS_EXTENSION_IDENTIFIER: {}},
        ) as session:
            discovery = await discover(session)
            if discovery.get("mode") != "agent-first":
                return
            for a in discovery["agents"].agents:
                detail = await session.get_agent(a.name)
                ttl = getattr(detail, "ttl_ms", None) or getattr(detail, "ttlMs", None)
                print(
                    f"mcp:agents/get {a.name} → {len(detail.tools)} tools"
                    + (f" ttlMs={ttl}" if ttl is not None else "")
                )


async def run_session(question: str, *, server_module: str) -> str:
    async with stdio_client(_server_params(server_module)) as (read, write):
        async with ClientSession(
            read,
            write,
            extensions={AGENTS_EXTENSION_IDENTIFIER: {}},
        ) as session:
            discovery = await discover(session)
            return await ask(question, session=session, discovery=discovery)


async def interactive(*, server_module: str) -> None:
    flat = server_module.endswith("main_flat")
    print("MCP client — agent-first discovery (no observability required).")
    print(f"Mode: {'FLAT tools/list' if flat else 'AGENT-FIRST agents/list'}\n")

    async with stdio_client(_server_params(server_module)) as (read, write):
        async with ClientSession(
            read,
            write,
            extensions={AGENTS_EXTENSION_IDENTIFIER: {}},
        ) as session:
            discovery = await discover(session)
            print("Ready. Type a question, or q to quit.\n")
            while True:
                try:
                    user = input("You> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if not user or user.lower() in {"exit", "quit", "q"}:
                    break
                try:
                    answer = await ask(user, session=session, discovery=discovery)
                    print(f"\nAssistant:\n{answer}\n")
                except Exception as exc:  # noqa: BLE001
                    print(f"\n[error] {exc}\n")


async def main() -> None:
    args = [a for a in sys.argv[1:] if a]
    flat = "--flat" in args
    discover_only = "--discover-only" in args
    args = [a for a in args if a not in {"--flat", "--discover-only", "--"}]
    server_module = "server.main_flat" if flat else "server.main"

    if discover_only:
        await run_discover_only(server_module=server_module)
        return

    argv_q = " ".join(args).strip()
    if argv_q in {"--default", "-d"}:
        argv_q = DEFAULT_QUESTION
    elif not argv_q:
        await interactive(server_module=server_module)
        return

    print(f"\nQuestion:\n{argv_q}\n")
    print(f"Mode: {'FLAT tools/list' if flat else 'AGENT-FIRST agents/list'}\n")
    answer = await run_session(argv_q, server_module=server_module)
    print(f"\nAnswer:\n{answer}\n")


if __name__ == "__main__":
    asyncio.run(main())
