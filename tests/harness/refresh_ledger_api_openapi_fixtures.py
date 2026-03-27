from __future__ import annotations

import argparse
import html
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "openapi" / "ledger_api"

LEDGER_API_SOURCES = [
    {
        "version": "3.4",
        "url": "https://docs.digitalasset.com/build/3.4/reference/json-api/openapi.html",
        "source_path": "published/json-ledger-api/openapi.yaml",
    },
    {
        "version": "3.5",
        "url": "https://docs.digitalasset.com/build/3.5/reference/json-api/openapi.html",
        "source_path": "published/json-ledger-api/openapi.yaml",
    },
]


def fetch_text(url: str) -> tuple[str | None, int | None]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request) as response:
            return response.read().decode("utf-8"), response.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return body, exc.code


def extract_yaml(html_text: str) -> str:
    blocks = re.findall(
        r'<div class="highlight-yaml notranslate"><div class="highlight"><pre>(.*?)</pre>',
        html_text,
        re.S,
    )
    rendered_blocks: list[str] = []
    for block in blocks:
        text = re.sub(r"<[^>]+>", "", block)
        text = html.unescape(text).strip("\n")
        text = re.sub(r"\n:lines:\s+[^\n]+\s*$", "", text)
        if text and text not in rendered_blocks:
            rendered_blocks.append(text)
    if not rendered_blocks:
        raise RuntimeError("No embedded YAML block found in the source page")
    return rendered_blocks[0] + "\n"


def refresh() -> dict:
    FIXTURE_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "source": "docs.digitalasset.com published JSON Ledger API OpenAPI pages",
        "captured_on": None,
        "versions": [],
    }

    for source in LEDGER_API_SOURCES:
        entry = {
            "version": source["version"],
            "url": source["url"],
            "source_path": source["source_path"],
        }
        html_text, status = fetch_text(source["url"])
        entry["http_status"] = status

        if status != 200 or html_text is None:
            entry["status"] = "unavailable"
            manifest["versions"].append(entry)
            continue

        yaml_text = extract_yaml(html_text)
        relative_path = Path(source["version"]) / "openapi.yaml"
        output_path = FIXTURE_ROOT / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(yaml_text, encoding="utf-8")

        entry["status"] = "captured"
        entry["fixture_path"] = relative_path.as_posix()
        manifest["versions"].append(entry)

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--captured-on",
        required=True,
        help="Capture date to record in the manifest, for example 2026-03-25",
    )
    args = parser.parse_args()

    manifest = refresh()
    manifest["captured_on"] = args.captured_on
    (FIXTURE_ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
