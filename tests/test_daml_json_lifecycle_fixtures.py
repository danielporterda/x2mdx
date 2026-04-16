from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from x2mdx.cli import main as cli_main


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "daml_json" / "lifecycle_states"


class DamlJsonLifecycleFixtureTests(unittest.TestCase):
    def test_checked_in_lifecycle_fixtures_render_expected_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "daml-lifecycle"

            self.assertEqual(
                cli_main(
                    [
                        "daml-json",
                        "build-api-pages-from-manifest",
                        "--manifest",
                        str(FIXTURE_ROOT / "manifest.json"),
                        "--output-dir",
                        str(output_dir),
                        "--overview-title",
                        "DAML Lifecycle Fixtures",
                        "--source-name",
                        "local DAML lifecycle verification fixtures",
                        "--version-filter",
                        "verification fixture versions",
                    ]
                ),
                0,
            )

            overview_text = (output_dir / "index.mdx").read_text(encoding="utf-8")
            list_text = (output_dir / "da-list.mdx").read_text(encoding="utf-8")
            alpha_text = (output_dir / "da-alpha.mdx").read_text(encoding="utf-8")
            exception_text = (output_dir / "da-exceptionlike.mdx").read_text(encoding="utf-8")

            self.assertIn("DAML Lifecycle Fixtures", overview_text)
            self.assertNotIn("🟢", overview_text)
            self.assertNotIn("🔵", overview_text)
            self.assertNotIn("🟠", overview_text)
            self.assertNotIn("🔴", overview_text)
            self.assertNotIn('style="', overview_text)
            self.assertIn("style={{", overview_text)
            self.assertIn(">Alpha</span>", overview_text)
            self.assertIn(">Deprecated</span>", overview_text)

            self.assertIn("Lifecycle state: `deprecated`", list_text)
            self.assertIn("List helpers are deprecated for new code.", list_text)
            self.assertIn("Replaces: `DA.NonEmpty::module::DA.NonEmpty`", list_text)
            self.assertIn("Lifecycle state: `alpha`", alpha_text)
            self.assertIn("Lifecycle state: `deprecated`", exception_text)
            self.assertIn("Replaces: `-`", exception_text)


if __name__ == "__main__":
    unittest.main()
