from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from x2mdx.cli import main as cli_main
from x2mdx.daml_json.lifecycle import build_daml_doc_report_from_sources
from x2mdx.daml_json.snapshots import load_daml_doc_sources


def module_doc(
    name: str,
    *,
    descr: str,
    deprecated: str | None = None,
) -> dict[str, object]:
    warns: list[dict[str, str]] = []
    if deprecated:
        warns.append({"DeprecatedData": deprecated})
    return {
        "md_name": name,
        "md_descr": descr,
        "md_warn": warns,
        "md_adts": [],
        "md_classes": [],
        "md_interfaces": [],
        "md_templates": [],
        "md_instances": [],
        "md_functions": [
            {
                "fct_name": "example",
                "fct_type": {"TypeFun": [{"TypeLit": "Int"}, {"TypeLit": "Int"}]},
                "fct_context": [],
                "fct_descr": f"{name} example function",
            }
        ],
    }


class DamlJsonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_json(self, relative_path: str, payload: object) -> Path:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path

    def _write_manifest(self) -> Path:
        first = self._write_json(
            "snapshots/1.0.0/modules.json",
            [
                module_doc("DA.List", descr="List module in 1.0.0"),
                module_doc("DA.Legacy", descr="Legacy module in 1.0.0"),
            ],
        )
        second = self._write_json(
            "snapshots/1.1.0/modules.json",
            [
                module_doc("DA.List", descr="List module in 1.1.0", deprecated="Use DA.NonEmpty instead."),
                module_doc("DA.NonEmpty", descr="NonEmpty module in 1.1.0"),
            ],
        )
        manifest = {
            "source": "unit test daml docs",
            "publish_version": "1.1.0",
            "versions": [
                {"version": "1.0.0", "json_path": str(first)},
                {"version": "1.1.0", "json_path": str(second)},
            ],
        }
        return self._write_json("manifest.json", manifest)

    def test_build_report_tracks_removed_and_deprecated_modules(self) -> None:
        manifest_path = self._write_manifest()
        sources = load_daml_doc_sources(manifest_path)
        report = build_daml_doc_report_from_sources(
            sources,
            source_name="unit test daml docs",
            version_filter="unit test versions",
        )

        self.assertEqual(report.publish_version, "1.1.0")
        self.assertEqual(report.module_deprecation_first_seen["DA.List"], "1.1.0")
        self.assertEqual(report.module_lifecycle["DA.Legacy"]["status"], "removed")
        self.assertEqual(report.module_lifecycle["DA.Legacy"]["removed_in"], "1.1.0")
        self.assertEqual(report.module_lifecycle["DA.NonEmpty"]["introduced_in"], "1.1.0")

        module_names = {str(module["md_name"]) for module in report.modules}
        self.assertIn("DA.Legacy", module_names)
        self.assertIn("DA.List", module_names)
        self.assertIn("DA.NonEmpty", module_names)

    def test_cli_builds_index_and_module_pages(self) -> None:
        manifest_path = self._write_manifest()
        output_dir = self.root / "out" / "daml-standard-library"

        result = cli_main(
            [
                "daml-json",
                "build-api-pages-from-manifest",
                "--manifest",
                str(manifest_path),
                "--output-dir",
                str(output_dir),
                "--source-name",
                "unit test daml docs",
                "--version-filter",
                "unit test versions",
            ]
        )

        self.assertEqual(result, 0)
        index_text = (output_dir / "index.mdx").read_text(encoding="utf-8")
        list_text = (output_dir / "da-list.mdx").read_text(encoding="utf-8")
        legacy_text = (output_dir / "da-legacy.mdx").read_text(encoding="utf-8")

        self.assertIn("Daml Standard Library", index_text)
        self.assertIn("removed in `1.1.0`", index_text)
        self.assertIn("Deprecated since: `1.1.0`", list_text)
        self.assertIn("historical reference", legacy_text)

