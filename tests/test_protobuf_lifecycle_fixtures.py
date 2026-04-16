from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from x2mdx.cli import main as cli_main


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "protobuf" / "lifecycle_states"


class ProtobufLifecycleFixtureTests(unittest.TestCase):
    def test_checked_in_lifecycle_fixtures_render_expected_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "protobuf-lifecycle"

            self.assertEqual(
                cli_main(
                    [
                        "protobuf",
                        "build-api-pages-from-manifest",
                        "--manifest",
                        str(FIXTURE_ROOT / "manifest.json"),
                        "--output-dir",
                        str(output_dir),
                        "--source-name",
                        "local protobuf lifecycle verification fixtures",
                        "--version-filter",
                        "verification fixture versions",
                    ]
                ),
                0,
            )

            overview_text = (output_dir / "index.mdx").read_text(encoding="utf-8")
            package_text = (output_dir / "packages" / "com-example-v1.mdx").read_text(encoding="utf-8")

            self.assertIn("Canton Protobuf History", overview_text)
            self.assertIn("local protobuf lifecycle verification fixtures", overview_text)
            self.assertIn("Table of Contents", overview_text)
            self.assertIn("Release Summary", overview_text)
            self.assertIn("## Reference", overview_text)
            self.assertIn("com-example-v1", overview_text)
            self.assertIn("Lifecycle state: `alpha`", package_text)
            self.assertIn("Lifecycle state: `beta`", package_text)
            self.assertIn("Lifecycle state: `stable`", package_text)
            self.assertIn("Lifecycle state: `deprecated`", package_text)
            self.assertIn("Replaces: `com.example.v1.ExampleService/GetFoo`", package_text)
            self.assertIn("**Endpoint `ExampleService.PreviewPayments`**", package_text)
            self.assertIn("**Endpoint `ExampleService.GetFoo`**", package_text)


if __name__ == "__main__":
    unittest.main()
