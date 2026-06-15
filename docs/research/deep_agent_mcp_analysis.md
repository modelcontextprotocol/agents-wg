# Mapping Deep Agent Architecture to MCP Agents

> Observations on production deep-agent systems and how they map onto MCP primitives, and where are the protocol gaps?

---

## MCP stack (Current Model)

```text
MCP Core                    Extensions (experimental / discussion)
├── Tools                   ├── Tasks (ext-tasks)
├── Resources               ├── Events (future)
├── Prompts                 ├── Skills (discussion)
├── Sampling                ├── .
└── Transports              └── …

```

---

## Deep-agent pattern (Production System)

```text
User
 ↓
Supervisor          ← small surface: delegation + generic tools
 ↓ task(agent, …)
Sub-agent             ← domain tools visible for subagent only
 ↓
Tools (native + optional MCP)
```

**Delegation boundary:**

```text
Supervisor
  ├── analytics-agent
  ├── docs-agent
  └── security-agent

analytics-agent
  ├── run_sql
  ├── get_metrics
  └── dashboards

docs-agent
  ├── search_docs
  └── summarize
```

The delegation bounds **reasoning cost** and reduces wrong tool selection. Sub-agent tools are registered on the sub-agent config only—not on the supervisor.

---

## MCP primitive coverage

| Production need | What it does| Deep Agent Stack | MCP Today |
|-----------------|-------------|-----------|--------|
| Tool call | Stateless request/response| Sub-agents invoke tools | ✅ Covered |
| Long-running work | `task_id` + poll + progress |Supervisor tracks jobs| ✅🧪 **Tasks** ([ext-tasks](https://github.com/modelcontextprotocol/ext-tasks)) |
| **Agent/Sub-Agent definition/ Registration / Delegation** | Production systems reason at the agent level, not the tool level. LLM mis-picks tools lead to latency and cost rise and wrong-domain answers.| Supervisor LLM has the context, Sub agent capabilities ONLY and system prompt to pick proper subagent quickly | ❌ No standard `analytics-agent` object—only. `run_sql`, `get_metrics`Protocol exposes all discovered tools, Client must decide `Tool Sprawl` |
| **Thread / conversation memory / Context injection per turn** | checkpoint persists `messages` per thread ID (Mongo or equivalent). | Supervisor agent Middleware consumes Client(UX) context, constructs system prompts for agent to call consecutive tools | Partially Covered by reasources/prompts to fetch profile/little context, But Client-dependent.Tasks hold **job** state ≠ agent context, **Need agent STATE/ external MEMORY** capability| 
| Parallel sub-agents / Multi consecutive tool calls | Thread would required multiple subagent outputs | Agent can store ouptuts in state and call respective sub-agent / tool | ❌ Needs Task DAG / Agent DAG
| **LLM routing / model hints** | Production systems would require fast model/reasoning model/structured-output model | middleware selects model object per call (context-size tiers; optional text classifier)—**no overseer LLM** | ❌  user can choose in client , Need model_hints |


---

## Proposed layering (direction for WG)

```text
Agent          ← definition + capability card (gap)
 ↓
Task           ← long-running unit of work (experimental)
 ↓
Sub-agent      ← executor with bounded tools/ toolsets (gap)
 ↓
Tool           ← MCP core ✅
```


Notes:

This document represents ongoing exploration on  how much of  orchestration should become standardized as part of MCP Agents. 
I am actively evaluating current MCP capabilities, Tasks, MCP Apps, and Agents WG proposals through prototypes and production-inspired experiments. Feedback, corrections, and alternative approaches are welcome.

---


## References

- [MCP Agents WG](https://github.com/modelcontextprotocol/agents-wg) · [Meetings](https://github.com/modelcontextprotocol/agents-wg/tree/main/meetings)
- [LangChain Deep Agents](https://docs.langchain.com/oss/python/deepagents/harness)
- [ext-tasks (experimental)](https://github.com/modelcontextprotocol/ext-tasks) — `io.modelcontextprotocol/tasks`
- [2026-04-21 — agents vs tasks, sub-agent communication](https://github.com/modelcontextprotocol/agents-wg/blob/main/meetings/2026-04-21.md)
- [2026-01-13 — sessions, discovery](https://github.com/modelcontextprotocol/agents-wg/blob/main/meetings/2026-01-13.md)
- [2026-05-29 — tasks conformance, extension versioning](https://github.com/modelcontextprotocol/agents-wg/blob/main/meetings/2026-05-29.md)
