from __future__ import annotations

import argparse
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.harness.characterization_common import CHARACTERIZATION_ROOT, reset_dir, run_x2mdx


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "openapi" / "ledger_api"
CHARACTERIZATION_FIXTURE_DIR = CHARACTERIZATION_ROOT / "openapi"
EXPECTED_DIR = CHARACTERIZATION_FIXTURE_DIR / "expected"
EXPECTED_FILE = EXPECTED_DIR / "json-api-reference.mdx"


def refresh() -> Path:
    reset_dir(EXPECTED_DIR)
    run_x2mdx(
        [
            "openapi",
            "build-api-pages-from-manifest",
            "--manifest",
            str(FIXTURE_ROOT / "manifest.json"),
            "--root",
            "published",
            "--include-spec-pattern",
            r"^json-ledger-api/openapi\.yaml$",
            "--output-file",
            str(EXPECTED_FILE),
            "--source-name",
            "docs.digitalasset.com JSON Ledger API OpenAPI fixtures",
            "--version-filter",
            "published docs major versions",
            "--version",
            "3.4",
            "--version",
            "3.5",
        ]
    )
    return EXPECTED_FILE


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Refresh the rendered OpenAPI characterization fixture from the checked-in published Ledger API snapshots."
    )
    parser.parse_args()
    refresh()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
