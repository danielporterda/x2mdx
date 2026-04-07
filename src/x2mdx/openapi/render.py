"""Render OpenAPI lifecycle reports into shared output-side page models."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from x2mdx.mintlify import MintlifyGroup
from x2mdx.openapi.models import OpenApiEntityLifecycle, OpenApiLifecycleReport, OpenApiSpecLifecycle
from x2mdx.output import Page, RawMarkdown
from x2mdx.templating import markdown_page, render_template

MAX_CHANGED_ENTITIES = 300
MAX_LATEST_OPERATIONS = 300
MAX_LATEST_COMPONENTS = 400
MAX_ENDPOINTS = 200
MAX_TABLE_OF_CONTENTS_ROWS = 300


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


def compact_change_summary(changes: list[str], *, max_items: int = 6) -> str:
    if not changes:
        return "-"
    if len(changes) <= max_items:
        return "; ".join(changes)
    shown = "; ".join(changes[:max_items])
    return f"{shown}; +{len(changes) - max_items} more"


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


def parameter_key(parameter: dict[str, Any]) -> tuple[str, str]:
    return (
        str(parameter.get("in", "") or ""),
        str(parameter.get("name", "") or ""),
    )


def parameter_label(parameter: dict[str, Any]) -> str:
    location, name = parameter_key(parameter)
    if location and name:
        return f"{location} param {md_code(name)}"
    return f"param {md_code(name or '-')}"


def response_map(responses: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(response.get("code", "")): response for response in responses}


def schema_map_changes(prefix: str, previous: dict[str, str], current: dict[str, str]) -> list[str]:
    changes: list[str] = []
    previous_keys = set(previous)
    current_keys = set(current)
    for content_type in sorted(current_keys - previous_keys):
        changes.append(f"{prefix} content {md_code(content_type)} added")
    for content_type in sorted(previous_keys - current_keys):
        changes.append(f"{prefix} content {md_code(content_type)} removed")
    for content_type in sorted(previous_keys & current_keys):
        if previous[content_type] != current[content_type]:
            changes.append(
                f"{prefix} schema {md_code(content_type)} changed {md_code(previous[content_type])} -> {md_code(current[content_type])}"
            )
    return changes


def summarize_operation_transition(previous: dict[str, Any] | None, current: dict[str, Any] | None) -> list[str]:
    if previous is None and current is None:
        return []
    if previous is None:
        return ["added endpoint"]
    if current is None:
        return ["removed endpoint"]

    changes: list[str] = []
    if (previous.get("operation_id") or "") != (current.get("operation_id") or ""):
        changes.append(
            f"operation id changed {md_code(previous.get('operation_id') or '-')} -> {md_code(current.get('operation_id') or '-')}"
        )
    if (previous.get("summary") or "") != (current.get("summary") or ""):
        changes.append(f"summary changed {md_code(previous.get('summary') or '-')} -> {md_code(current.get('summary') or '-')}")
    if (previous.get("description") or "") != (current.get("description") or ""):
        changes.append("description updated")

    previous_tags = set(str(tag) for tag in previous.get("tags", []))
    current_tags = set(str(tag) for tag in current.get("tags", []))
    for tag in sorted(current_tags - previous_tags):
        changes.append(f"tag {md_code(tag)} added")
    for tag in sorted(previous_tags - current_tags):
        changes.append(f"tag {md_code(tag)} removed")

    previous_parameters = {parameter_key(param): param for param in previous.get("parameters", [])}
    current_parameters = {parameter_key(param): param for param in current.get("parameters", [])}
    for key in sorted(current_parameters.keys() - previous_parameters.keys()):
        changes.append(f"{parameter_label(current_parameters[key])} added")
    for key in sorted(previous_parameters.keys() - current_parameters.keys()):
        changes.append(f"{parameter_label(previous_parameters[key])} removed")
    for key in sorted(previous_parameters.keys() & current_parameters.keys()):
        previous_param = previous_parameters[key]
        current_param = current_parameters[key]
        field_changes: list[str] = []
        if bool(previous_param.get("required")) != bool(current_param.get("required")):
            field_changes.append("required")
        if (previous_param.get("schema") or "-") != (current_param.get("schema") or "-"):
            field_changes.append("schema")
        if (previous_param.get("description") or "") != (current_param.get("description") or ""):
            field_changes.append("description")
        if field_changes:
            changes.append(f"{parameter_label(current_param)} changed ({', '.join(field_changes)})")

    previous_request_body = previous.get("request_body") or {}
    current_request_body = current.get("request_body") or {}
    if not previous_request_body and current_request_body:
        changes.append("request body added")
    elif previous_request_body and not current_request_body:
        changes.append("request body removed")
    elif previous_request_body and current_request_body:
        if bool(previous_request_body.get("required")) != bool(current_request_body.get("required")):
            changes.append("request body required flag changed")
        changes.extend(
            schema_map_changes(
                "request body",
                {
                    str(content_type): str(schema)
                    for content_type, schema in dict(previous_request_body.get("schema_by_content_type", {})).items()
                },
                {
                    str(content_type): str(schema)
                    for content_type, schema in dict(current_request_body.get("schema_by_content_type", {})).items()
                },
            )
        )

    previous_responses = response_map(previous.get("responses", []))
    current_responses = response_map(current.get("responses", []))
    for code in sorted(current_responses.keys() - previous_responses.keys()):
        changes.append(f"response {md_code(code)} added")
    for code in sorted(previous_responses.keys() - current_responses.keys()):
        changes.append(f"response {md_code(code)} removed")
    for code in sorted(previous_responses.keys() & current_responses.keys()):
        previous_response = previous_responses[code]
        current_response = current_responses[code]
        if (previous_response.get("description") or "") != (current_response.get("description") or ""):
            changes.append(f"response {md_code(code)} description updated")
        changes.extend(
            schema_map_changes(
                f"response {md_code(code)}",
                {
                    str(content_type): str(schema)
                    for content_type, schema in dict(previous_response.get("schema_by_content_type", {})).items()
                },
                {
                    str(content_type): str(schema)
                    for content_type, schema in dict(current_response.get("schema_by_content_type", {})).items()
                },
            )
        )

    return changes


def operation_summary_text(operation: dict[str, Any]) -> str:
    summary = str(operation.get("summary", "") or "").strip()
    if summary:
        return md_text(summary)
    description = str(operation.get("description", "") or "").strip()
    if description:
        return md_text(description)
    return "-"


def operation_change_summary_value(spec: OpenApiSpecLifecycle, lifecycle: OpenApiEntityLifecycle) -> str:
    if not lifecycle.changed_in_versions:
        return "-"

    version_summaries: list[str] = []
    details_by_version = spec.operation_details_by_version
    for changed_version in lifecycle.changed_in_versions:
        index = lifecycle.versions_present.index(changed_version)
        if index == 0:
            continue
        previous_version = lifecycle.versions_present[index - 1]
        previous = details_by_version.get(previous_version, {}).get(lifecycle.entity_key)
        current = details_by_version.get(changed_version, {}).get(lifecycle.entity_key)
        changes = compact_change_summary(summarize_operation_transition(previous, current))
        version_summaries.append(f"{changed_version}: {changes}")

    if not version_summaries:
        return "-"
    if len(version_summaries) <= 3:
        return "; ".join(version_summaries)
    shown = "; ".join(version_summaries[:3])
    return f"{shown}; +{len(version_summaries) - 3} more"


def table_of_contents_rows(spec: OpenApiSpecLifecycle) -> list[list[str]]:
    lifecycle_by_key = {
        record.entity_key: record
        for record in spec.entity_lifecycle
        if record.entity_type == "operation"
    }
    rows: list[list[str]] = []
    for operation in spec.latest_operation_details:
        entity_key = str(operation.get("entity_key", "") or "")
        lifecycle = lifecycle_by_key.get(entity_key)
        if lifecycle is None:
            continue
        rows.append(
            [
                endpoint_anchor_link(endpoint_name(operation)),
                operation_summary_text(operation),
                lifecycle_value(lifecycle.introduced_version, "introduced"),
                operation_change_summary_value(spec, lifecycle),
                "-",
                lifecycle_value(lifecycle.removed_version, "removed"),
            ]
        )
    return rows


def endpoint_header(operation: dict[str, Any]) -> str:
    method = str(operation.get("method", "")).strip()
    path = str(operation.get("path", "")).strip()
    return md_code(f"{method} {path}".strip())


def endpoint_name(operation: dict[str, Any]) -> str:
    method = str(operation.get("method", "")).strip()
    path = str(operation.get("path", "")).strip()
    return f"{method} {path}".strip()


def endpoint_anchor_id(endpoint: str) -> str:
    return f"endpoint-{slugify(endpoint)}"


def endpoint_anchor_link(endpoint: str) -> str:
    return f"[{md_code(endpoint)}](#{endpoint_anchor_id(endpoint)})"


def _endpoint_reference_operation(operation: dict[str, Any]) -> dict[str, Any]:
    endpoint = endpoint_name(operation)
    parameters = operation.get("parameters", [])
    request_body = operation.get("request_body", {})
    responses = operation.get("responses", [])

    request_body_context: dict[str, Any] | None = None
    if request_body:
        content_types = request_body.get("content_types", [])
        schema_by_content_type = request_body.get("schema_by_content_type", {})
        required_fields_by_content_type = request_body.get("required_fields_by_content_type", {})
        sample_by_content_type = request_body.get("sample_by_content_type", {})
        request_body_context = {
            "required": md_code("yes" if request_body.get("required") else "no"),
            "content_rows": [
                [
                    md_code(content_type),
                    md_code(schema_by_content_type.get(content_type, "-")),
                    ", ".join(md_code(field_name) for field_name in required_fields_by_content_type.get(content_type, []))
                    or "-",
                ]
                for content_type in content_types
            ],
            "content": md_code("-"),
            "examples": [
                {
                    "content_type": md_code(content_type),
                    "body": json.dumps(sample_by_content_type[content_type], indent=2),
                }
                for content_type in content_types
                if content_type in sample_by_content_type
            ],
        }

    return {
        "anchor_id": endpoint_anchor_id(endpoint),
        "header": endpoint_header(operation),
        "bullet_items": [
            item
            for item in [
                f"Operation ID: {md_code(operation['operation_id'])}" if operation.get("operation_id") else "",
                f"Summary: {md_text(operation['summary'])}" if operation.get("summary") else "",
                f"Description: {md_text(operation['description'])}" if operation.get("description") else "",
                f"Tags: {md_code(', '.join(operation['tags']))}" if operation.get("tags") else "",
            ]
            if item
        ],
        "parameter_rows": [
            [
                md_code(parameter.get("name", "-")),
                md_code(parameter.get("in", "-")),
                md_code("yes" if parameter.get("required") else "no"),
                md_code(parameter.get("schema", "-")),
                md_text(parameter.get("description", "-") or "-"),
            ]
            for parameter in parameters
        ],
        "request_body": request_body_context,
        "response_rows": [
            [
                md_code(response.get("code", "-")),
                md_text(response.get("description", "-") or "-"),
                md_code(", ".join(response.get("content_types", [])) if response.get("content_types") else "-"),
                md_code(
                    ", ".join(
                        f"{content_type}:{response.get('schema_by_content_type', {}).get(content_type, '-')}"
                        for content_type in response.get("content_types", [])
                    )
                    if response.get("content_types")
                    else "-"
                ),
            ]
            for response in responses
        ],
    }


def render_endpoint_reference(operations: list[dict[str, Any]], max_endpoints: int) -> str:
    if not operations:
        return "No endpoint details available in the latest spec."
    return render_template(
        "openapi/endpoint_reference.md.j2",
        operations=[_endpoint_reference_operation(operation) for operation in operations[:max_endpoints]],
        max_endpoints=max_endpoints,
        total_operations=len(operations),
    )


def build_spec_page(spec: OpenApiSpecLifecycle, spec_dir_name: str) -> Page:
    counts = lifecycle_counts(spec)
    interesting = interesting_entities(spec)
    toc_rows = table_of_contents_rows(spec)
    latest_operations = spec.latest_entities.get("operations", [])
    latest_components = spec.latest_entities.get("components", [])
    latest_paths = spec.latest_entities.get("paths", [])
    latest_tags = spec.latest_entities.get("tags", [])

    body = render_template(
        "openapi/spec.md.j2",
        table_of_contents_rows=toc_rows[:MAX_TABLE_OF_CONTENTS_ROWS],
        table_of_contents_total=len(toc_rows),
        table_of_contents_limit=MAX_TABLE_OF_CONTENTS_ROWS,
        endpoint_reference=render_endpoint_reference(spec.latest_operation_details, MAX_ENDPOINTS),
        version_timeline_rows=[
            [
                md_code(version),
                md_code(spec.per_version_entity_deltas.get(version, {}).get("added_count", 0)),
                md_code(spec.per_version_entity_deltas.get(version, {}).get("changed_count", 0)),
                md_code(spec.per_version_entity_deltas.get(version, {}).get("removed_count", 0)),
            ]
            for version in spec.versions_present
        ],
        interesting_rows=[
            [
                md_code(record.name),
                md_code(record.entity_type),
                lifecycle_value(record.introduced_version, "introduced"),
                changed_versions_value(record.changed_in_versions),
                lifecycle_value(record.removed_version, "removed"),
            ]
            for record in interesting[:MAX_CHANGED_ENTITIES]
        ],
        interesting_total=len(interesting),
        interesting_limit=MAX_CHANGED_ENTITIES,
        latest_operations_rows=[
            [
                md_code(str(record.get("name", ""))),
                lifecycle_value(str(record.get("introduced_version", "")), "introduced"),
                changed_versions_value(list(record.get("changed_in_versions", []))),
                lifecycle_value(record.get("removed_version"), "removed"),
            ]
            for record in latest_operations[:MAX_LATEST_OPERATIONS]
        ],
        latest_operations_total=len(latest_operations),
        latest_operations_limit=MAX_LATEST_OPERATIONS,
        latest_components_rows=[
            [
                md_code(str(record.get("name", ""))),
                lifecycle_value(str(record.get("introduced_version", "")), "introduced"),
                changed_versions_value(list(record.get("changed_in_versions", []))),
                lifecycle_value(record.get("removed_version"), "removed"),
            ]
            for record in latest_components[:MAX_LATEST_COMPONENTS]
        ],
        latest_components_total=len(latest_components),
        latest_components_limit=MAX_LATEST_COMPONENTS,
        spec_metadata_items=[
            f"Canonical spec id: {md_code(spec.spec_id)}",
            f"Latest source path: {md_code(spec.latest_source_path)}",
            f"OpenAPI version (latest): {md_code(spec.latest_openapi_version or '-')}",
            f"Introduced: {lifecycle_value(spec.introduced_version, 'introduced')}",
            f"Changed in versions: {changed_versions_value(spec.changed_in_versions)}",
            f"Removed: {lifecycle_value(spec.removed_version, 'removed')}",
        ],
        entity_summary_items=[
            f"Total entities tracked: {md_code(counts['total'])}",
            f"Entities introduced after spec introduction: {md_code(counts['introduced_later'])}",
            f"Entities changed at least once: {md_code(counts['changed'])}",
            f"Entities removed: {md_code(counts['removed'])}",
            f"Latest operations: {md_code(len(latest_operations))}",
            f"Latest paths: {md_code(len(latest_paths))}",
            f"Latest components: {md_code(len(latest_components))}",
            f"Latest tags: {md_code(len(latest_tags))}",
        ],
    )
    body = body.replace("## Endpoint Reference (Latest)\n\n<a id=", "## Endpoint Reference (Latest)\n\n\n<a id=", 1)
    return Page(
        path=f"{spec_dir_name}/{slugify(spec.spec_id)}.mdx",
        title=spec.display_name,
        description="Generated lifecycle view for an OpenAPI specification",
        blocks=[RawMarkdown(body)],
    )


def build_overview_page(
    report: OpenApiLifecycleReport,
    spec_pages: list[Page],
    overview_name: str,
    overview_title: str,
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

    return markdown_page(
        path=overview_name,
        title=overview_title,
        description="Generated OpenAPI lifecycle reference",
        template_name="openapi/overview.md.j2",
        source_items=[
            f"Generated at (UTC): {md_code(report.generated_at_utc)}",
            f"Source: {md_code(report.source_name)}",
            f"Tag filter: {md_code(report.tag_filter)}",
        ],
        summary_items=[
            f"Tags scanned: {md_code(report.summary.get('tag_count', 0))}",
            f"Specs discovered: {md_code(report.summary.get('spec_count', 0))}",
            f"Total entities tracked: {md_code(report.summary.get('total_entities', 0))}",
            f"Total entity change events: {md_code(report.summary.get('total_entity_change_events', 0))}",
        ],
        rows=rows,
    )


def build_pages(
    report: OpenApiLifecycleReport,
    overview_name: str = "overview.mdx",
    spec_dir_name: str = "specs",
    overview_title: str = "OpenAPI Lifecycle Overview",
) -> list[Page]:
    spec_pages = [build_spec_page(spec, spec_dir_name) for spec in sorted(report.specs, key=lambda item: item.spec_id)]
    overview_page = build_overview_page(report, spec_pages, overview_name, overview_title)
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
    landing_page = markdown_page(
        path="index.mdx",
        title="OpenAPI Preview",
        description="Mintlify preview for generated OpenAPI MDX output",
        template_name="openapi/preview.md.j2",
        notes=[
            "Use the overview page for the lifecycle summary.",
            "Use the spec pages for per-spec entity and endpoint details.",
        ],
        quick_links=[
            f"[Overview](./{overview_name[:-4]})",
            f"[Specs](./{spec_dir_name}/{slugify(report.specs[0].spec_id)})" if report.specs else "No specs generated.",
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
