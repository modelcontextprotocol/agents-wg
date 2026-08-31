"""Flat MCP server — same tools as ``server.main``, but **no agents**.

Does not call ``register_agents()``, so ``server/discover`` will not advertise
``io.modelcontextprotocol/agents``. Clients use classic ``tools/list`` (~18 schemas).

  python -m server.main_flat
"""

from __future__ import annotations

from server.main import mcp

if __name__ == "__main__":
    mcp.run()
