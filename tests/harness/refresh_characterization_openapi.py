from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile
import sys


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.harness.characterization_common import CHARACTERIZATION_ROOT, load_json, reset_dir, run_x2mdx, write_json


FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "openapi" / "ledger_api"
CHARACTERIZATION_FIXTURE_DIR = CHARACTERIZATION_ROOT / "openapi"
EXPECTED_DIR = CHARACTERIZATION_FIXTURE_DIR / "expected"
EXPECTED_FILE = EXPECTED_DIR / "json-api-reference.mdx"
EXPECTED_MULTIPAGE_DIR = CHARACTERIZATION_FIXTURE_DIR / "expected_multipage"
DOCS_JSON_BEFORE = CHARACTERIZATION_FIXTURE_DIR / "docs_json.before.json"
DOCS_JSON_AFTER = CHARACTERIZATION_FIXTURE_DIR / "docs_json.after.json"


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
    reset_dir(EXPECTED_MULTIPAGE_DIR)
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
            "--output-dir",
            str(EXPECTED_MULTIPAGE_DIR),
            "--overview-name",
            "json-api-overview.mdx",
            "--overview-title",
            "JSON API OpenAPI Lifecycle",
            "--spec-dir-name",
            "json-api-specs",
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
    with tempfile.TemporaryDirectory() as temp_dir:
        docs_root = Path(temp_dir) / "docs-main"
        output_file = docs_root / "appdev" / "reference" / "json-api-reference.mdx"
        docs_json_path = docs_root / "docs.json"
        docs_json_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(DOCS_JSON_BEFORE, docs_json_path)
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
                str(output_file),
                "--docs-json",
                str(docs_json_path),
                "--nav-dropdown",
                "Reference",
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
        write_json(DOCS_JSON_AFTER, load_json(docs_json_path))
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
