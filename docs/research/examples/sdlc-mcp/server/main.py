"""SDLC MCP server — agent-first discovery + tools/call.

Wire (when the formal agent discovery extension is negotiated):
  Client ──server/discover──► Server  (io.modelcontextprotocol/agents)
  Client ──agents/list──► Server  (roster cards only)
  Client ──agents/get──► Server   (scoped tool schemas)
  Client ──tools/call──► Server   (unchanged)

Run (stdio):
  cd sdlc-mcp && source .venv/bin/activate
  python -m server.main
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `python -m server.main` from sdlc-mcp/
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from server import backend
from mcp.server.mcpserver import MCPServer

mcp = MCPServer(
    "sdlc-release-readiness",
    instructions=(
        "SDLC release-readiness server. Prefer agents/list → agents/get → tools/call."
    ),
    # Agent discovery TTL (independent of tools/list). 0 = do not cache.
    agents_ttl_ms=60_000,
)


# ---------------------------------------------------------------------------
# Workflow tools (deepagent workflow-agent)
# ---------------------------------------------------------------------------


@mcp.tool()
def list_failed_pipelines(service: str = "payments-service", limit: int = 5) -> str:
    """List recent failed CI/CD pipeline runs for a service."""
    return backend.list_failed_pipelines(service=service, limit=limit)


@mcp.tool()
def list_pending_approvals(service: str = "payments-service") -> str:
    """List pipeline approval gates still waiting."""
    return backend.list_pending_approvals(service=service)


@mcp.tool()
def get_pipeline_run(run_id: int) -> str:
    """Get details for a specific pipeline run id."""
    return backend.get_pipeline_run(run_id=run_id)


@mcp.tool()
def list_open_change_requests(service: str = "payments-service") -> str:
    """List open change requests / CAB tickets for a service."""
    return backend.list_open_change_requests(service=service)


@mcp.tool()
def list_deployments(service: str = "payments-service") -> str:
    """List recent deployments across environments."""
    return backend.list_deployments(service=service)


@mcp.tool()
def get_service_owners(service: str = "payments-service") -> str:
    """Return owning team, on-call, and repo for a service."""
    return backend.get_service_owners(service=service)


@mcp.tool()
def list_open_incidents(service: str = "payments-service") -> str:
    """List open incidents related to a service."""
    return backend.list_open_incidents(service=service)


@mcp.tool()
def list_feature_flags(service: str = "payments-service") -> str:
    """List feature flags relevant to the upcoming release."""
    return backend.list_feature_flags(service=service)


@mcp.tool()
def list_test_flakes(service: str = "payments-service") -> str:
    """List flaky tests that may block the release pipeline."""
    return backend.list_test_flakes(service=service)


@mcp.tool()
def get_task_config(task_name: str) -> str:
    """Return configuration for an automation / release task by name."""
    return backend.get_task_config(task_name=task_name)


# ---------------------------------------------------------------------------
# Research tools (deepagent research-agent)
# ---------------------------------------------------------------------------


@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for outages, CVEs, or release-risk context (Exa if EXA_API_KEY set)."""
    return backend.web_search(query=query, max_results=max_results)


@mcp.tool()
def fetch_url_summary(url: str) -> str:
    """Summarize a URL for release risk context."""
    return backend.fetch_url_summary(url=url)


@mcp.tool()
def search_internal_docs(query: str) -> str:
    """Search internal SDLC / runbook docs (fixture)."""
    return backend.search_internal_docs(query=query)


# ---------------------------------------------------------------------------
# Insights tools (deepagent insights-agent)
# ---------------------------------------------------------------------------


@mcp.tool()
def get_dora_metrics(service: str = "payments-service") -> str:
    """Fetch DORA metrics for a service over the last 30 days."""
    return backend.get_dora_metrics(service=service)


@mcp.tool()
def get_error_budget(service: str = "payments-service") -> str:
    """Fetch error budget / SLO remaining for a service."""
    return backend.get_error_budget(service=service)


@mcp.tool()
def get_slo_burn(service: str = "payments-service") -> str:
    """Fetch recent SLO burn series (errors vs deploys) for charting."""
    return backend.get_slo_burn(service=service)


@mcp.tool()
def build_insight_chart(
    service: str = "payments-service",
    title: str = "Release risk — errors vs deploys",
) -> str:
    """Build a release-risk chart PNG; returns path + ASCII summary."""
    return backend.build_insight_chart(service=service, title=title)


@mcp.tool()
def compute_release_risk_score(service: str = "payments-service") -> str:
    """Compute a simple 0-100 release risk score (higher = riskier)."""
    return backend.compute_release_risk_score(service=service)


# ---------------------------------------------------------------------------
# Agents — bind tools by name (Proposal 1). Registered only when this module
# is the stdio entrypoint (see register_agents / __main__).
# ---------------------------------------------------------------------------

WORKFLOW_TOOLS = [
    "list_failed_pipelines",
    "list_pending_approvals",
    "get_pipeline_run",
    "list_open_change_requests",
    "list_deployments",
    "get_service_owners",
    "list_open_incidents",
    "list_feature_flags",
    "list_test_flakes",
    "get_task_config",
]
RESEARCH_TOOLS = ["web_search", "fetch_url_summary", "search_internal_docs"]
INSIGHTS_TOOLS = [
    "get_dora_metrics",
    "get_error_budget",
    "get_slo_burn",
    "build_insight_chart",
    "compute_release_risk_score",
]

def register_agents() -> None:
    """Advertise the agent extension. Skip this for the flat tools/list demo."""
    mcp.add_agent(
        name="workflow-agent",
        description="Pipelines, approvals, deployments, incidents",
        capabilities=["failed pipelines", "pending approvals", "change requests"],
        tools=WORKFLOW_TOOLS,
        instructions="You handle CI/CD and approvals for the named service.",
    )
    mcp.add_agent(
        name="research-agent",
        description="Outages, CVEs, internal runbooks",
        capabilities=["web search", "internal docs", "CVEs"],
        tools=RESEARCH_TOOLS,
        instructions="You research outages, CVEs, and internal docs.",
    )
    mcp.add_agent(
        name="insights-agent",
        description="DORA, error budget, release risk",
        capabilities=["dora", "risk score", "charts"],
        tools=INSIGHTS_TOOLS,
        instructions="You compute release-risk insights and charts.",
    )


if __name__ == "__main__":
    register_agents()
    mcp.run()
