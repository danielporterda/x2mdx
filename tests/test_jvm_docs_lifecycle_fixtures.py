from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from x2mdx.cli import main as cli_main


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "jvm_docs" / "lifecycle_states"


class JvmDocsLifecycleFixtureTests(unittest.TestCase):
    def test_checked_in_lifecycle_fixtures_render_expected_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_root = Path(temp_dir) / "jvm-lifecycle"
            overview_file = output_root / "index.mdx"
            details_dir = output_root / "details"

            self.assertEqual(
                cli_main(
                    [
                        "jvm-docs",
                        "build-api-pages-from-manifest",
                        "--manifest",
                        str(FIXTURE_ROOT / "manifest.json"),
                        "--overview-file",
                        str(overview_file),
                        "--details-dir",
                        str(details_dir),
                        "--overview-title",
                        "JVM Lifecycle Fixtures",
                        "--source-name",
                        "local JVM lifecycle verification fixtures",
                        "--version-filter",
                        "verification fixture versions",
                    ]
                ),
                0,
            )

            overview_text = overview_file.read_text(encoding="utf-8")
            java_detail_text = (details_dir / "bindings-java.mdx").read_text(encoding="utf-8")
            scala_detail_text = (details_dir / "bindings-scala-2-13.mdx").read_text(encoding="utf-8")
            java_package_text = (
                details_dir / "bindings-java-packages" / "com-example.mdx"
            ).read_text(encoding="utf-8")
            scala_package_text = (
                details_dir / "bindings-scala-2-13-packages" / "com-example-scala.mdx"
            ).read_text(encoding="utf-8")

            self.assertIn("JVM Lifecycle Fixtures", overview_text)
            self.assertIn("local JVM lifecycle verification fixtures", overview_text)
            self.assertIn("bindings-java", overview_text)
            self.assertIn("bindings-scala_2.13", overview_text)

            self.assertIn("## Table of Contents", java_detail_text)
            self.assertIn("🟢", java_detail_text)
            self.assertIn("🔵", java_detail_text)
            self.assertIn("Lifecycle state: `beta`", java_package_text)
            self.assertIn("| `newMethod` | `stable` | `com.example.Foo#oldMethod()` |", java_package_text)
            self.assertIn("| `oldMethod` | `deprecated` | - | `1.0.0` | `1.1.0` | - |", java_package_text)

            self.assertIn("## Table of Contents", scala_detail_text)
            self.assertIn("Lifecycle state: `alpha`", scala_package_text)


if __name__ == "__main__":
    unittest.main()
