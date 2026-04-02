from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from x2mdx.cli import main as cli_main


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "characterization"
GENERATED_AT_PATTERNS = [
    re.compile(r"Generated at \(UTC\): `[^`]+`"),
    re.compile(r"Generated at: `[^`]+`"),
]


def normalize_dynamic_text(text: str) -> str:
    normalized = text
    for pattern in GENERATED_AT_PATTERNS:
        normalized = pattern.sub(lambda match: match.group(0).split("`", 1)[0] + "`<normalized>`", normalized)
    return normalized


def mdx_tree(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): normalize_dynamic_text(path.read_text(encoding="utf-8"))
        for path in sorted(root.rglob("*.mdx"))
    }


class CharacterizationOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def assertTreeEqual(self, actual_root: Path, expected_root: Path) -> None:
        self.assertEqual(mdx_tree(actual_root), mdx_tree(expected_root))

    def test_openapi_render_matches_characterization_output(self) -> None:
        expected_file = FIXTURE_ROOT / "openapi" / "expected" / "json-api-reference.mdx"
        actual_file = self.root / "openapi" / "json-api-reference.mdx"
        manifest_path = REPO_ROOT / "tests" / "fixtures" / "openapi" / "ledger_api" / "manifest.json"

        result = cli_main(
            [
                "openapi",
                "build-api-pages-from-manifest",
                "--manifest",
                str(manifest_path),
                "--root",
                "published",
                "--include-spec-pattern",
                r"^json-ledger-api/openapi\.yaml$",
                "--output-file",
                str(actual_file),
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

        self.assertEqual(result, 0)
        self.assertEqual(actual_file.read_text(encoding="utf-8"), expected_file.read_text(encoding="utf-8"))

    def test_jvm_docs_render_matches_characterization_output(self) -> None:
        fixture_dir = FIXTURE_ROOT / "jvm_docs"
        actual_root = self.root / "jvm_docs"
        result = cli_main(
            [
                "jvm-docs",
                "build-api-pages-from-manifest",
                "--manifest",
                str(fixture_dir / "input" / "manifest.json"),
                "--overview-file",
                str(actual_root / "index.mdx"),
                "--details-dir",
                str(actual_root),
                "--overview-title",
                "Ledger API JVM Bindings",
                "--source-name",
                "Published DAML Java/Scala bindings Javadoc/Scaladoc jars",
                "--version-filter",
                "characterization fixture versions",
            ]
        )

        self.assertEqual(result, 0)
        self.assertTreeEqual(actual_root, fixture_dir / "expected")

    def test_daml_json_render_matches_characterization_output(self) -> None:
        fixture_dir = FIXTURE_ROOT / "daml_json"
        actual_root = self.root / "daml_json"
        result = cli_main(
            [
                "daml-json",
                "build-api-pages-from-manifest",
                "--manifest",
                str(fixture_dir / "input" / "manifest.json"),
                "--output-dir",
                str(actual_root),
                "--publish-version",
                "3.4.11",
                "--overview-title",
                "Daml Standard Library",
                "--source-name",
                "Published Daml Standard Library docs JSON from local SDK artifacts",
                "--version-filter",
                "characterization fixture versions",
                "--link-prefix",
                "/appdev/reference/daml-standard-library",
            ]
        )

        self.assertEqual(result, 0)
        self.assertTreeEqual(actual_root, fixture_dir / "expected")

    def test_protobuf_render_matches_characterization_output(self) -> None:
        fixture_dir = FIXTURE_ROOT / "protobuf"
        actual_root = self.root / "expected"
        result = cli_main(
            [
                "protobuf",
                "build-api-pages-from-manifest",
                "--manifest",
                str(fixture_dir / "input" / "manifest.json"),
                "--output-dir",
                str(actual_root),
                "--source-name",
                "Canton protobuf descriptor snapshots from release tags",
                "--version-filter",
                "characterization fixture versions",
            ]
        )

        self.assertEqual(result, 0)
        self.assertTreeEqual(actual_root, fixture_dir / "expected")

    def test_typedoc_render_matches_characterization_output(self) -> None:
        fixture_dir = FIXTURE_ROOT / "typedoc"
        actual_file = self.root / "typedoc" / "typescript.mdx"
        expected_file = fixture_dir / "expected" / "typescript.mdx"

        result = cli_main(
            [
                "typedoc",
                "build-api-pages-from-manifest",
                "--manifest",
                str(fixture_dir / "input" / "manifest.json"),
                "--output-file",
                str(actual_file),
                "--publish-version",
                "3.4.11",
                "--source-name",
                "Published @daml/types npm tarballs rendered to local TypeDoc JSON",
                "--version-filter",
                "characterization fixture versions",
                "--page-title",
                "TypeScript",
                "--page-description",
                "TypeScript and JavaScript language bindings for Canton.",
            ]
        )

        self.assertEqual(result, 0)
        self.assertEqual(actual_file.read_text(encoding="utf-8"), expected_file.read_text(encoding="utf-8"))
