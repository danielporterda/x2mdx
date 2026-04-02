"""Render OpenRPC reports into overview and per-spec MDX pages."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from x2mdx.openrpc.models import OpenRpcMethodLifecycle, OpenRpcReport, OpenRpcSpecLifecycle
from x2mdx.output import Page, RawMarkdown


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


def render_change_summary(change_details: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for entry in change_details:
        version = str(entry["version"])
        changes = entry["changes"] if isinstance(entry.get("changes"), list) else []
        rendered_changes = "; ".join(str(change) for change in changes) if changes else "details updated"
        parts.append(f"`{version}`: {rendered_changes}")
    return "<br/>".join(parts) if parts else "-"


def spec_page_name(spec: OpenRpcSpecLifecycle) -> str:
    return f"{slugify(spec.spec_id)}.mdx"


def spec_page_link(spec: OpenRpcSpecLifecycle, *, spec_dir_name: str) -> str:
    return f"{spec_dir_name}/{Path(spec_page_name(spec)).with_suffix('').as_posix()}"


def build_overview_page(
    report: OpenRpcReport,
    *,
    overview_name: str,
    spec_dir_name: str,
    overview_title: str,
) -> Page:
    lines = [
        f"# {overview_title}",
        "",
        "Generated from versioned OpenRPC snapshots.",
        "",
        f"- Publish version: `{report.publish_version}`",
        f"- Versions compared: {', '.join(f'`{version}`' for version in report.versions)}",
        f"- Source: `{report.source_name}`",
        f"- Version filter: `{report.version_filter}`",
        f"- Generated at: `{report.generated_at_utc}`",
        "",
        "## Spec Reference",
        "",
        "| Spec | Title | Methods | Changed In |",
        "| --- | --- | --- | --- |",
    ]
    for spec in report.specs:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"[`{escape_md_cell(spec.display_name)}`]({spec_page_link(spec, spec_dir_name=spec_dir_name)})",
                    escape_md_cell(spec.info_title or "-"),
                    md_code(str(len(spec.methods))),
                    ", ".join(md_code(version) for version in spec.changed_in_versions) if spec.changed_in_versions else "-",
                ]
            )
            + " |"
        )

    return Page(
        path=overview_name,
        title=overview_title,
        description="Versioned OpenRPC reference docs.",
        blocks=[RawMarkdown("\n".join(lines))],
    )


def render_param_table(params: list[dict[str, Any]]) -> str:
    if not params:
        return "_No parameters._"
    lines = [
        "| Parameter | Schema | Required Fields | Description |",
        "| --- | --- | --- | --- |",
    ]
    for param in params:
        lines.append(
            "| "
            + " | ".join(
                [
                    md_code(param["name"]),
                    md_code(param["schema"]),
                    ", ".join(md_code(field) for field in param["required_fields"]) if param["required_fields"] else "-",
                    escape_md_cell(param["description"]) if param["description"] else "-",
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def render_result_table(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "| Schema | Required Fields | Description |",
            "| --- | --- | --- |",
            "| "
            + " | ".join(
                [
                    md_code(result["schema"]),
                    ", ".join(md_code(field) for field in result["required_fields"]) if result["required_fields"] else "-",
                    escape_md_cell(result["description"]) if result["description"] else "-",
                ]
            )
            + " |",
        ]
    )


def build_spec_page(
    spec: OpenRpcSpecLifecycle,
    *,
    overview_name: str,
    spec_dir_name: str,
) -> Page:
    lines = [
        f"# {spec.display_name}",
        "",
        f"[Back to overview](../{Path(overview_name).with_suffix('').as_posix()})",
        "",
    ]
    if spec.info_description:
        lines.extend([spec.info_description, ""])
    lines.extend(
        [
            f"- Latest source path: `{spec.latest_source_path}`",
            f"- Publish version: `{spec.latest_version}`",
            f"- OpenRPC version: `{spec.openrpc_version or '-'}`",
            f"- Spec info.version: `{spec.info_version or '-'}`",
            "",
            "## Version Change Timeline",
            "",
            "| Version | Active Methods | Added | Changed | Removed |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for version in spec.versions_present:
        delta = spec.per_version_method_deltas[version]
        lines.append(
            "| "
            + " | ".join(
                [
                    md_code(version),
                    str(delta["active_count"]),
                    str(delta["added_count"]),
                    str(delta["changed_count"]),
                    str(delta["removed_count"]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Method Diff Summary",
            "",
            "| Method | Introduced | Changes | Removed |",
            "| --- | --- | --- | --- |",
        ]
    )
    for method in spec.methods:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"[{md_code(method.method)}](#{method.anchor})",
                    md_code(method.introduced_version),
                    escape_md_cell(render_change_summary(method.change_details)),
                    md_code(method.removed_version) if method.removed_version else "-",
                ]
            )
            + " |"
        )

    lines.extend(["", "## Methods"])
    for method in spec.methods:
        latest = method.latest
        lines.extend(
            [
                "",
                f'<a id="{method.anchor}"></a>',
                f"### `{method.method}`",
                "",
                f"- Introduced: `{method.introduced_version}`",
            ]
        )
        if method.change_details:
            lines.append("Changed in: " + ", ".join(md_code(entry["version"]) for entry in method.change_details))
        if method.removed_version:
            lines.append(f"Removed in: `{method.removed_version}`")
            lines.append("Shown for historical reference.")
        if latest["summary"]:
            lines.extend(["", latest["summary"]])
        if latest["description"]:
            lines.extend(["", latest["description"]])

        if method.change_details:
            lines.extend(
                [
                    "",
                    "**Version Changes**",
                    "",
                    "| Version | Changes |",
                    "| --- | --- |",
                ]
            )
            for entry in method.change_details:
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            md_code(entry["version"]),
                            escape_md_cell("; ".join(str(change) for change in entry["changes"])),
                        ]
                    )
                    + " |"
                )

        lines.extend(
            [
                "",
                "**Parameters**",
                "",
                render_param_table(latest["params"]),
                "",
                "**Result**",
                "",
                render_result_table(latest["result"]),
            ]
        )

        param_samples = {param["name"]: param["sample"] for param in latest["params"] if param["sample"] is not None}
        if param_samples:
            lines.extend(
                [
                    "",
                    "**Params Example**",
                    "",
                    f"```json\n{json.dumps(param_samples, indent=2)}\n```",
                ]
            )
        if latest["result"]["sample"] is not None:
            lines.extend(
                [
                    "",
                    "**Result Example**",
                    "",
                    f"```json\n{json.dumps(latest['result']['sample'], indent=2)}\n```",
                ]
            )

    return Page(
        path=f"{spec_dir_name}/{Path(spec_page_name(spec)).as_posix()}",
        title=spec.display_name,
        description=spec.info_title or "OpenRPC reference page.",
        blocks=[RawMarkdown("\n".join(lines).rstrip())],
    )


def build_pages(
    report: OpenRpcReport,
    *,
    output_dir: Path,
    overview_name: str = "index.mdx",
    spec_dir_name: str = "specs",
    overview_title: str = "Wallet Gateway OpenRPC",
) -> tuple[Path, list[Page]]:
    pages = [build_overview_page(report, overview_name=overview_name, spec_dir_name=spec_dir_name, overview_title=overview_title)]
    pages.extend(
        build_spec_page(spec, overview_name=overview_name, spec_dir_name=spec_dir_name)
        for spec in report.specs
    )
    return output_dir, pages
