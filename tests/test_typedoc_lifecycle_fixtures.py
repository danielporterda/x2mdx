from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from x2mdx.cli import main as cli_main


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "typedoc" / "lifecycle_states"


class TypeDocLifecycleFixtureTests(unittest.TestCase):
    def test_checked_in_lifecycle_and_replacement_fixtures_render_expected_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "typedoc-lifecycle.mdx"

            self.assertEqual(
                cli_main(
                    [
                        "typedoc",
                        "build-api-pages-from-manifest",
                        "--manifest",
                        str(FIXTURE_ROOT / "manifest.json"),
                        "--output-file",
                        str(output_file),
                        "--page-title",
                        "TypeScript",
                        "--page-description",
                        "Lifecycle fixture surface for TypeDoc.",
                    ]
                ),
                0,
            )

            page = output_file.read_text(encoding="utf-8")

            self.assertIn("## Table of Contents", page)
            self.assertIn("## Version Change Summary", page)
            self.assertIn("## Reference", page)
            self.assertNotIn("🟢", page)
            self.assertNotIn("🔵", page)
            self.assertNotIn("🟠", page)
            self.assertNotIn("🔴", page)
            self.assertNotIn('style="', page)
            self.assertIn("style={{", page)
            self.assertIn(">Alpha</span>", page)
            self.assertIn(">Beta</span>", page)
            self.assertIn(">Stable</span>", page)
            self.assertIn(">Deprecated</span>", page)
            self.assertIn("<code>alpha</code>", page)
            self.assertIn("<code>beta</code>", page)
            self.assertIn("<code>stable</code>", page)
            self.assertIn("<code>deprecated</code>", page)

            self.assertIn("#### ThingRecord", page)
            self.assertIn("Lifecycle state: `stable`", page)
            self.assertIn("Replaces: `Type Aliases::Thing`", page)

            self.assertIn("#### alphaWidget", page)
            self.assertIn("Lifecycle state: `alpha`", page)

            self.assertIn("#### listPaymentsPreview", page)
            self.assertIn("Lifecycle state: `beta`", page)

            self.assertIn("#### listPaymentsV2", page)
            self.assertIn("Replaces: `Functions::listPayments`", page)

            self.assertIn("#### LegacyWidget", page)
            self.assertIn("Lifecycle state: `deprecated`", page)
            self.assertIn("lifecycle state changed `-` -> `deprecated`", page)


if __name__ == "__main__":
    unittest.main()
