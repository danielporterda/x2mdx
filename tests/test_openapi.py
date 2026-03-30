from __future__ import annotations

import io
import json
import tempfile
import textwrap
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from x2mdx.cli import main as cli_main
from x2mdx.openapi.lifecycle import build_openapi_lifecycle_report_from_snapshots, parse_openapi
from x2mdx.openapi.models import OpenApiLifecycleConfig, OpenApiSourceSnapshot
from x2mdx.openapi.render import build_pages
from x2mdx.openapi.serde import report_from_json_data, report_to_json_data
from x2mdx.render import write_pages


def write_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(contents).lstrip(), encoding="utf-8")


class OpenApiLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _config(self) -> OpenApiLifecycleConfig:
        return OpenApiLifecycleConfig(
            roots=["published"],
            include_spec_patterns=[r"^utility\.yaml$"],
            canonical_path_map={"v1/utility.yaml": "utility.yaml"},
            priority_prefixes=["published/v1/", "published/"],
        )

    def _snapshot(self, version: str, source_path: str, contents: str) -> OpenApiSourceSnapshot:
        return OpenApiSourceSnapshot(
            version=version,
            source_path=source_path,
            document=parse_openapi(textwrap.dedent(contents).lstrip()),
        )

    def _write_manifest(
        self,
        *,
        name: str,
        versions: list[tuple[str, str, str]],
    ) -> Path:
        fixture_root = self.root / name
        manifest = {
            "source": f"{name} test fixtures",
            "captured_on": "2026-03-26",
            "versions": [],
        }
        for version, source_path, contents in versions:
            relative_path = Path(version) / "openapi.yaml"
            write_text(fixture_root / relative_path, contents)
            manifest["versions"].append(
                {
                    "version": version,
                    "status": "captured",
                    "source_path": source_path,
                    "fixture_path": relative_path.as_posix(),
                }
            )

        manifest_path = fixture_root / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        return manifest_path

    def test_build_lifecycle_tracks_versions_and_removed_entities(self) -> None:
        snapshots = [
            self._snapshot(
                "v0.1.0",
                "published/utility.yaml",
                """
                openapi: 3.0.3
                info:
                  title: Utility API
                  version: 0.1.0
                paths:
                  /ping:
                    get:
                      operationId: getPing
                      summary: Ping
                      tags: [health]
                      responses:
                        "200":
                          description: ok
                components:
                  schemas:
                    PingResponse:
                      type: object
                      properties:
                        ok:
                          type: boolean
                tags:
                  - name: health
                """,
            ),
            self._snapshot(
                "v0.1.1",
                "published/v1/utility.yaml",
                """
                openapi: 3.0.3
                info:
                  title: Utility API
                  version: 0.1.1
                paths:
                  /ping:
                    get:
                      operationId: getPing
                      summary: Ping endpoint
                      tags: [health]
                      responses:
                        "200":
                          description: ok
                components:
                  schemas:
                    PingResponse:
                      type: object
                      properties:
                        status:
                          type: string
                    HealthResponse:
                      type: object
                      properties:
                        ok:
                          type: boolean
                tags:
                  - name: health
                """,
            ),
            self._snapshot(
                "v0.1.2",
                "published/v1/utility.yaml",
                """
                openapi: 3.0.3
                info:
                  title: Utility API
                  version: 0.1.2
                paths:
                  /health:
                    get:
                      operationId: getHealth
                      summary: Health endpoint
                      tags: [health]
                      responses:
                        "200":
                          description: ok
                components:
                  schemas:
                    HealthResponse:
                      type: object
                      properties:
                        ok:
                          type: boolean
                tags:
                  - name: health
                """,
            ),
        ]

        report = build_openapi_lifecycle_report_from_snapshots(
            snapshots,
            self._config(),
            source_name="unit test snapshots",
            version_filter="unit test versions",
        )

        self.assertEqual(report.tags, ["v0.1.0", "v0.1.1", "v0.1.2"])
        self.assertEqual(report.summary["spec_count"], 1)

        spec = report.specs[0]
        self.assertEqual(spec.spec_id, "utility.yaml")
        self.assertEqual(spec.latest_source_path, "published/v1/utility.yaml")
        self.assertEqual(spec.introduced_version, "v0.1.0")
        self.assertEqual(spec.changed_in_versions, ["v0.1.1", "v0.1.2"])
        self.assertEqual(spec.latest_version, "v0.1.2")

        entity_by_name = {entity.name: entity for entity in spec.entity_lifecycle}
        self.assertEqual(entity_by_name["GET /ping"].introduced_version, "v0.1.0")
        self.assertEqual(entity_by_name["GET /ping"].removed_version, "v0.1.2")
        self.assertEqual(entity_by_name["GET /health"].introduced_version, "v0.1.2")
        self.assertEqual(entity_by_name["schemas.HealthResponse"].introduced_version, "v0.1.1")

        self.assertEqual(spec.per_version_entity_deltas["v0.1.1"]["changed_count"], 3)
        self.assertEqual(spec.per_version_entity_deltas["v0.1.2"]["removed_count"], 3)

    def test_render_pages_from_report_round_trip(self) -> None:
        report = build_openapi_lifecycle_report_from_snapshots(
            [
                self._snapshot(
                    "v0.1.0",
                    "published/utility.yaml",
                    """
                    openapi: 3.0.3
                    info:
                      title: Utility API
                      version: 0.1.0
                    paths:
                      /ping:
                        get:
                          operationId: getPing
                          summary: Ping
                          tags: [health]
                          responses:
                            "200":
                              description: ok
                    """,
                ),
                self._snapshot(
                    "v0.1.1",
                    "published/utility.yaml",
                    """
                    openapi: 3.0.3
                    info:
                      title: Utility API
                      version: 0.1.1
                    paths:
                      /ping:
                        get:
                          operationId: getPing
                          summary: Ping endpoint
                          tags: [health]
                          parameters:
                            - name: limit
                              in: query
                              schema:
                                type: integer
                          responses:
                            "200":
                              description: pong
                            "202":
                              description: accepted
                    """,
                ),
            ],
            self._config(),
            source_name="unit test snapshots",
            version_filter="unit test versions",
        )
        round_tripped = report_from_json_data(report_to_json_data(report))
        pages = build_pages(round_tripped)

        out_dir = self.root / "out"
        written = write_pages(pages, out_dir)
        written_paths = {path.relative_to(out_dir).as_posix() for path in written}

        self.assertIn("overview.mdx", written_paths)
        self.assertIn("specs/utility-yaml.mdx", written_paths)

        overview = (out_dir / "overview.mdx").read_text(encoding="utf-8")
        spec_page = (out_dir / "specs" / "utility-yaml.mdx").read_text(encoding="utf-8")

        self.assertIn("OpenAPI Lifecycle Overview", overview)
        self.assertIn("[Open](./specs/utility-yaml)", overview)
        self.assertIn("Version Change Timeline", spec_page)
        self.assertIn("Endpoint Diff Summary", spec_page)
        self.assertIn("[`GET /ping`](#endpoint-get-ping)", spec_page)
        self.assertIn('<a id="endpoint-get-ping"></a>', spec_page)
        self.assertIn("summary changed `Ping` -> `Ping endpoint`", spec_page)
        self.assertIn("query param `limit` added", spec_page)
        self.assertIn("response `200` description updated", spec_page)
        self.assertIn("response `202` added", spec_page)
        self.assertLess(spec_page.index("Endpoint Diff Summary"), spec_page.index("Spec Metadata"))
        self.assertGreater(spec_page.index("Spec Metadata"), spec_page.index("Latest Components"))
        self.assertGreater(spec_page.index("Entity Summary"), spec_page.index("Spec Metadata"))
        self.assertIn("Endpoint Reference (Latest)", spec_page)
        self.assertIn("### `GET /ping`", spec_page)
        self.assertNotIn("| Endpoint | Operation ID | Summary | Tags |", spec_page)

    def test_render_pages_show_required_request_body_fields(self) -> None:
        report = build_openapi_lifecycle_report_from_snapshots(
            [
                self._snapshot(
                    "v0.1.0",
                    "published/utility.yaml",
                    """
                    openapi: 3.0.3
                    info:
                      title: Utility API
                      version: 0.1.0
                    paths:
                      /submit:
                        post:
                          operationId: submitCommand
                          requestBody:
                            required: true
                            content:
                              application/json:
                                schema:
                                  $ref: '#/components/schemas/SubmitRequest'
                          responses:
                            "200":
                              description: accepted
                    components:
                      schemas:
                        SubmitRequest:
                          type: object
                          required:
                            - commandId
                            - payload
                          properties:
                            commandId:
                              type: string
                            payload:
                              type: object
                              required:
                                - innerId
                              properties:
                                innerId:
                                  type: string
                                includeDetails:
                                  type: boolean
                            traceId:
                              type: string
                    """,
                ),
            ],
            self._config(),
            source_name="unit test snapshots",
            version_filter="unit test versions",
        )
        pages = build_pages(report)

        out_dir = self.root / "out-request-body"
        write_pages(pages, out_dir)
        spec_page = (out_dir / "specs" / "utility-yaml.mdx").read_text(encoding="utf-8")

        self.assertIn("### `POST /submit`", spec_page)
        self.assertIn("| Content Type | Schema | Required Fields |", spec_page)
        self.assertIn("| `application/json` | `object` | `commandId`, `payload` |", spec_page)
        self.assertIn("**Request Example: `application/json`**", spec_page)
        self.assertIn('"commandId": "<string>"', spec_page)
        self.assertIn('"payload": {', spec_page)
        self.assertIn('"innerId": "<string>"', spec_page)

    def test_render_pages_keep_openapi_path_placeholders_readable(self) -> None:
        report = build_openapi_lifecycle_report_from_snapshots(
            [
                self._snapshot(
                    "v0.1.0",
                    "published/utility.yaml",
                    """
                    openapi: 3.0.3
                    info:
                      title: Utility API
                      version: 0.1.0
                    paths:
                      /items/{itemId}:
                        get:
                          operationId: getItem
                          summary: Fetch {itemId}
                          description: Get {itemId} by id.
                          responses:
                            "200":
                              description: ok
                    """,
                )
            ],
            self._config(),
            source_name="unit test snapshots",
            version_filter="unit test versions",
        )

        pages = build_pages(report)
        out_dir = self.root / "escaped"
        write_pages(pages, out_dir)
        spec_page = (out_dir / "specs" / "utility-yaml.mdx").read_text(encoding="utf-8")

        self.assertIn("`GET /items/{itemId}`", spec_page)
        self.assertIn("Fetch \\{itemId\\}", spec_page)
        self.assertIn("Get \\{itemId\\} by id.", spec_page)
        self.assertNotIn("&#123;", spec_page)
        self.assertNotIn("&#125;", spec_page)

    def test_cli_list_formats_outputs_supported_formats(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            result = cli_main(["list-formats"])

        self.assertEqual(result, 0)
        self.assertEqual(stdout.getvalue(), "openapi\njvm-docs\n")

    def test_cli_build_api_pages_from_manifest_writes_mdx_pages(self) -> None:
        manifest_path = self._write_manifest(
            name="cli-lifecycle",
            versions=[
                (
                    "v0.1.0",
                    "published/utility.yaml",
                    """
                    openapi: 3.0.3
                    info:
                      title: Utility API
                      version: 0.1.0
                    paths:
                      /ping:
                        get:
                          operationId: getPing
                          summary: Ping
                          responses:
                            "200":
                              description: ok
                    """,
                ),
                (
                    "v0.1.1",
                    "published/utility.yaml",
                    """
                    openapi: 3.0.3
                    info:
                      title: Utility API
                      version: 0.1.1
                    paths:
                      /ping:
                        get:
                          operationId: getPing
                          summary: Ping endpoint
                          responses:
                            "200":
                              description: ok
                    """,
                ),
            ],
        )

        out_dir = self.root / "rendered"
        self.assertEqual(
            cli_main(
                [
                    "openapi",
                    "build-api-pages-from-manifest",
                    "--manifest",
                    str(manifest_path),
                    "--root",
                    "published",
                    "--include-spec-pattern",
                    r"^utility\.yaml$",
                    "--output-dir",
                    str(out_dir),
                ]
            ),
            0,
        )
        self.assertTrue((out_dir / "overview.mdx").exists())
        self.assertTrue((out_dir / "specs" / "utility-yaml.mdx").exists())

    def test_cli_build_api_pages_from_manifest_writes_single_file_and_updates_docs_json(self) -> None:
        manifest_path = self._write_manifest(
            name="cli-docs-json",
            versions=[
                (
                    "v0.1.0",
                    "published/utility.yaml",
                    """
                    openapi: 3.0.3
                    info:
                      title: Utility API
                      version: 0.1.0
                    paths:
                      /ping:
                        get:
                          operationId: getPing
                          summary: Ping
                          responses:
                            "200":
                              description: ok
                    """,
                ),
                (
                    "v0.1.1",
                    "published/utility.yaml",
                    """
                    openapi: 3.0.3
                    info:
                      title: Utility API
                      version: 0.1.1
                    paths:
                      /ping:
                        get:
                          operationId: getPing
                          summary: Ping endpoint
                          responses:
                            "200":
                              description: ok
                    """,
                ),
            ],
        )
        docs_root = self.root / "docs-main"
        output_file = docs_root / "appdev" / "reference" / "json-api-reference.mdx"
        docs_json_path = docs_root / "docs.json"
        docs_json_path.parent.mkdir(parents=True, exist_ok=True)
        docs_json_path.write_text(
            json.dumps(
                {
                    "$schema": "https://mintlify.com/docs.json",
                    "navigation": {
                        "dropdowns": [
                            {
                                "dropdown": "App Development",
                                "versions": [
                                    {
                                        "version": "MainNet",
                                        "groups": [
                                            {
                                                "group": "Get Started",
                                                "pages": ["appdev/get-started/choose-your-path"],
                                            }
                                        ],
                                    },
                                    {
                                        "version": "TestNet",
                                        "groups": [
                                            {
                                                "group": "Get Started",
                                                "pages": ["appdev/get-started/choose-your-path"],
                                            }
                                        ],
                                    },
                                ],
                            }
                        ]
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        self.assertEqual(
            cli_main(
                [
                    "openapi",
                    "build-api-pages-from-manifest",
                    "--manifest",
                    str(manifest_path),
                    "--root",
                    "published",
                    "--include-spec-pattern",
                    r"^utility\.yaml$",
                    "--output-file",
                    str(output_file),
                    "--docs-json",
                    str(docs_json_path),
                    "--nav-dropdown",
                    "App Development",
                    "--nav-group",
                    "Reference",
                ]
            ),
            0,
        )

        self.assertTrue(output_file.exists())
        rendered = output_file.read_text(encoding="utf-8")
        self.assertIn('title: "Utility API"', rendered)
        self.assertIn("Endpoint Reference (Latest)", rendered)
        self.assertNotIn("| Endpoint | Operation ID | Summary | Tags |", rendered)

        docs_json = json.loads(docs_json_path.read_text(encoding="utf-8"))
        versions = docs_json["navigation"]["dropdowns"][0]["versions"]
        for version in versions:
            reference_group = next(group for group in version["groups"] if group["group"] == "Reference")
            self.assertEqual(reference_group["pages"], ["appdev/reference/json-api-reference"])


if __name__ == "__main__":
    unittest.main()
