"""Render descriptor-backed protobuf history reports into MDX pages."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from x2mdx.output import Page, RawMarkdown


def escape_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def escape_md(text: str) -> str:
    return text.replace("|", r"\|")


def escape_md_cell(text: str) -> str:
    return escape_text(escape_md(text)).replace("\n", "<br/>")


def md_link(label: str, url: str | None) -> str:
    return f"[{label}]({url})" if url else label


def render_description(text: str) -> str:
    return escape_text(text.strip()) if text.strip() else "_No description._"


def slugify_segment(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return slug or "item"


def relative_page_link(from_path: Path, to_path: Path) -> str:
    relative = os.path.relpath(to_path.with_suffix(""), start=from_path.parent)
    return Path(relative).as_posix()


def build_endpoint_page_path(output_dir: Path, endpoint: dict[str, Any]) -> Path:
    package_dir = [slugify_segment(part) for part in endpoint["package"].split(".") if part]
    return output_dir.joinpath(
        "endpoints",
        *package_dir,
        slugify_segment(endpoint["service"]),
        slugify_segment(endpoint["name"]),
        "index.mdx",
    )


def build_endpoint_page_map(report: dict[str, Any], *, output_dir: Path) -> dict[str, Path]:
    return {
        entry["id"]: build_endpoint_page_path(output_dir, entry)
        for entry in report["endpointLifecycle"]
    }


def render_message_block(message: dict[str, Any], ctx: dict[str, dict[str, Any]], *, level: int, seen: set[str]) -> list[str]:
    if message["id"] in seen:
        return [f"{'#' * level} Message `{message['id']}`", "", "_Already shown above._"]
    seen.add(message["id"])

    lines = [
        f"{'#' * level} Message `{message['id']}`",
        "",
        f"- Source: {md_link(message['file'], message['sourceUrl'])}",
        f"- Fields: {len(message['fieldIds'])}",
        "",
        render_description(message["description"]),
    ]

    if message["fieldIds"]:
        lines.extend(
            [
                "",
                "| Field | Type | Label | Description |",
                "| --- | --- | --- | --- |",
            ]
        )
        for field_id in message["fieldIds"]:
            field = ctx["fields"][field_id]
            field_type = field["type"]
            if field.get("typeName"):
                field_type = f"`{field['typeName']}`"
            lines.append(
                "| "
                + " | ".join(
                    [
                        escape_md_cell(field["name"]),
                        escape_md_cell(field_type),
                        escape_md_cell(field["label"]),
                        escape_md_cell(field["description"] or ""),
                    ]
                )
                + " |"
            )

    for enum_id in message.get("enumIds", []):
        lines.extend(["", *render_enum_block(ctx["enums"][enum_id], ctx, level=level + 1, seen=seen)])
    for nested_id in message.get("nestedMessageIds", []):
        lines.extend(["", *render_message_block(ctx["messages"][nested_id], ctx, level=level + 1, seen=seen)])
    return lines


def render_enum_block(enum_doc: dict[str, Any], ctx: dict[str, dict[str, Any]], *, level: int, seen: set[str]) -> list[str]:
    if enum_doc["id"] in seen:
        return [f"{'#' * level} Enum `{enum_doc['id']}`", "", "_Already shown above._"]
    seen.add(enum_doc["id"])

    lines = [
        f"{'#' * level} Enum `{enum_doc['id']}`",
        "",
        f"- Source: {md_link(enum_doc['file'], enum_doc['sourceUrl'])}",
        "",
        render_description(enum_doc["description"]),
        "",
        "| Name | Number |",
        "| --- | --- |",
    ]
    for value_id in enum_doc["valueIds"]:
        value = ctx["enumValues"][value_id]
        lines.append(f"| {escape_md_cell(value['name'])} | `{value['number']}` |")
    return lines


def render_type_section(type_name: str, ctx: dict[str, dict[str, Any]], *, level: int) -> list[str]:
    if type_name in ctx["messages"]:
        return render_message_block(ctx["messages"][type_name], ctx, level=level, seen=set())
    if type_name in ctx["enums"]:
        return render_enum_block(ctx["enums"][type_name], ctx, level=level, seen=set())
    return [f"{'#' * level} Type `{type_name}`", "", "_Type details unavailable in latest snapshot._"]


def render_endpoint_signature(endpoint: dict[str, Any]) -> str:
    request_prefix = "stream " if endpoint["clientStreaming"] else ""
    response_prefix = "stream " if endpoint["serverStreaming"] else ""
    return (
        f"{endpoint['service']}.{endpoint['name']}("
        f"{request_prefix}{endpoint['requestType']}) returns "
        f"({response_prefix}{endpoint['responseType']})"
    )


def render_history_table(lifecycle_entry: dict[str, Any]) -> str:
    lines = [
        "| Version | Kind | Details |",
        "| --- | --- | --- |",
    ]
    for event in lifecycle_entry.get("history", []):
        details = ", ".join(event.get("changeTypes", []))
        lines.append(
            f"| `{escape_md_cell(event['version'])}` | `{escape_md_cell(event['kind'])}` | {escape_md_cell(details)} |"
        )
    return "\n".join(lines)


def build_pages(report: dict[str, Any], *, output_dir: Path) -> tuple[Path, list[Page]]:
    root = output_dir.parent
    pages: list[Page] = []
    latest = report["latestSnapshot"]
    ctx = {
        "files": latest["files"],
        "services": latest["services"],
        "endpoints": latest["endpoints"],
        "messages": latest["messages"],
        "fields": latest["fields"],
        "enums": latest["enums"],
        "enumValues": latest["enumValues"],
    }
    endpoint_page_map = build_endpoint_page_map(report, output_dir=output_dir)
    overview_path = output_dir / "index.mdx"

    lifecycle_rows = [
        "| Endpoint | Introduced | Last Changed | Removed | Status | Source |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for entry in report["endpointLifecycle"]:
        page_path = endpoint_page_map[entry["id"]]
        link = relative_page_link(overview_path, page_path)
        lifecycle_rows.append(
            "| "
            + " | ".join(
                [
                    f"[`{escape_md(entry['id'])}`]({link})",
                    f"`{entry['introducedIn']}`",
                    f"`{entry['lastChangedIn']}`",
                    f"`{entry['removedIn'] or ''}`",
                    "current" if entry["current"] else "removed",
                    md_link("file", entry.get("sourceUrl")),
                ]
            )
            + " |"
        )

    release_rows = [
        "| Version | Endpoints +/~/- | Messages +/~/- | Enums +/~/- | Files +/~/- |",
        "| --- | --- | --- | --- | --- |",
    ]
    for release in report["releases"]:
        counts = release["changes"]["counts"]
        release_rows.append(
            "| "
            + " | ".join(
                [
                    f"`{release['version']}`",
                    f"`{counts['endpoints']['added']}/{counts['endpoints']['modified']}/{counts['endpoints']['removed']}`",
                    f"`{counts['messages']['added']}/{counts['messages']['modified']}/{counts['messages']['removed']}`",
                    f"`{counts['enums']['added']}/{counts['enums']['modified']}/{counts['enums']['removed']}`",
                    f"`{counts['files']['added']}/{counts['files']['modified']}/{counts['files']['removed']}`",
                ]
            )
            + " |"
        )

    package_rows = [
        "| Package | Files | Services | Endpoints | Messages | Enums |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for package in latest["packages"]:
        package_rows.append(
            "| "
            + " | ".join(
                [
                    escape_md_cell(package["package"]),
                    f"`{package['fileCount']}`",
                    f"`{package['serviceCount']}`",
                    f"`{package['endpointCount']}`",
                    f"`{package['messageCount']}`",
                    f"`{package['enumCount']}`",
                ]
            )
            + " |"
        )

    overview_lines = [
        "# Canton Protobuf History",
        "",
        "This page is generated from local descriptor-image snapshots with source info.",
        "",
        "## Source",
        "",
        f"- Source name: `{report['sourceName']}`",
        f"- Version filter: `{report['versionFilter']}`",
        f"- Latest release: `{report['latestRelease']}`",
        f"- Source repo: `{report['repo'].get('remote') or '-'}`",
        f"- Generated at: `{report['generatedAt']}`",
        "",
        "## Latest Snapshot",
        "",
        f"- Packages: `{latest['stats']['packages']}`",
        f"- Services: `{latest['stats']['services']}`",
        f"- Endpoints: `{latest['stats']['endpoints']}`",
        f"- Messages: `{latest['stats']['messages']}`",
        f"- Enums: `{latest['stats']['enums']}`",
        "",
        "## Endpoint Lifecycle",
        "",
        *lifecycle_rows,
        "",
        "## Release Summary",
        "",
        *release_rows,
        "",
        "## Latest Packages",
        "",
        *package_rows,
    ]

    pages.append(
        Page(
            path=overview_path.relative_to(root).as_posix(),
            title="Canton Protobuf History",
            description="Descriptor-backed protobuf API history and endpoint reference.",
            blocks=[RawMarkdown("\n".join(overview_lines).rstrip())],
        )
    )

    latest_endpoints = latest["endpoints"]
    releases_by_version = {release["version"]: release for release in report["releases"]}
    for lifecycle_entry in report["endpointLifecycle"]:
        endpoint = latest_endpoints.get(lifecycle_entry["id"])
        if endpoint is None:
            for release in reversed(report["releases"]):
                for candidate in release["changes"]["endpoints"]["removed"]:
                    if candidate["id"] == lifecycle_entry["id"]:
                        endpoint = candidate
                        break
                if endpoint is not None:
                    break
        if endpoint is None:
            continue

        page_path = endpoint_page_map[lifecycle_entry["id"]]
        lines = [
            f"# Endpoint `{endpoint['id']}`",
            "",
            f"[Back to Canton Protobuf History]({relative_page_link(page_path, overview_path)})",
            "",
            "## Snapshot",
            "",
            f"- Introduced in: `{lifecycle_entry['introducedIn']}`",
            f"- Last changed in: `{lifecycle_entry['lastChangedIn']}`",
            f"- Removed in: `{lifecycle_entry['removedIn'] or '-'}`",
            f"- Status: `{'current' if lifecycle_entry['current'] else 'removed'}`",
            f"- Source: {md_link(endpoint['file'], endpoint.get('sourceUrl'))}",
            "",
            "## Signature",
            "",
            f"```protobuf\nrpc {render_endpoint_signature(endpoint)};\n```",
            "",
            render_description(endpoint["description"]),
            "",
            "## History",
            "",
            render_history_table(lifecycle_entry),
            "",
            "## Request Type",
            "",
            *render_type_section(endpoint["requestType"], ctx, level=3),
            "",
            "## Response Type",
            "",
            *render_type_section(endpoint["responseType"], ctx, level=3),
        ]
        pages.append(
            Page(
                path=page_path.relative_to(root).as_posix(),
                title=f"{endpoint['service']}.{endpoint['name']}",
                description=f"Descriptor-backed protobuf endpoint reference for {endpoint['id']}.",
                blocks=[RawMarkdown("\n".join(lines).rstrip())],
            )
        )

    return root, pages
