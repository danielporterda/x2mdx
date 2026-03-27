"""Render OpenAPI lifecycle reports into shared output-side page models."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from x2mdx.mintlify import MintlifyGroup
from x2mdx.openapi.models import OpenApiEntityLifecycle, OpenApiLifecycleReport, OpenApiSpecLifecycle
from x2mdx.output import BulletList, Heading, Page, Paragraph, RawMarkdown, Table

MAX_CHANGED_ENTITIES = 300
MAX_LATEST_OPERATIONS = 300
MAX_LATEST_COMPONENTS = 400
MAX_ENDPOINTS = 200


def slugify(value: str) -> str:
    output = value.lower()
    output = re.sub(r"[^a-z0-9]+", "-", output)
    output = re.sub(r"-{2,}", "-", output).strip("-")
    return output


def md_text(text: Any) -> str:
    output = html.escape(str(text), quote=False)
    output = output.replace("{", "\\{").replace("}", "\\}")
    output = output.replace("|", "\\|").replace("\n", " ").strip()
    return output


def md_code(text: Any) -> str:
    output = str(text).replace("`", "\\`").replace("|", "\\|").replace("\n", " ").strip()
    return f"`{output}`"


def lifecycle_value(value: str | None, kind: str) -> str:
    if not value:
        return "-"
    rendered = md_code(value)
    if kind == "removed":
        return f"❌ {rendered}"
    return rendered


def changed_versions_value(changed_versions: list[str]) -> str:
    if not changed_versions:
        return "-"
    if len(changed_versions) <= 5:
        return md_code(", ".join(changed_versions))
    head = ", ".join(changed_versions[:5])
    return md_code(f"{head} (+{len(changed_versions) - 5} more)")


def lifecycle_counts(spec: OpenApiSpecLifecycle) -> dict[str, int]:
    return {
        "total": len(spec.entity_lifecycle),
        "changed": sum(1 for record in spec.entity_lifecycle if record.changed_in_versions),
        "removed": sum(1 for record in spec.entity_lifecycle if record.removed_version),
        "introduced_later": sum(
            1 for record in spec.entity_lifecycle if record.introduced_version != spec.introduced_version
        ),
    }


def interesting_entities(spec: OpenApiSpecLifecycle) -> list[OpenApiEntityLifecycle]:
    rows = [
        record
        for record in spec.entity_lifecycle
        if record.introduced_version != spec.introduced_version
        or record.changed_in_versions
        or record.removed_version
    ]
    rows.sort(key=lambda record: (record.entity_type, record.name))
    return rows


def endpoint_header(operation: dict[str, Any]) -> str:
    method = str(operation.get("method", "")).strip()
    path = str(operation.get("path", "")).strip()
    return md_code(f"{method} {path}".strip())


def render_endpoint_reference(operations: list[dict[str, Any]], max_endpoints: int) -> str:
    lines: list[str] = []
    if not operations:
        return "No endpoint details available in the latest spec."

    shown = operations[:max_endpoints]
    lines.extend(
        [
            "| Endpoint | Operation ID | Summary | Tags |",
            "| --- | --- | --- | --- |",
        ]
    )
    for operation in shown:
        operation_id = operation.get("operation_id") or "-"
        summary = operation.get("summary") or "-"
        tags = ", ".join(operation.get("tags") or []) or "-"
        lines.append(
            f"| {endpoint_header(operation)} | {md_code(operation_id)} | {md_text(summary)} | {md_code(tags)} |"
        )

    if len(operations) > max_endpoints:
        lines.extend(
            [
                "",
                f"_Showing first {max_endpoints} endpoints out of {len(operations)}._",
            ]
        )
        return "\n".join(lines)

    for operation in shown:
        lines.extend(["", f"### {endpoint_header(operation)}", ""])
        if operation.get("operation_id"):
            lines.append(f"- Operation ID: {md_code(operation['operation_id'])}")
        if operation.get("summary"):
            lines.append(f"- Summary: {md_text(operation['summary'])}")
        if operation.get("description"):
            lines.append(f"- Description: {md_text(operation['description'])}")
        if operation.get("tags"):
            lines.append(f"- Tags: {md_code(', '.join(operation['tags']))}")

        parameters = operation.get("parameters", [])
        if parameters:
            lines.extend(
                [
                    "",
                    "**Parameters**",
                    "",
                    "| Name | In | Required | Schema | Description |",
                    "| --- | --- | --- | --- | --- |",
                ]
            )
            for parameter in parameters:
                lines.append(
                    f"| {md_code(parameter.get('name', '-'))} | {md_code(parameter.get('in', '-'))} | {md_code('yes' if parameter.get('required') else 'no')} | {md_code(parameter.get('schema', '-'))} | {md_text(parameter.get('description', '-') or '-')} |"
                )

        request_body = operation.get("request_body", {})
        if request_body:
            lines.extend(["", "**Request Body**", ""])
            lines.append(f"- Required: {md_code('yes' if request_body.get('required') else 'no')}")
            content_types = request_body.get("content_types", [])
            schema_by_content_type = request_body.get("schema_by_content_type", {})
            if content_types:
                lines.append("- Content:")
                for content_type in content_types:
                    lines.append(f"  - {md_code(content_type)} -> {md_code(schema_by_content_type.get(content_type, '-'))}")
            else:
                lines.append(f"- Content: {md_code('-')}")

        responses = operation.get("responses", [])
        if responses:
            lines.extend(
                [
                    "",
                    "**Responses**",
                    "",
                    "| Code | Description | Content Types | Schemas |",
                    "| --- | --- | --- | --- |",
                ]
            )
            for response in responses:
                content_types = response.get("content_types", [])
                schema_by_content_type = response.get("schema_by_content_type", {})
                content_value = ", ".join(content_types) if content_types else "-"
                schema_value = (
                    ", ".join(f"{content_type}:{schema_by_content_type.get(content_type, '-')}" for content_type in content_types)
                    if content_types
                    else "-"
                )
                lines.append(
                    f"| {md_code(response.get('code', '-'))} | {md_text(response.get('description', '-') or '-')} | {md_code(content_value)} | {md_code(schema_value)} |"
                )

    return "\n".join(lines)


def build_spec_page(spec: OpenApiSpecLifecycle, spec_dir_name: str) -> Page:
    counts = lifecycle_counts(spec)
    interesting = interesting_entities(spec)
    latest_operations = spec.latest_entities.get("operations", [])
    latest_components = spec.latest_entities.get("components", [])
    latest_paths = spec.latest_entities.get("paths", [])
    latest_tags = spec.latest_entities.get("tags", [])

    blocks = [
        Paragraph("Generated from supplied versioned OpenAPI artifacts."),
        Heading(level=2, text="Spec Metadata"),
        BulletList(
            items=[
                f"Canonical spec id: {md_code(spec.spec_id)}",
                f"Latest source path: {md_code(spec.latest_source_path)}",
                f"OpenAPI version (latest): {md_code(spec.latest_openapi_version or '-')}",
                f"Introduced: {lifecycle_value(spec.introduced_version, 'introduced')}",
                f"Changed in versions: {changed_versions_value(spec.changed_in_versions)}",
                f"Removed: {lifecycle_value(spec.removed_version, 'removed')}",
            ]
        ),
        Heading(level=2, text="Entity Summary"),
        BulletList(
            items=[
                f"Total entities tracked: {md_code(counts['total'])}",
                f"Entities introduced after spec introduction: {md_code(counts['introduced_later'])}",
                f"Entities changed at least once: {md_code(counts['changed'])}",
                f"Entities removed: {md_code(counts['removed'])}",
                f"Latest operations: {md_code(len(latest_operations))}",
                f"Latest paths: {md_code(len(latest_paths))}",
                f"Latest components: {md_code(len(latest_components))}",
                f"Latest tags: {md_code(len(latest_tags))}",
            ]
        ),
        Heading(level=2, text="Endpoint Reference (Latest)"),
        RawMarkdown(render_endpoint_reference(spec.latest_operation_details, MAX_ENDPOINTS)),
        Heading(level=2, text="Version Change Timeline"),
        Table(
            headers=["Version", "Added", "Changed", "Removed"],
            rows=[
                [
                    md_code(version),
                    md_code(spec.per_version_entity_deltas.get(version, {}).get("added_count", 0)),
                    md_code(spec.per_version_entity_deltas.get(version, {}).get("changed_count", 0)),
                    md_code(spec.per_version_entity_deltas.get(version, {}).get("removed_count", 0)),
                ]
                for version in spec.versions_present
            ],
        ),
        Heading(level=2, text="Changed Entities"),
    ]

    if not interesting:
        blocks.append(Paragraph("No entity-level lifecycle changes in the selected version range."))
    else:
        blocks.append(
            Table(
                headers=["Entity", "Type", "Introduced", "Changed In", "Removed"],
                rows=[
                    [
                        md_code(record.name),
                        md_code(record.entity_type),
                        lifecycle_value(record.introduced_version, "introduced"),
                        changed_versions_value(record.changed_in_versions),
                        lifecycle_value(record.removed_version, "removed"),
                    ]
                    for record in interesting[:MAX_CHANGED_ENTITIES]
                ],
            )
        )
        if len(interesting) > MAX_CHANGED_ENTITIES:
            blocks.append(
                Paragraph(
                    f"_Showing first {MAX_CHANGED_ENTITIES} rows out of {len(interesting)} changed entities._"
                )
            )

    blocks.append(Heading(level=2, text="Latest Operations"))
    if not latest_operations:
        blocks.append(Paragraph("No operations in latest version."))
    else:
        blocks.append(
            Table(
                headers=["Operation", "Introduced", "Changed In", "Removed"],
                rows=[
                    [
                        md_code(str(record.get("name", ""))),
                        lifecycle_value(str(record.get("introduced_version", "")), "introduced"),
                        changed_versions_value(list(record.get("changed_in_versions", []))),
                        lifecycle_value(record.get("removed_version"), "removed"),
                    ]
                    for record in latest_operations[:MAX_LATEST_OPERATIONS]
                ],
            )
        )
        if len(latest_operations) > MAX_LATEST_OPERATIONS:
            blocks.append(
                Paragraph(
                    f"_Showing first {MAX_LATEST_OPERATIONS} operations out of {len(latest_operations)}._"
                )
            )

    blocks.append(Heading(level=2, text="Latest Components"))
    if not latest_components:
        blocks.append(Paragraph("No components in latest version."))
    else:
        blocks.append(
            Table(
                headers=["Component", "Introduced", "Changed In", "Removed"],
                rows=[
                    [
                        md_code(str(record.get("name", ""))),
                        lifecycle_value(str(record.get("introduced_version", "")), "introduced"),
                        changed_versions_value(list(record.get("changed_in_versions", []))),
                        lifecycle_value(record.get("removed_version"), "removed"),
                    ]
                    for record in latest_components[:MAX_LATEST_COMPONENTS]
                ],
            )
        )
        if len(latest_components) > MAX_LATEST_COMPONENTS:
            blocks.append(
                Paragraph(
                    f"_Showing first {MAX_LATEST_COMPONENTS} components out of {len(latest_components)}._"
                )
            )

    return Page(
        path=f"{spec_dir_name}/{slugify(spec.spec_id)}.mdx",
        title=spec.display_name,
        description="Generated lifecycle view for an OpenAPI specification",
        blocks=blocks,
    )


def build_overview_page(
    report: OpenApiLifecycleReport,
    spec_pages: list[Page],
    overview_name: str,
) -> Page:
    spec_page_map = {
        spec.spec_id: page
        for spec, page in zip(sorted(report.specs, key=lambda item: item.spec_id), spec_pages)
    }
    rows = []
    for spec in sorted(report.specs, key=lambda item: item.spec_id):
        page = spec_page_map[spec.spec_id]
        spec_dir_link = f"./{page.path[:-4]}"
        rows.append(
            [
                f"[Open]({spec_dir_link})",
                md_code(spec.spec_id),
                lifecycle_value(spec.introduced_version, "introduced"),
                md_code(spec.latest_version),
                lifecycle_value(spec.removed_version, "removed"),
                changed_versions_value(spec.changed_in_versions),
                md_code(spec.entity_count),
            ]
        )

    return Page(
        path=overview_name,
        title="OpenAPI Lifecycle Overview",
        description="Generated OpenAPI lifecycle reference",
        blocks=[
            Paragraph("This section is generated from supplied versioned OpenAPI artifacts."),
            BulletList(
                items=[
                    f"Generated at (UTC): {md_code(report.generated_at_utc)}",
                    f"Source: {md_code(report.source_name)}",
                    f"Tag filter: {md_code(report.tag_filter)}",
                ]
            ),
            Heading(level=2, text="Summary"),
            BulletList(
                items=[
                    f"Tags scanned: {md_code(report.summary.get('tag_count', 0))}",
                    f"Specs discovered: {md_code(report.summary.get('spec_count', 0))}",
                    f"Total entities tracked: {md_code(report.summary.get('total_entities', 0))}",
                    f"Total entity change events: {md_code(report.summary.get('total_entity_change_events', 0))}",
                ]
            ),
            Heading(level=2, text="Specs"),
            Table(
                headers=["Page", "Spec", "Introduced", "Latest", "Removed", "Changed In Versions", "Entities"],
                rows=rows,
            ),
        ],
    )


def build_pages(report: OpenApiLifecycleReport, overview_name: str = "overview.mdx", spec_dir_name: str = "specs") -> list[Page]:
    spec_pages = [build_spec_page(spec, spec_dir_name) for spec in sorted(report.specs, key=lambda item: item.spec_id)]
    overview_page = build_overview_page(report, spec_pages, overview_name)
    return [overview_page, *spec_pages]


def build_api_page(report: OpenApiLifecycleReport, output_path: str) -> Page:
    specs = sorted(report.specs, key=lambda item: item.spec_id)
    if len(specs) != 1:
        raise ValueError(f"Expected exactly one spec for single-page output, found {len(specs)}")

    spec_page = build_spec_page(specs[0], "specs")
    return Page(
        path=output_path,
        title=spec_page.title,
        description="Generated API reference from versioned OpenAPI artifacts",
        blocks=spec_page.blocks,
    )


def build_preview_pages(
    report: OpenApiLifecycleReport,
    overview_name: str = "overview.mdx",
    spec_dir_name: str = "specs",
) -> list[Page]:
    content_pages = build_pages(report, overview_name=overview_name, spec_dir_name=spec_dir_name)
    landing_page = Page(
        path="index.mdx",
        title="OpenAPI Preview",
        description="Mintlify preview for generated OpenAPI MDX output",
        blocks=[
            Paragraph("This preview site is generated by `x2mdx`."),
            BulletList(
                items=[
                    "Use the overview page for the lifecycle summary.",
                    "Use the spec pages for per-spec entity and endpoint details.",
                ]
            ),
            Heading(level=2, text="Quick Links"),
            BulletList(
                items=[
                    f"[Overview](./{overview_name[:-4]})",
                    f"[Specs](./{spec_dir_name}/{slugify(report.specs[0].spec_id)})" if report.specs else "No specs generated.",
                ]
            ),
        ],
    )
    return [landing_page, *content_pages]


def build_preview_groups(
    report: OpenApiLifecycleReport,
    overview_name: str = "overview.mdx",
    spec_dir_name: str = "specs",
) -> list[MintlifyGroup]:
    spec_refs = [
        f"{spec_dir_name}/{slugify(spec.spec_id)}"
        for spec in sorted(report.specs, key=lambda item: item.spec_id)
    ]
    return [
        MintlifyGroup(
            group="Preview",
            pages=[
                "index",
                overview_name[:-4],
                MintlifyGroup(group="Specs", pages=spec_refs, expanded=True),
            ],
            expanded=True,
        )
    ]
