from __future__ import annotations

import re
import unittest
from pathlib import Path

from x2mdx.output import Page
from x2mdx.render import render_page


GENERATED_AT_PATTERNS = [
    re.compile(r"Generated at \(UTC\): `[^`]+`"),
    re.compile(r"Generated at: `[^`]+`"),
]


def normalize_dynamic_text(text: str) -> str:
    normalized = text
    for pattern in GENERATED_AT_PATTERNS:
        normalized = pattern.sub(lambda match: match.group(0).split("`", 1)[0] + "`<normalized>`", normalized)
    return normalized


def rendered_page(page: Page) -> str:
    return normalize_dynamic_text(render_page(page))


def rendered_page_map(pages: list[Page]) -> dict[str, str]:
    return {Path(page.path).as_posix(): rendered_page(page) for page in pages}


def assert_page_equal(testcase: unittest.TestCase, actual: Page, expected: Page) -> None:
    testcase.assertEqual(actual.path, expected.path)
    testcase.assertEqual(rendered_page(actual), rendered_page(expected))


def assert_page_tree_equal(testcase: unittest.TestCase, actual: list[Page], expected: list[Page]) -> None:
    testcase.assertEqual(rendered_page_map(actual), rendered_page_map(expected))
