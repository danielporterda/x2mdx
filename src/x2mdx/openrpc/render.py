"""Render OpenRPC reports into overview and per-spec MDX pages."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from x2mdx.openrpc.models import OpenRpcMethodLifecycle, OpenRpcReport, OpenRpcSpecLifecycle
from x2mdx.output import Page
from x2mdx.templating import markdown_page, render_status_cell, render_status_legend


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


def build_overview_page(
    report: OpenRpcReport,
    *,
    overview_name: str,
    spec_dir_name: str,
    overview_title: str,
    link_prefix: str | None = None,
) -> Page:
    normalized_link_prefix = normalize_link_prefix(link_prefix) if link_prefix else None
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
        spec_summary_legend=render_status_legend(include_deprecated=False),
        spec_rows=[
            [
                f"[`{escape_md_cell(spec.display_name)}`]("
                + (
                    f"{normalized_link_prefix}/{spec_page_link(spec, spec_dir_name=spec_dir_name)}"
                    if normalized_link_prefix
                    else spec_page_link(spec, spec_dir_name=spec_dir_name)
                )
                + ")",
                render_status_cell(
                    introduced=spec.introduced_version,
                    changed=spec.changed_in_versions,
                    removed=spec.removed_version,
                ),
                spec_summary_text(spec),
            ]
            for spec in report.specs
        ],
    )


def _method_context(method: OpenRpcMethodLifecycle) -> dict[str, Any]:
    latest = method.latest
    lifecycle_lines = [f"- Introduced: `{method.introduced_version}`"]
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
        method_summary_legend=render_status_legend(include_deprecated=False),
        method_summary_rows=[
            [
                f"[{md_code(method.method)}](#{method.anchor})",
                render_status_cell(
                    introduced=method.introduced_version,
                    changed=[entry["version"] for entry in method.change_details],
                    removed=method.removed_version,
                ),
                method_summary_text(method),
            ]
            for method in spec.methods
        ],
        methods=[_method_context(method) for method in spec.methods],
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
