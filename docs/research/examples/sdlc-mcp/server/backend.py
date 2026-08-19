"""Backend helpers — what tools call when a client does tools/call.

Today these read fixtures (and optional live Exa/Tavily). In production each
function would be an HTTP call to CI, ITSM, observability, etc.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from server.fixtures import load_sdlc

_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "outputs"


def _j(data: Any) -> str:
    return json.dumps(data, indent=2)


# --- Workflow ---


def list_failed_pipelines(service: str = "payments-service", limit: int = 5) -> str:
    rows = load_sdlc()["failed_pipelines"]
    key = service.lower().replace("-service", "").replace("_", "-")
    filtered = [r for r in rows if key in r["name"].lower()]
    rows = filtered or rows
    return _j({"service": service, "failed": rows[: max(1, limit)]})


def list_pending_approvals(service: str = "payments-service") -> str:
    rows = load_sdlc()["pending_approvals"]
    key = service.lower().replace("-service", "").replace("_", "-")
    filtered = [r for r in rows if key in r["pipeline"].lower()]
    rows = filtered or rows
    return _j({"pending_approvals": rows})


def get_pipeline_run(run_id: int) -> str:
    runs = load_sdlc()["pipeline_runs"]
    row = runs.get(str(run_id))
    if not row:
        return _j({"error": f"run_id {run_id} not found", "known_ids": list(runs)})
    return _j(row)


def list_open_change_requests(service: str = "payments-service") -> str:
    rows = [r for r in load_sdlc()["change_requests"] if r["service"] == service]
    return _j({"change_requests": rows})


def list_deployments(service: str = "payments-service") -> str:
    _ = service
    return _j({"deployments": load_sdlc()["deployments"]})


def get_service_owners(service: str = "payments-service") -> str:
    owners = load_sdlc()["service_owners"]
    row = owners.get(service)
    if not row:
        return _j({"error": f"unknown service {service}", "known": list(owners)})
    return _j({"service": service, **row})


def list_open_incidents(service: str = "payments-service") -> str:
    rows = [i for i in load_sdlc()["incidents"] if i["service"] == service]
    return _j({"incidents": rows})


def list_feature_flags(service: str = "payments-service") -> str:
    _ = service
    return _j({"feature_flags": load_sdlc()["feature_flags"]})


def list_test_flakes(service: str = "payments-service") -> str:
    _ = service
    return _j({"test_flakes": load_sdlc()["test_flakes"]})


def get_task_config(task_name: str) -> str:
    return _j(
        {
            "task": task_name,
            "type": "automation",
            "schedule": "0 2 * * *",
            "connector": "git-custodian",
            "status": "enabled",
            "service": "payments-service",
        }
    )


# --- Research ---


def _search_tavily(query: str, max_results: int) -> list[dict] | None:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import urllib.request

        body = json.dumps(
            {"api_key": api_key, "query": query, "max_results": max_results}
        ).encode()
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode())
        return [
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": r.get("content") or r.get("snippet"),
            }
            for r in payload.get("results", [])[:max_results]
        ]
    except Exception as exc:  # noqa: BLE001
        return [{"title": "tavily_error", "url": "", "snippet": str(exc)}]


def _search_exa(query: str, max_results: int) -> list[dict] | None:
    api_key = os.getenv("EXA_API_KEY", "").strip()
    if not api_key:
        return None
    try:
        import urllib.request

        body = json.dumps(
            {"query": query, "numResults": max_results, "type": "auto"}
        ).encode()
        req = urllib.request.Request(
            "https://api.exa.ai/search",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode())
        return [
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": r.get("text") or r.get("summary") or "",
            }
            for r in payload.get("results", [])[:max_results]
        ]
    except Exception as exc:  # noqa: BLE001
        return [{"title": "exa_error", "url": "", "snippet": str(exc)}]


def web_search(query: str, max_results: int = 5) -> str:
    results = _search_exa(query, max_results) or _search_tavily(query, max_results)
    source = "live"
    if results is None:
        results = load_sdlc()["web_search_fallback"][: max(1, max_results)]
        source = "fixture"
    return _j({"query": query, "source": source, "results": results})


def fetch_url_summary(url: str) -> str:
    fallback = load_sdlc()["web_search_fallback"]
    for row in fallback:
        if row["url"] == url or url in row["url"]:
            return _j({"url": url, "summary": row["snippet"], "source": "fixture"})
    try:
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": "sdlc-mcp/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            raw = resp.read(4000).decode("utf-8", errors="ignore")
        text = " ".join(raw.split())[:800]
        return _j({"url": url, "summary": text or "(empty body)", "source": "live"})
    except Exception as exc:  # noqa: BLE001
        return _j(
            {
                "url": url,
                "summary": f"Could not fetch ({exc}). Use web_search results instead.",
                "source": "error",
            }
        )


def search_internal_docs(query: str) -> str:
    hits = [
        {
            "path": "/docs/runbooks/payments-release.md",
            "snippet": "Block prod if staging smoke fails or CAB gate overdue.",
        },
        {
            "path": "/docs/slo/payments-checkout.md",
            "snippet": "Error budget burn >1.5x over 1h requires incident review before release.",
        },
    ]
    return _j({"query": query, "hits": hits})


# --- Insights ---


def get_dora_metrics(service: str = "payments-service") -> str:
    row = load_sdlc()["dora_metrics"].get(service)
    if not row:
        return _j({"error": f"no DORA metrics for {service}"})
    return _j({"service": service, **row})


def get_error_budget(service: str = "payments-service") -> str:
    row = load_sdlc()["error_budget"].get(service)
    if not row:
        return _j({"error": f"no error budget for {service}"})
    return _j({"service": service, **row})


def get_slo_burn(service: str = "payments-service") -> str:
    row = load_sdlc()["slo_burn"].get(service)
    if not row:
        return _j({"error": f"no SLO burn for {service}"})
    return _j({"service": service, **row})


def build_insight_chart(
    service: str = "payments-service",
    title: str = "Release risk — errors vs deploys",
) -> str:
    row = load_sdlc()["slo_burn"].get(service)
    if not row:
        return _j({"error": f"no series for {service}"})

    series = row["series"]
    days = [p["day"] for p in series]
    errors = [p["errors"] for p in series]
    deploys = [p["deploys"] for p in series]

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _OUTPUT_DIR / f"{service.replace('/', '_')}_release_risk.png"

    try:
        os.environ.setdefault("MPLCONFIGDIR", str(_OUTPUT_DIR / ".mplconfig"))
        Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax1 = plt.subplots(figsize=(8, 4))
        ax1.bar(days, errors, color="#c44e52", alpha=0.85, label="errors")
        ax1.set_ylabel("errors")
        ax1.set_title(title)
        ax2 = ax1.twinx()
        ax2.plot(days, deploys, color="#4c72b0", marker="o", label="deploys")
        ax2.set_ylabel("deploys")
        fig.tight_layout()
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
        chart_note = str(out_path)
    except Exception as exc:  # noqa: BLE001
        chart_note = f"(matplotlib unavailable: {exc})"

    max_e = max(errors) or 1
    ascii_bars = " | ".join(
        f"{d}:{'#' * max(1, int(e / max_e * 8))}" for d, e in zip(days, errors)
    )
    risk = "elevated" if errors[-1] >= max(errors[:-1] or [0]) else "moderate"

    return _j(
        {
            "service": service,
            "chart_path": chart_note,
            "ascii": ascii_bars,
            "risk_signal": risk,
            "latest_errors": errors[-1],
            "latest_deploys": deploys[-1],
            "latency_p99_ms": row.get("latency_p99_ms"),
            "error_rate_pct": row.get("error_rate_pct"),
        }
    )


def compute_release_risk_score(service: str = "payments-service") -> str:
    data = load_sdlc()
    failed = len(data["failed_pipelines"])
    pending = len(data["pending_approvals"])
    budget = data["error_budget"].get(service, {})
    dora = data["dora_metrics"].get(service, {})
    score = min(
        100,
        failed * 12
        + pending * 10
        + int(dora.get("change_failure_rate_pct", 0))
        + int(max(0, 50 - budget.get("budget_remaining_pct", 50)) / 2),
    )
    return _j(
        {
            "service": service,
            "risk_score": score,
            "drivers": {
                "failed_pipelines": failed,
                "pending_approvals": pending,
                "change_failure_rate_pct": dora.get("change_failure_rate_pct"),
                "budget_remaining_pct": budget.get("budget_remaining_pct"),
            },
            "recommendation": (
                "hold"
                if score >= 60
                else "proceed_with_caution"
                if score >= 40
                else "go"
            ),
        }
    )

