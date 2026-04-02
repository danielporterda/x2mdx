from __future__ import annotations

import io
import json
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from x2mdx.asyncapi.lifecycle import build_asyncapi_report_from_sources, parse_asyncapi
from x2mdx.asyncapi.models import AsyncApiSourceSnapshot
from x2mdx.cli import main as cli_main


def write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(contents).lstrip(), encoding="utf-8")


class AsyncApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _snapshot(self, version: str, source_path: str, contents: str) -> AsyncApiSourceSnapshot:
        return AsyncApiSourceSnapshot(
            version=version,
            source_path=source_path,
            document=parse_asyncapi(textwrap.dedent(contents).lstrip()),
        )

    def _write_manifest(self) -> Path:
        fixture_root = self.root / "fixtures"
        manifest = {
            "source": "asyncapi test fixtures",
            "versions": [],
        }
        versions = {
            "1.0.0": """
                asyncapi: 2.6.0
                info:
                  title: Sample WebSocket API
                  version: 1.0.0
                channels:
                  /stream:
                    description: Stream updates.
                    publish:
                      operationId: sendStream
                      bindings:
                        ws:
                          method: GET
                      message:
                        $ref: '#/components/messages/StreamRequest'
                    subscribe:
                      operationId: onStream
                      bindings:
                        ws:
                          method: GET
                      message:
                        $ref: '#/components/messages/StreamEvent'
                  /legacy:
                    subscribe:
                      operationId: onLegacy
                      bindings:
                        ws:
                          method: GET
                      message:
                        $ref: '#/components/messages/LegacyEvent'
                components:
                  schemas:
                    StreamRequest:
                      type: object
                      required: [party]
                      properties:
                        party:
                          type: string
                    StreamEvent:
                      type: object
                      required: [offset]
                      properties:
                        offset:
                          type: string
                    LegacyEvent:
                      type: object
                      properties:
                        value:
                          type: string
                  messages:
                    StreamRequest:
                      contentType: application/json
                      payload:
                        $ref: '#/components/schemas/StreamRequest'
                    StreamEvent:
                      contentType: application/json
                      payload:
                        $ref: '#/components/schemas/StreamEvent'
                    LegacyEvent:
                      contentType: application/json
                      payload:
                        $ref: '#/components/schemas/LegacyEvent'
            """,
            "1.1.0": """
                asyncapi: 2.6.0
                info:
                  title: Sample WebSocket API
                  version: 1.1.0
                channels:
                  /stream:
                    description: Stream updates for clients.
                    publish:
                      operationId: sendStream
                      bindings:
                        ws:
                          method: GET
                      message:
                        $ref: '#/components/messages/StreamRequest'
                    subscribe:
                      operationId: onStream
                      bindings:
                        ws:
                          method: GET
                      message:
                        $ref: '#/components/messages/StreamEvent'
                  /updates:
                    subscribe:
                      operationId: onUpdates
                      bindings:
                        ws:
                          method: GET
                      message:
                        $ref: '#/components/messages/UpdateEvent'
                components:
                  schemas:
                    StreamRequest:
                      type: object
                      required: [party, offset]
                      properties:
                        party:
                          type: string
                        offset:
                          type: string
                    StreamEvent:
                      type: object
                      required: [offset]
                      properties:
                        offset:
                          type: string
                    UpdateEvent:
                      type: object
                      required: [id]
                      properties:
                        id:
                          type: string
                  messages:
                    StreamRequest:
                      contentType: application/json
                      payload:
                        $ref: '#/components/schemas/StreamRequest'
                    StreamEvent:
                      contentType: application/json
                      payload:
                        $ref: '#/components/schemas/StreamEvent'
                    UpdateEvent:
                      contentType: application/json
                      payload:
                        $ref: '#/components/schemas/UpdateEvent'
            """,
        }

        for version, contents in versions.items():
            relative_path = Path(version) / "asyncapi.yaml"
            write_text(fixture_root / relative_path, contents)
            manifest["versions"].append(
                {
                    "version": version,
                    "source_path": f"published/{version}/asyncapi.yaml",
                    "fixture_path": relative_path.as_posix(),
                }
            )

        manifest_path = fixture_root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return manifest_path

    def test_build_report_tracks_channel_changes_and_removals(self) -> None:
        report = build_asyncapi_report_from_sources(
            [
                self._snapshot(
                    "1.0.0",
                    "published/1.0.0/asyncapi.yaml",
                    """
                    asyncapi: 2.6.0
                    info:
                      title: Sample WebSocket API
                      version: 1.0.0
                    channels:
                      /stream:
                        description: Stream updates.
                        publish:
                          operationId: sendStream
                          bindings:
                            ws:
                              method: GET
                          message:
                            $ref: '#/components/messages/StreamRequest'
                      /legacy:
                        subscribe:
                          operationId: onLegacy
                          bindings:
                            ws:
                              method: GET
                          message:
                            $ref: '#/components/messages/LegacyEvent'
                    components:
                      schemas:
                        StreamRequest:
                          type: object
                          required: [party]
                          properties:
                            party:
                              type: string
                        LegacyEvent:
                          type: object
                          properties:
                            value:
                              type: string
                      messages:
                        StreamRequest:
                          contentType: application/json
                          payload:
                            $ref: '#/components/schemas/StreamRequest'
                        LegacyEvent:
                          contentType: application/json
                          payload:
                            $ref: '#/components/schemas/LegacyEvent'
                    """,
                ),
                self._snapshot(
                    "1.1.0",
                    "published/1.1.0/asyncapi.yaml",
                    """
                    asyncapi: 2.6.0
                    info:
                      title: Sample WebSocket API
                      version: 1.1.0
                    channels:
                      /stream:
                        description: Stream updates for clients.
                        publish:
                          operationId: sendStream
                          bindings:
                            ws:
                              method: GET
                          message:
                            $ref: '#/components/messages/StreamRequest'
                      /updates:
                        subscribe:
                          operationId: onUpdates
                          bindings:
                            ws:
                              method: GET
                          message:
                            $ref: '#/components/messages/UpdateEvent'
                    components:
                      schemas:
                        StreamRequest:
                          type: object
                          required: [party, offset]
                          properties:
                            party:
                              type: string
                            offset:
                              type: string
                        UpdateEvent:
                          type: object
                          required: [id]
                          properties:
                            id:
                              type: string
                      messages:
                        StreamRequest:
                          contentType: application/json
                          payload:
                            $ref: '#/components/schemas/StreamRequest'
                        UpdateEvent:
                          contentType: application/json
                          payload:
                            $ref: '#/components/schemas/UpdateEvent'
                    """,
                ),
            ],
            source_name="unit test snapshots",
            version_filter="unit test versions",
        )

        self.assertEqual(report.versions, ["1.0.0", "1.1.0"])
        self.assertEqual(report.publish_version, "1.1.0")
        channels = {channel.channel: channel for channel in report.channels}

        self.assertEqual(channels["/stream"].introduced_version, "1.0.0")
        self.assertEqual(channels["/stream"].changed_in_versions, ["1.1.0"])
        self.assertEqual(
            channels["/stream"].change_details,
            [
                {
                    "version": "1.1.0",
                    "changes": [
                        "channel description updated",
                        "publish required fields added: `offset`",
                    ],
                }
            ],
        )
        self.assertEqual(channels["/updates"].introduced_version, "1.1.0")
        self.assertEqual(channels["/legacy"].removed_version, "1.1.0")
        self.assertEqual(report.per_version_deltas["1.1.0"]["added_count"], 1)
        self.assertEqual(report.per_version_deltas["1.1.0"]["changed_count"], 1)
        self.assertEqual(report.per_version_deltas["1.1.0"]["removed_count"], 1)

    def test_cli_builds_asyncapi_page_and_updates_docs_json(self) -> None:
        manifest_path = self._write_manifest()
        output_file = self.root / "docs" / "reference" / "asyncapi.mdx"
        docs_json = self.root / "docs" / "docs.json"
        docs_json.parent.mkdir(parents=True, exist_ok=True)
        docs_json.write_text(
            json.dumps(
                {
                    "navigation": {
                        "dropdowns": [
                            {
                                "dropdown": "Reference",
                                "pages": [],
                            }
                        ]
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = cli_main(
                [
                    "asyncapi",
                    "build-api-pages-from-manifest",
                    "--manifest",
                    str(manifest_path),
                    "--output-file",
                    str(output_file),
                    "--docs-json",
                    str(docs_json),
                    "--nav-dropdown",
                    "Reference",
                    "--nav-group",
                    "JSON Ledger API",
                ]
            )

        self.assertEqual(exit_code, 0, stdout.getvalue())
        text = output_file.read_text(encoding="utf-8")
        docs = json.loads(docs_json.read_text(encoding="utf-8"))

        self.assertIn("Channel Diff Summary", text)
        self.assertIn("Version Change Timeline", text)
        self.assertIn("publish required fields added: `offset`", text)
        self.assertIn("**Message Example**", text)
        self.assertEqual(
            docs["navigation"]["dropdowns"][0]["groups"],
            [{"group": "JSON Ledger API", "pages": ["reference/asyncapi"]}],
        )

