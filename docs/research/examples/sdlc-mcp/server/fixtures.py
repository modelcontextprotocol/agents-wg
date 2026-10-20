"""Load SDLC fixture data (same payload as deepagent-poc)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_sdlc() -> dict:
    path = Path(__file__).with_name("sdlc.json")
    return json.loads(path.read_text(encoding="utf-8"))
