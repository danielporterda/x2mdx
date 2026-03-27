from __future__ import annotations

import json
from pathlib import Path

from x2mdx.openapi.snapshots import load_openapi_source_snapshots

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "openapi" / "ledger_api"
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def load_published_ledger_api_snapshots() -> list[OpenApiSourceSnapshot]:
    return load_openapi_source_snapshots(MANIFEST_PATH)
