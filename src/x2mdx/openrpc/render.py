"""Render OpenRPC reports into overview and per-spec MDX pages."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from x2mdx.openrpc.models import OpenRpcMethodLifecycle, OpenRpcReport, OpenRpcSpecLifecycle
from x2mdx.output import Page
from x2mdx.presentation import (
    CollectionPageModel,
    DetailCodeBlock,
    DetailTable,
    LifecycleStatus,
    ProtocolSubject,
    StatusRow,
    VersionDeltaRow,
    status_legend_items,
    status_row_context,
    version_delta_row_cells,
)
from x2mdx.templating import markdown_page


def slugify(value: str) -> str:
    output = value.lower()
    output = re.sub(r"[^a-z0-9]+", "-", output)
    output = re.sub(r"-{2,}", "-", output).strip("-")
    return output


def escape_md_cell(text: str) -> str:
    return str(text).replace("|", r"\|").replace("\n", "<br/>")


def md_code(text: Any) -> str:
    output = str(text).replace("`", "\\`").replace("|", "\\|").replace("\n", " ").strip()
    return f"`{output}`"


def spec_page_name(spec: OpenRpcSpecLifecycle) -> str:
    return f"{slugify(spec.spec_id)}.mdx"


def spec_page_link(spec: OpenRpcSpecLifecycle, *, spec_dir_name: str) -> str:
    return f"{spec_dir_name}/{Path(spec_page_name(spec)).with_suffix('').as_posix()}"


def normalize_link_prefix(link_prefix: str) -> str:
    trimmed = link_prefix.strip()
    if not trimmed:
        raise ValueError("link_prefix must not be empty")
    if trimmed == "/":
        return ""
    return "/" + trimmed.strip("/")


def spec_summary_text(spec: OpenRpcSpecLifecycle) -> str:
    parts: list[str] = []
    if spec.info_title and spec.info_title != spec.display_name:
        parts.append(str(spec.info_title))
    parts.append(f"{len(spec.methods)} methods")
    return escape_md_cell(". ".join(parts))


def method_summary_text(method: OpenRpcMethodLifecycle) -> str:
    summary = str(method.latest.get("summary") or "").strip()
    if summary:
        return escape_md_cell(summary)
    description = str(method.latest.get("description") or "").strip()
    if description:
        return escape_md_cell(description)
    return "-"


def build_overview_page_legacy(
    report: OpenRpcReport,
    *,
    overview_name: str,
    spec_dir_name: str,
    overview_title: str,
    link_prefix: str | None = None,
) -> Page:
    normalized_link_prefix = normalize_link_prefix(link_prefix) if link_prefix else None
    status_rows = tuple(
        StatusRow(
            link=f"[`{escape_md_cell(spec.display_name)}`]("
            + (
                f"{normalized_link_prefix}/{spec_page_link(spec, spec_dir_name=spec_dir_name)}"
                if normalized_link_prefix
                else spec_page_link(spec, spec_dir_name=spec_dir_name)
            )
            + ")",
            summary=spec_summary_text(spec),
            lifecycle=LifecycleStatus.from_values(
                introduced=spec.introduced_version,
                changed_versions=spec.changed_in_versions,
                removed=spec.removed_version,
            ),
        )
        for spec in report.specs
    )
    return markdown_page(
        path=overview_name,
        title=overview_title,
        description="Versioned OpenRPC reference docs.",
        template_name="openrpc/overview.md.j2",
        overview_title=overview_title,
        overview_items=[
            f"Publish version: `{report.publish_version}`",
            f"Versions compared: {', '.join(f'`{version}`' for version in report.versions)}",
            f"Source: `{report.source_name}`",
            f"Version filter: `{report.version_filter}`",
            f"Generated at: `{report.generated_at_utc}`",
        ],
        spec_summary_legend=status_legend_items(status_rows),
        spec_rows=[status_row_context(row) for row in status_rows],
    )


def build_overview_page(
    report: OpenRpcReport,
    *,
    overview_name: str,
    spec_dir_name: str,
    overview_title: str,
    link_prefix: str | None = None,
) -> Page:
    normalized_link_prefix = normalize_link_prefix(link_prefix) if link_prefix else None
    page_model = CollectionPageModel(
        path=overview_name,
        title=overview_title,
        description="Versioned OpenRPC reference docs.",
        metadata_items=(
            f"Publish version: `{report.publish_version}`",
            f"Versions compared: {', '.join(f'`{version}`' for version in report.versions)}",
            f"Source: `{report.source_name}`",
            f"Version filter: `{report.version_filter}`",
            f"Generated at: `{report.generated_at_utc}`",
        ),
        status_rows=tuple(
            StatusRow(
                link=f"[`{escape_md_cell(spec.display_name)}`]("
                + (
                    f"{normalized_link_prefix}/{spec_page_link(spec, spec_dir_name=spec_dir_name)}"
                    if normalized_link_prefix
                    else spec_page_link(spec, spec_dir_name=spec_dir_name)
                )
                + ")",
                summary=spec_summary_text(spec),
                lifecycle=LifecycleStatus.from_values(
                    introduced=spec.introduced_version,
                    changed_versions=spec.changed_in_versions,
                    removed=spec.removed_version,
                ),
            )
            for spec in report.specs
        ),
    )
    return markdown_page(
        path=page_model.path,
        title=page_model.title,
        description=page_model.description,
        template_name="openrpc/overview.md.j2",
        overview_title=page_model.title,
        overview_items=list(page_model.metadata_items),
        spec_summary_legend=status_legend_items(page_model.status_rows),
        spec_rows=[status_row_context(row) for row in page_model.status_rows],
    )


def _method_context_legacy(method: OpenRpcMethodLifecycle) -> dict[str, Any]:
    latest = method.latest
    lifecycle_lines: list[str] = []
    if latest.get("state"):
        lifecycle_lines.append(f"- Lifecycle state: {md_code(latest['state'])}")
    if latest.get("replaces"):
        lifecycle_lines.append(f"- Replaces: {md_code(latest['replaces'])}")
    lifecycle_lines.append(f"- Introduced: `{method.introduced_version}`")
    if method.change_details:
        lifecycle_lines.append("Changed in: " + ", ".join(md_code(entry["version"]) for entry in method.change_details))
    if method.removed_version:
        lifecycle_lines.append(f"Removed in: `{method.removed_version}`")
        lifecycle_lines.append("Shown for historical reference.")

    param_samples = {param["name"]: param["sample"] for param in latest["params"] if param["sample"] is not None}
    return {
        "anchor": method.anchor,
        "heading_text": md_code(method.method),
        "lifecycle_text": "\n".join(lifecycle_lines),
        "summary": latest["summary"],
        "description": latest["description"],
        "change_rows": [
            [
                md_code(entry["version"]),
                escape_md_cell("; ".join(str(change) for change in entry["changes"])),
            ]
            for entry in method.change_details
        ],
        "parameter_rows": [
            [
                md_code(param["name"]),
                md_code(param["schema"]),
                ", ".join(md_code(field) for field in param["required_fields"]) if param["required_fields"] else "-",
                escape_md_cell(param["description"]) if param["description"] else "-",
            ]
            for param in latest["params"]
        ],
        "result_row": [
            md_code(latest["result"]["schema"]),
            ", ".join(md_code(field) for field in latest["result"]["required_fields"])
            if latest["result"]["required_fields"]
            else "-",
            escape_md_cell(latest["result"]["description"]) if latest["result"]["description"] else "-",
        ],
        "param_sample": param_samples or None,
        "result_sample": latest["result"]["sample"],
    }


def _method_subject(method: OpenRpcMethodLifecycle) -> ProtocolSubject:
    latest = method.latest
    lifecycle_items: list[str] = []
    if latest.get("state"):
        lifecycle_items.append(f"- Lifecycle state: {md_code(latest['state'])}")
    if latest.get("replaces"):
        lifecycle_items.append(f"- Replaces: {md_code(latest['replaces'])}")
    lifecycle_items.append(f"- Introduced: `{method.introduced_version}`")
    if method.change_details:
        lifecycle_items.append("Changed in: " + ", ".join(md_code(entry["version"]) for entry in method.change_details))
    if method.removed_version:
        lifecycle_items.append(f"Removed in: `{method.removed_version}`")
        lifecycle_items.append("Shown for historical reference.")

    parameter_rows = tuple(
        (
            md_code(param["name"]),
            md_code(param["schema"]),
            ", ".join(md_code(field) for field in param["required_fields"]) if param["required_fields"] else "-",
            escape_md_cell(param["description"]) if param["description"] else "-",
        )
        for param in latest["params"]
    )
    result_row = (
        md_code(latest["result"]["schema"]),
        ", ".join(md_code(field) for field in latest["result"]["required_fields"])
        if latest["result"]["required_fields"]
        else "-",
        escape_md_cell(latest["result"]["description"]) if latest["result"]["description"] else "-",
    )
    detail_blocks: list[DetailTable | DetailCodeBlock] = [
        DetailTable(
            title="Parameters",
            headers=("Parameter", "Schema", "Required Fields", "Description"),
            rows=parameter_rows,
            empty_message="_No parameters._",
        ),
        DetailTable(
            title="Result",
            headers=("Schema", "Required Fields", "Description"),
            rows=(result_row,),
        ),
    ]
    param_samples = {param["name"]: param["sample"] for param in latest["params"] if param["sample"] is not None}
    if param_samples:
        detail_blocks.append(
            DetailCodeBlock(
                title="Params Example",
                language="json",
                body=json.dumps(param_samples, indent=2),
            )
        )
    if latest["result"]["sample"] is not None:
        detail_blocks.append(
            DetailCodeBlock(
                title="Result Example",
                language="json",
                body=json.dumps(latest["result"]["sample"], indent=2),
            )
        )
    return ProtocolSubject(
        anchor=method.anchor,
        title=method.method,
        summary=str(latest["summary"] or ""),
        lifecycle=LifecycleStatus.from_values(
            introduced=method.introduced_version,
            changed_versions=[str(entry["version"]) for entry in method.change_details],
            state=str(latest.get("state") or "") or None,
            removed=method.removed_version,
        ),
        lifecycle_items=tuple(lifecycle_items),
        description=str(latest["description"] or ""),
        version_changes=tuple(
            (
                md_code(entry["version"]),
                escape_md_cell("; ".join(str(change) for change in entry["changes"])),
            )
            for entry in method.change_details
        ),
        detail_blocks=tuple(detail_blocks),
    )


def _method_context(method: ProtocolSubject) -> dict[str, Any]:
    parameter_table = next(
        block for block in method.detail_blocks if isinstance(block, DetailTable) and block.title == "Parameters"
    )
    result_table = next(block for block in method.detail_blocks if isinstance(block, DetailTable) and block.title == "Result")
    param_example = next(
        (block for block in method.detail_blocks if isinstance(block, DetailCodeBlock) and block.title == "Params Example"),
        None,
    )
    result_example = next(
        (block for block in method.detail_blocks if isinstance(block, DetailCodeBlock) and block.title == "Result Example"),
        None,
    )
    return {
        "anchor": method.anchor,
        "heading_text": md_code(method.title),
        "lifecycle_text": "\n".join(method.lifecycle_items),
        "summary": None if method.summary == "-" else method.summary,
        "description": method.description,
        "change_rows": [list(row) for row in method.version_changes],
        "parameter_rows": [list(row) for row in parameter_table.rows],
        "result_row": list(result_table.rows[0]),
        "param_sample": None,
        "result_sample": None,
    }


def build_spec_page_legacy(
    spec: OpenRpcSpecLifecycle,
    *,
    overview_name: str,
    spec_dir_name: str,
    link_prefix: str | None = None,
) -> Page:
    normalized_link_prefix = normalize_link_prefix(link_prefix) if link_prefix else None
    overview_link = f"../{Path(overview_name).with_suffix('').as_posix()}"
    if normalized_link_prefix is not None:
        overview_link = normalized_link_prefix or "/"
    status_rows = tuple(
        StatusRow(
            link=f"[{md_code(method.method)}](#{method.anchor})",
            summary=method_summary_text(method),
            lifecycle=LifecycleStatus.from_values(
                introduced=method.introduced_version,
                changed_versions=[str(entry["version"]) for entry in method.change_details],
                state=str(method.latest.get("state") or "") or None,
                removed=method.removed_version,
            ),
        )
        for method in spec.methods
    )
    return markdown_page(
        path=f"{spec_dir_name}/{Path(spec_page_name(spec)).as_posix()}",
        title=spec.display_name,
        description=spec.info_title or "OpenRPC reference page.",
        template_name="openrpc/spec.md.j2",
        spec=spec,
        overview_link=overview_link,
        metadata_items=[
            f"Latest source path: `{spec.latest_source_path}`",
            f"Publish version: `{spec.latest_version}`",
            f"OpenRPC version: `{spec.openrpc_version or '-'}`",
            f"Spec info.version: `{spec.info_version or '-'}`",
        ],
        version_timeline_rows=[
            [
                md_code(version),
                str(spec.per_version_method_deltas[version]["active_count"]),
                str(spec.per_version_method_deltas[version]["added_count"]),
                str(spec.per_version_method_deltas[version]["changed_count"]),
                str(spec.per_version_method_deltas[version]["removed_count"]),
            ]
            for version in spec.versions_present
        ],
        method_summary_legend=status_legend_items(status_rows),
        method_summary_rows=[status_row_context(row) for row in status_rows],
        methods=[_method_context_legacy(method) for method in spec.methods],
    )


def build_spec_page(
    spec: OpenRpcSpecLifecycle,
    *,
    overview_name: str,
    spec_dir_name: str,
    link_prefix: str | None = None,
) -> Page:
    normalized_link_prefix = normalize_link_prefix(link_prefix) if link_prefix else None
    overview_link = f"../{Path(overview_name).with_suffix('').as_posix()}"
    if normalized_link_prefix is not None:
        overview_link = normalized_link_prefix or "/"
    methods = tuple(_method_subject(method) for method in spec.methods)
    page_model = CollectionPageModel(
        path=f"{spec_dir_name}/{Path(spec_page_name(spec)).as_posix()}",
        title=spec.display_name,
        description=spec.info_title or "OpenRPC reference page.",
        metadata_items=(
            f"Latest source path: `{spec.latest_source_path}`",
            f"Publish version: `{spec.latest_version}`",
            f"OpenRPC version: `{spec.openrpc_version or '-'}`",
            f"Spec info.version: `{spec.info_version or '-'}`",
        ),
        status_rows=tuple(
            StatusRow(
                link=f"[{md_code(method.title)}](#{method.anchor})",
                summary=method_summary_text(legacy_method),
                lifecycle=method.lifecycle,
            )
            for method, legacy_method in zip(methods, spec.methods)
        ),
        version_rows=tuple(
            VersionDeltaRow(
                version=version,
                active=str(spec.per_version_method_deltas[version]["active_count"]),
                added=str(spec.per_version_method_deltas[version]["added_count"]),
                changed=str(spec.per_version_method_deltas[version]["changed_count"]),
                removed=str(spec.per_version_method_deltas[version]["removed_count"]),
            )
            for version in spec.versions_present
        ),
    )
    method_contexts: list[dict[str, Any]] = []
    for method in methods:
        context = _method_context(method)
        param_example = next(
            (block for block in method.detail_blocks if isinstance(block, DetailCodeBlock) and block.title == "Params Example"),
            None,
        )
        result_example = next(
            (block for block in method.detail_blocks if isinstance(block, DetailCodeBlock) and block.title == "Result Example"),
            None,
        )
        context["param_sample"] = json.loads(param_example.body) if param_example else None
        context["result_sample"] = json.loads(result_example.body) if result_example else None
        method_contexts.append(context)
    return markdown_page(
        path=page_model.path,
        title=page_model.title,
        description=page_model.description,
        template_name="openrpc/spec.md.j2",
        spec=spec,
        overview_link=overview_link,
        metadata_items=list(page_model.metadata_items),
        version_timeline_rows=[version_delta_row_cells(row, include_active=True) for row in page_model.version_rows],
        method_summary_legend=status_legend_items(page_model.status_rows),
        method_summary_rows=[status_row_context(row) for row in page_model.status_rows],
        methods=method_contexts,
    )


def build_pages(
    report: OpenRpcReport,
    *,
    output_dir: Path,
    overview_name: str = "index.mdx",
    spec_dir_name: str = "specs",
    overview_title: str = "Wallet Gateway OpenRPC",
    link_prefix: str | None = None,
) -> tuple[Path, list[Page]]:
    pages = [
        build_overview_page(
            report,
            overview_name=overview_name,
            spec_dir_name=spec_dir_name,
            overview_title=overview_title,
            link_prefix=link_prefix,
        )
    ]
    pages.extend(
        build_spec_page(
            spec,
            overview_name=overview_name,
            spec_dir_name=spec_dir_name,
            link_prefix=link_prefix,
        )
        for spec in report.specs
    )
    return output_dir, pages


def build_pages_legacy(
    report: OpenRpcReport,
    *,
    output_dir: Path,
    overview_name: str = "index.mdx",
    spec_dir_name: str = "specs",
    overview_title: str = "Wallet Gateway OpenRPC",
    link_prefix: str | None = None,
) -> tuple[Path, list[Page]]:
    pages = [
        build_overview_page_legacy(
            report,
            overview_name=overview_name,
            spec_dir_name=spec_dir_name,
            overview_title=overview_title,
            link_prefix=link_prefix,
        )
    ]
    pages.extend(
        build_spec_page_legacy(
            spec,
            overview_name=overview_name,
            spec_dir_name=spec_dir_name,
            link_prefix=link_prefix,
        )
        for spec in report.specs
    )
    return output_dir, pages
