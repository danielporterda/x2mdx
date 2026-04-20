from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from x2mdx.cli import main as cli_main

from tests.harness.characterization_cases import CHARACTERIZATION_CASES, CharacterizationCase


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

    def assertFileEqual(self, actual_file: Path, expected_file: Path) -> None:
        self.assertEqual(
            normalize_dynamic_text(actual_file.read_text(encoding="utf-8")),
            normalize_dynamic_text(expected_file.read_text(encoding="utf-8")),
        )

    def assertJsonEqual(self, actual_file: Path, expected_file: Path) -> None:
        self.assertEqual(
            json.loads(actual_file.read_text(encoding="utf-8")),
            json.loads(expected_file.read_text(encoding="utf-8")),
        )

    def prepare_docs_json(self, case: CharacterizationCase) -> None:
        if case.docs_json_before is None or case.actual_docs_json is None:
            return
        actual_docs_json = self.root / case.actual_docs_json
        actual_docs_json.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(case.docs_json_before, actual_docs_json)

    def test_characterization_outputs_match_golden_fixtures(self) -> None:
        for case in CHARACTERIZATION_CASES:
            with self.subTest(case=case.name):
                self.prepare_docs_json(case)
                result = cli_main(case.argv_factory(self.root))
                self.assertEqual(result, 0)

                if case.expected_file is not None and case.actual_file is not None:
                    self.assertFileEqual(self.root / case.actual_file, case.expected_file)
                if case.expected_tree is not None and case.actual_tree is not None:
                    self.assertTreeEqual(self.root / case.actual_tree, case.expected_tree)
                if case.docs_json_after is not None and case.actual_docs_json is not None:
                    self.assertJsonEqual(self.root / case.actual_docs_json, case.docs_json_after)
