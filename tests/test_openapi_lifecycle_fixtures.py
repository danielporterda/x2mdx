from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from x2mdx.cli import main as cli_main


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "openapi" / "lifecycle_states"


class OpenApiLifecycleFixtureTests(unittest.TestCase):
    def test_checked_in_lifecycle_and_replacement_fixtures_render_expected_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "lifecycle-pages"

            self.assertEqual(
                cli_main(
                    [
                        "openapi",
                        "build-api-pages-from-manifest",
                        "--manifest",
                        str(FIXTURE_ROOT / "manifest.json"),
                        "--root",
                        "published",
                        "--include-spec-pattern",
                        r"^lifecycle-example/openapi\.yaml$",
                        "--output-dir",
                        str(output_dir),
                        "--source-name",
                        "local OpenAPI lifecycle and replacement verification fixtures",
                        "--version-filter",
                        "verification fixture versions",
                    ]
                ),
                0,
            )

            spec_page = (output_dir / "specs" / "lifecycle-example-openapi-yaml.mdx").read_text(encoding="utf-8")

            self.assertIn("## Table of Contents", spec_page)
            self.assertIn("## Version Change Summary", spec_page)
            self.assertIn("## Reference", spec_page)
            self.assertNotIn("🟢", spec_page)
            self.assertNotIn("🔵", spec_page)
            self.assertNotIn("🟠", spec_page)
            self.assertNotIn("🔴", spec_page)
            self.assertNotIn('style="', spec_page)
            self.assertIn("style={{", spec_page)
            self.assertIn(">Alpha</span>", spec_page)
            self.assertIn(">Beta</span>", spec_page)
            self.assertIn(">Stable</span>", spec_page)
            self.assertIn(">Deprecated</span>", spec_page)
            self.assertIn("<code>alpha</code>", spec_page)
            self.assertIn("<code>beta</code>", spec_page)
            self.assertIn("<code>stable</code>", spec_page)
            self.assertIn("<code>deprecated</code>", spec_page)

            self.assertIn("### `/payments/alpha`", spec_page)
            self.assertIn("Lifecycle state: `alpha`", spec_page)
            self.assertIn("### `/payments`", spec_page)
            self.assertIn("Lifecycle state: `stable`", spec_page)
            self.assertIn("Replaces: `listPayments`", spec_page)

            self.assertIn("### `/payments/preview`", spec_page)
            self.assertIn("Lifecycle state: `beta`", spec_page)

            self.assertIn("### `/legacy-payments`", spec_page)
            self.assertIn("Lifecycle state: `deprecated`", spec_page)

            self.assertIn("operation id changed `listPayments` -> `listPaymentsV2`", spec_page)
            self.assertIn("lifecycle state changed `-` -> `stable`", spec_page)
            self.assertIn("replacement target changed `-` -> `listPayments`", spec_page)


if __name__ == "__main__":
    unittest.main()
