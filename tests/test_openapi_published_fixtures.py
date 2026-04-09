from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from x2mdx.cli import main as cli_main
from tests.harness.ledger_api_openapi import load_manifest, load_published_ledger_api_snapshots
from x2mdx.openapi.lifecycle import build_openapi_lifecycle_report_from_snapshots
from x2mdx.openapi.models import OpenApiLifecycleConfig
from x2mdx.openapi.render import build_pages
from x2mdx.render import render_page


class PublishedLedgerApiFixtureTests(unittest.TestCase):
    def test_published_ledger_api_fixtures_build_report(self) -> None:
        manifest = load_manifest()
        snapshots = load_published_ledger_api_snapshots()

        manifest_versions = [entry["version"] for entry in manifest["versions"]]
        self.assertEqual(manifest_versions, ["3.4", "3.5"])
        self.assertEqual([snapshot.version for snapshot in snapshots], ["3.4", "3.5"])

        report = build_openapi_lifecycle_report_from_snapshots(
            snapshots,
            OpenApiLifecycleConfig(
                roots=["published"],
                include_spec_patterns=[r"^json-ledger-api/openapi\.yaml$"],
            ),
            source_name="docs.digitalasset.com JSON Ledger API OpenAPI fixtures",
            version_filter="published docs major versions",
        )

        self.assertEqual(report.tags, ["3.4", "3.5"])
        self.assertEqual(report.summary["spec_count"], 1)
        self.assertEqual(report.source_name, "docs.digitalasset.com JSON Ledger API OpenAPI fixtures")

        spec = report.specs[0]
        self.assertEqual(spec.spec_id, "json-ledger-api/openapi.yaml")
        self.assertEqual(spec.latest_version, "3.5")
        self.assertEqual(spec.latest_source_path, "published/json-ledger-api/openapi.yaml")
        self.assertGreater(spec.entity_count, 0)

        pages = build_pages(report)
        overview = next(page for page in pages if page.path == "overview.mdx")
        self.assertEqual(overview.title, "OpenAPI Lifecycle Overview")
        spec_page = next(page for page in pages if page.path == "specs/json-ledger-api-openapi-yaml.mdx")
        self.assertIn("Table of Contents", render_page(spec_page))

    def test_cli_build_api_pages_from_manifest_writes_mdx_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "ledger-api-pages"

            self.assertEqual(
                cli_main(
                    [
                        "openapi",
                        "build-api-pages-from-manifest",
                        "--manifest",
                        "tests/fixtures/openapi/ledger_api/manifest.json",
                        "--root",
                        "published",
                        "--include-spec-pattern",
                        r"^json-ledger-api/openapi\.yaml$",
                        "--output-dir",
                        str(output_dir),
                        "--version",
                        "3.4",
                        "--version",
                        "3.5",
                        "--source-name",
                        "docs.digitalasset.com JSON Ledger API OpenAPI fixtures",
                        "--version-filter",
                        "published docs major versions",
                    ]
                ),
                0,
            )

            self.assertTrue((output_dir / "overview.mdx").exists())
            self.assertTrue((output_dir / "specs" / "json-ledger-api-openapi-yaml.mdx").exists())
            spec_page = (output_dir / "specs" / "json-ledger-api-openapi-yaml.mdx").read_text(encoding="utf-8")
            self.assertIn("Table of Contents", spec_page)
            self.assertIn("| Name | Kind | Summary | Introduced | Changed | Deprecated | Removed |", spec_page)
            self.assertIn("| Content Type | Schema | Required Fields |", spec_page)
            self.assertIn("| `application/json` | `object` | `actAs`, `commandId`, `commands` |", spec_page)
            self.assertIn("**Request Example: `application/json`**", spec_page)
            self.assertIn('"commandId": "<string>"', spec_page)
            self.assertIn('"commands": [', spec_page)
            self.assertIn('"CreateAndExerciseCommand": {', spec_page)
            self.assertIn('"templateId": "<string>"', spec_page)


if __name__ == "__main__":
    unittest.main()
