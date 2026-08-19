# Research examples (PR #20)

Runnable companions to [deep_agent_mcp_analysis.md](../deep_agent_mcp_analysis.md).
**Langfuse / Helm is not required** to review the MCP agent-first change.

| App | Folder | What it shows |
| --- | ------ | ------------- |
| **MCP Agents (this is the protocol change)** | [`sdlc-mcp/`](./sdlc-mcp) | `agents/list` → `agents/get` → `tools/call` on a plain `MCPServer` |
| **Deep Agents (methodology reference)** | [`deepagent-poc/`](./deepagent-poc) | In-process roster + `task()` — optional; not on the MCP wire |

Same SDLC scenario: `payments-service` v2.4.

---

## PR path — MCP server only (no observability)

Needs: Python 3.11+, the experimental SDK in this workspace (`mcp-agents-poc/python-sdk`).
No Groq key for `--discover-only`.

```text
mcp-agents-poc/
├── python-sdk/
└── agents-wg/docs/research/examples/sdlc-mcp/
```

```bash
cd docs/research/examples/sdlc-mcp
python3 -m venv .venv
source .venv/bin/activate

pip install -e ../../../../../python-sdk[cli]
pip install -e ../../../../../python-sdk/src/mcp-types
pip install -r requirements.txt
```

### See the wire (no LLM)

```bash
python -m client.main --discover-only
```

Expected:

```text
mcp:initialize → sdlc-release-readiness …
mcp:agents/list → 3 agents (roster only)
  - workflow-agent: …
  - research-agent: …
  - insights-agent: …
mcp:agents/get workflow-agent → N tools
mcp:agents/get research-agent → N tools
mcp:agents/get insights-agent → N tools
```

Server advertises `experimental.agents`. Roster has **labels only**; tool schemas appear
only after `agents/get`. TTL is on the **result** (`ttlMs`), not per tool.

### Optional: LLM turn (same server)

```bash
cp .env.example .env   # set GROQ_API_KEY
python -m client.main --default
```

Flat comparison (no agents — all schemas on `tools/list`):

```bash
python -m client.main --flat --discover-only
python -m client.main --flat --default
```

Server alone / Inspector:

```bash
python -m server.main
npx @modelcontextprotocol/inspector python -m server.main
```

---

## Optional — Deep Agents comparison

```bash
cd docs/research/examples/deepagent-poc
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # GROQ_API_KEY
python -m src.main --default
```

That example may still mention Langfuse in its own README; **do not install it for PR #20**.
Leave `LANGFUSE_ENABLED=false` (or unset).

---

## Optional — Langfuse traces (not part of the PR)

Only if you already run Langfuse and want spans. Helm install:
[Langfuse Kubernetes (Helm)](https://langfuse.com/self-hosting/deployment/kubernetes-helm).

```bash
helm repo add langfuse https://langfuse.github.io/langfuse-k8s
helm repo update
kubectl create namespace langfuse
helm install langfuse langfuse/langfuse -n langfuse
kubectl port-forward svc/langfuse-web -n langfuse 3000:3000
```

The **MCP example in this folder does not send traces** — it is a plain `MCPServer`.
The workspace copy of `sdlc-mcp` (outside this repo) is the Langfuse-instrumented demo.
