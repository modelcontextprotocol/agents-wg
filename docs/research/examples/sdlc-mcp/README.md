# SDLC MCP — agent-first discovery

Same release-readiness tools as [`../deepagent-poc`](../deepagent-poc). Default
server path is **agent-first** (`agents/list` → `agents/get` → `tools/call`).
`server.main_flat` is the comparison: all schemas on `tools/list`.

**No Langfuse.** Runbook: [../README.md](../README.md).

```text
deepagent-poc                          sdlc-mcp (this project)
─────────────                          ───────────────────────
Supervisor sees agent roster           Host sees 3 agent cards
task(workflow|research|insights)       agents/get then tools/call
Specialist picks tools                 Specialist LLM sees scoped schemas
```

## Wire

```text
Client                         Server (MCPServer + AgentManager)
──────                         ────────────────────────────────
server/discover ─────────────► io.modelcontextprotocol/agents
agents/list ─────────────────► roster cards only (+ ttlMs)
agents/get  ─────────────────► scoped Tool[] (+ ttlMs)
tools/call  ─────────────────► ToolManager handler → backend
```

## Setup

```bash
cd docs/research/examples/sdlc-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e ../../../../../python-sdk[cli]
pip install -e ../../../../../python-sdk/src/mcp-types
pip install -r requirements.txt
```

## Run

```bash
# Protocol only — no LLM / no Groq
python -m client.main --discover-only

# LLM turn (optional)
cp .env.example .env   # GROQ_API_KEY
python -m client.main --default

# Flat tools/list comparison
python -m client.main --flat --discover-only
```

Server / Inspector:

```bash
python -m server.main
npx @modelcontextprotocol/inspector python -m server.main
```

## Tool inventory (bound to agents in `server.main`)

| Agent | Tools |
|-------|--------|
| workflow-agent | `list_failed_pipelines`, `list_pending_approvals`, `get_pipeline_run`, `list_open_change_requests`, `list_deployments`, `get_service_owners`, `list_open_incidents`, `list_feature_flags`, `list_test_flakes`, `get_task_config` |
| research-agent | `web_search`, `fetch_url_summary`, `search_internal_docs` |
| insights-agent | `get_dora_metrics`, `get_error_budget`, `get_slo_burn`, `build_insight_chart`, `compute_release_risk_score` |

## Layout

```text
sdlc-mcp/
├── requirements.txt      # no langfuse
├── server/main.py        # MCPServer + register_agents()
├── server/main_flat.py   # same tools, no agents
├── server/backend.py
└── client/main.py        # discovery + optional LLM
```
