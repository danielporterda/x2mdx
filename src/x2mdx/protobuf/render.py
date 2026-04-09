"""Render descriptor-backed protobuf history reports into grouped MDX pages."""

from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from x2mdx.output import Page
from x2mdx.templating import markdown_page

PACKAGE_GROUP_ORDER = [
    "Ledger API",
    "Participant Administration",
    "Sequencer",
    "Mediator",
    "Shared Administration",
    "Other APIs",
    "Schema Packages",
]


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


def compact_text(text: str, *, limit: int = 120) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def change_versions_for_package(
    package_name: str,
    endpoint_lifecycle: list[dict[str, Any]],
    *,
    version_order: dict[str, int],
) -> list[str]:
    versions = {
        str(event["version"])
        for entry in endpoint_lifecycle
        if entry["package"] == package_name
        for event in entry.get("history", [])
        if event.get("kind") == "modified"
    }
    return sorted(versions, key=lambda version: version_order.get(version, len(version_order)))


def introduced_version_for_package(
    package_name: str,
    endpoint_lifecycle: list[dict[str, Any]],
    *,
    version_order: dict[str, int],
) -> str | None:
    versions = [str(entry["introducedIn"]) for entry in endpoint_lifecycle if entry["package"] == package_name and entry.get("introducedIn")]
    if not versions:
        return None
    return sorted(versions, key=lambda version: version_order.get(version, len(version_order)))[0]


def slugify_segment(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return slug or "item"


def relative_page_link(from_path: Path, to_path: Path) -> str:
    relative = os.path.relpath(to_path.with_suffix(""), start=from_path.parent)
    return Path(relative).as_posix()


def relative_anchor_link(from_path: Path, to_path: Path, anchor: str) -> str:
    if from_path == to_path:
        return f"#{anchor}"
    return f"{relative_page_link(from_path, to_path)}#{anchor}"


def service_anchor(service_id: str) -> str:
    return f"service-{slugify_segment(service_id)}"


def endpoint_anchor(endpoint_id: str) -> str:
    return f"endpoint-{slugify_segment(endpoint_id)}"


def type_anchor(type_name: str) -> str:
    return f"type-{slugify_segment(type_name)}"


def build_package_page_path(output_dir: Path, package_name: str) -> Path:
    return output_dir / "packages" / f"{slugify_segment(package_name)}.mdx"


def build_package_page_map(report: dict[str, Any], *, output_dir: Path) -> dict[str, Path]:
    package_names = {package["package"] for package in report["latestSnapshot"]["packages"]}
    package_names.update(entry["package"] for entry in report["endpointLifecycle"])
    return {
        package_name: build_package_page_path(output_dir, package_name)
        for package_name in sorted(package_names)
    }


def build_type_page_map(report: dict[str, Any], *, package_page_map: dict[str, Path]) -> dict[str, Path]:
    latest = report["latestSnapshot"]
    version_order = {str(release["version"]): index for index, release in enumerate(report["releases"])}
    type_page_map: dict[str, Path] = {}
    for collection_name in ("messages", "enums"):
        for entity in latest[collection_name].values():
            page_path = package_page_map.get(entity["package"])
            if page_path is not None:
                type_page_map[entity["id"]] = page_path
    return type_page_map


def package_group(package_name: str, *, has_services: bool) -> str:
    if not has_services:
        return "Schema Packages"
    if package_name.startswith("com.daml.ledger.api.v2"):
        return "Ledger API"
    if ".participant." in package_name:
        return "Participant Administration"
    if "sequencer" in package_name:
        return "Sequencer"
    if "mediator" in package_name:
        return "Mediator"
    if package_name.startswith(
        (
            "com.digitalasset.canton.admin.health",
            "com.digitalasset.canton.connection",
            "com.digitalasset.canton.crypto",
            "com.digitalasset.canton.time",
            "com.digitalasset.canton.topology",
        )
    ):
        return "Shared Administration"
    return "Other APIs"


def package_group_sort_key(package_name: str, *, has_services: bool) -> tuple[int, str]:
    label = package_group(package_name, has_services=has_services)
    return (PACKAGE_GROUP_ORDER.index(label), package_name)


def render_type_link(type_name: str, *, from_path: Path, type_page_map: dict[str, Path]) -> str:
    label = f"`{escape_md(type_name)}`"
    page_path = type_page_map.get(type_name)
    if page_path is None:
        return label
    return f"[{label}]({relative_anchor_link(from_path, page_path, type_anchor(type_name))})"


def render_field_type(field: dict[str, Any], *, current_page: Path, type_page_map: dict[str, Path]) -> str:
    type_name = field.get("typeName")
    if type_name and not field.get("map"):
        return render_type_link(type_name, from_path=current_page, type_page_map=type_page_map)
    return f"`{escape_md(field['type'])}`"


def render_message_block(
    message: dict[str, Any],
    ctx: dict[str, dict[str, Any]],
    *,
    current_page: Path,
    type_page_map: dict[str, Path],
    seen: set[str],
) -> list[str]:
    if message["id"] in seen:
        return []
    seen.add(message["id"])

    lines = [
        f'<a id="{type_anchor(message["id"])}"></a>',
        f"**Message `{message['id']}`**",
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
            lines.append(
                "| "
                + " | ".join(
                    [
                        escape_md_cell(field["name"]),
                        render_field_type(field, current_page=current_page, type_page_map=type_page_map),
                        escape_md_cell(field["label"]),
                        escape_md_cell(field["description"] or ""),
                    ]
                )
                + " |"
            )

    for enum_id in message.get("enumIds", []):
        nested_lines = render_enum_block(
            ctx["enums"][enum_id],
            ctx,
            current_page=current_page,
            type_page_map=type_page_map,
            seen=seen,
        )
        if nested_lines:
            lines.extend(["", *nested_lines])
    for nested_id in message.get("nestedMessageIds", []):
        nested_lines = render_message_block(
            ctx["messages"][nested_id],
            ctx,
            current_page=current_page,
            type_page_map=type_page_map,
            seen=seen,
        )
        if nested_lines:
            lines.extend(["", *nested_lines])
    return lines


def render_enum_block(
    enum_doc: dict[str, Any],
    ctx: dict[str, dict[str, Any]],
    *,
    current_page: Path,
    type_page_map: dict[str, Path],
    seen: set[str],
) -> list[str]:
    del current_page, type_page_map
    if enum_doc["id"] in seen:
        return []
    seen.add(enum_doc["id"])

    lines = [
        f'<a id="{type_anchor(enum_doc["id"])}"></a>',
        f"**Enum `{enum_doc['id']}`**",
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


def endpoint_snapshot_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    latest_endpoints = dict(report["latestSnapshot"]["endpoints"])
    snapshots = dict(latest_endpoints)
    for release in reversed(report["releases"]):
        for endpoint in release["changes"]["endpoints"]["removed"]:
            snapshots.setdefault(endpoint["id"], endpoint)
    return snapshots


def build_package_docs(report: dict[str, Any]) -> list[dict[str, Any]]:
    latest = report["latestSnapshot"]
    package_docs = {package["package"]: dict(package) for package in latest["packages"]}
    current_services = latest["services"]
    current_endpoints = latest["endpoints"]

    for entry in report["endpointLifecycle"]:
        package_doc = package_docs.setdefault(
            entry["package"],
            {
                "package": entry["package"],
                "fileIds": [],
                "fileCount": 0,
                "serviceIds": [],
                "serviceCount": 0,
                "endpointIds": [],
                "endpointCount": 0,
                "messageIds": [],
                "messageCount": 0,
                "enumIds": [],
                "enumCount": 0,
            },
        )
        if entry["id"] not in package_doc["endpointIds"] and entry["id"] in current_endpoints:
            package_doc["endpointIds"].append(entry["id"])

    for service_id, service_doc in current_services.items():
        package_doc = package_docs.setdefault(
            service_doc["package"],
            {
                "package": service_doc["package"],
                "fileIds": [],
                "fileCount": 0,
                "serviceIds": [],
                "serviceCount": 0,
                "endpointIds": [],
                "endpointCount": 0,
                "messageIds": [],
                "messageCount": 0,
                "enumIds": [],
                "enumCount": 0,
            },
        )
        if service_id not in package_doc["serviceIds"]:
            package_doc["serviceIds"].append(service_id)

    for package_doc in package_docs.values():
        package_doc["serviceIds"] = sorted(package_doc["serviceIds"])
        package_doc["endpointIds"] = sorted(package_doc["endpointIds"])
        package_doc["serviceCount"] = len(package_doc["serviceIds"])
        package_doc["endpointCount"] = len(package_doc["endpointIds"])

    return sorted(
        package_docs.values(),
        key=lambda package: package_group_sort_key(
            package["package"],
            has_services=bool(package["serviceCount"] or package["endpointCount"]),
        ),
    )


def render_overview_page(
    report: dict[str, Any],
    *,
    output_dir: Path,
    overview_path: Path,
    package_page_map: dict[str, Path],
    package_docs: list[dict[str, Any]],
) -> Page:
    latest = report["latestSnapshot"]
    version_order = {str(release["version"]): index for index, release in enumerate(report["releases"])}

    release_rows: list[list[str]] = []
    for release in report["releases"]:
        counts = release["changes"]["counts"]
        release_rows.append(
            [
                f"`{release['version']}`",
                str(counts["endpoints"]["added"]),
                str(counts["endpoints"]["modified"]),
                str(counts["endpoints"]["removed"]),
            ]
        )

    package_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for package in package_docs:
        label = package_group(
            package["package"],
            has_services=bool(package["serviceCount"] or package["endpointCount"]),
        )
        package_groups[label].append(package)

    grouped_packages: list[dict[str, Any]] = []
    toc_rows: list[list[str]] = []
    for label in PACKAGE_GROUP_ORDER:
        packages = package_groups.get(label, [])
        if not packages:
            continue
        rows: list[list[str]] = []
        for package in packages:
            package_path = package_page_map[package["package"]]
            link = package_path.relative_to(output_dir.parent).with_suffix("").as_posix()
            introduced = introduced_version_for_package(
                package["package"],
                report["endpointLifecycle"],
                version_order=version_order,
            )
            changed_versions = change_versions_for_package(
                package["package"],
                report["endpointLifecycle"],
                version_order=version_order,
            )
            rows.append(
                [
                    f"[`{escape_md(package['package'])}`]({link})",
                    f"`{package['serviceCount']}`",
                    f"`{package['endpointCount']}`",
                    f"`{package['messageCount']}`",
                    f"`{package['enumCount']}`",
                ]
            )
            toc_rows.append(
                [
                    f"[`{escape_md(package['package'])}`]({link})",
                    "`Package`",
                    escape_md_cell(
                        compact_text(
                            f"{package['serviceCount']} services, {package['endpointCount']} endpoints, "
                            f"{package['messageCount']} messages, {package['enumCount']} enums"
                        )
                    ),
                    f"`{introduced}`" if introduced else "-",
                    ", ".join(f"`{version}`" for version in changed_versions) if changed_versions else "-",
                    "-",
                    "-",
                ]
            )
        grouped_packages.append({"label": label, "rows": rows})

    return markdown_page(
        path=overview_path.relative_to(output_dir.parent).as_posix(),
        title="Canton Protobuf History",
        description="Descriptor-backed protobuf API history grouped by package.",
        template_name="protobuf/overview.md.j2",
        toc_rows=toc_rows,
        package_groups=grouped_packages,
        release_rows=release_rows,
    )


def render_package_page(
    package_doc: dict[str, Any],
    report: dict[str, Any],
    *,
    package_path: Path,
    overview_path: Path,
    ctx: dict[str, dict[str, Any]],
    endpoint_docs: dict[str, dict[str, Any]],
    type_page_map: dict[str, Path],
) -> Page:
    lifecycle_map = {entry["id"]: entry for entry in report["endpointLifecycle"]}
    package_entries = sorted(
        [entry for entry in report["endpointLifecycle"] if entry["package"] == package_doc["package"]],
        key=lambda entry: (entry["service"], entry["name"]),
    )
    service_buckets: dict[str, dict[str, Any]] = {}
    for service_id in package_doc["serviceIds"]:
        service_doc = ctx["services"][service_id]
        service_buckets[service_id] = {
            "id": service_id,
            "name": service_doc["name"],
            "file": service_doc["file"],
            "sourceUrl": service_doc.get("sourceUrl"),
            "description": service_doc.get("description", ""),
            "endpointIds": [],
        }
    for entry in package_entries:
        bucket = service_buckets.setdefault(
            entry["serviceFullName"],
            {
                "id": entry["serviceFullName"],
                "name": entry["service"],
                "file": endpoint_docs.get(entry["id"], {}).get("file", "-"),
                "sourceUrl": endpoint_docs.get(entry["id"], {}).get("sourceUrl"),
                "description": "",
                "endpointIds": [],
            },
        )
        bucket["endpointIds"].append(entry["id"])

    package_files = [ctx["files"][file_id] for file_id in package_doc["fileIds"] if file_id in ctx["files"]]
    package_messages = [ctx["messages"][message_id] for message_id in package_doc["messageIds"] if message_id in ctx["messages"]]
    package_enums = [ctx["enums"][enum_id] for enum_id in package_doc["enumIds"] if enum_id in ctx["enums"]]

    service_contexts: list[dict[str, Any]] = []
    service_rows: list[list[str]] = []
    for service in sorted(service_buckets.values(), key=lambda item: item["name"]):
        service_rows.append(
            [
                f"[`{escape_md(service['name'])}`](#{service_anchor(service['id'])})",
                f"`{len(service['endpointIds'])}`",
                md_link("file", service.get("sourceUrl")),
                escape_md_cell(compact_text(service.get("description", ""))),
            ]
        )
        service_contexts.append(
            {
                "anchor": service_anchor(service["id"]),
                "heading": f"Service `{service['name']}`",
                "summary_items": [
                    f"Source: {md_link(service['file'], service.get('sourceUrl'))}",
                    f"Endpoints tracked: `{len(service['endpointIds'])}`",
                ],
                "description": render_description(service.get("description", "")),
                "endpoint_rows": [
                    [
                        f"[`{escape_md(endpoint_docs[endpoint_id]['name'])}`](#{endpoint_anchor(endpoint_id)})",
                        f"`{lifecycle_map[endpoint_id]['introducedIn']}`",
                        f"`{lifecycle_map[endpoint_id]['lastChangedIn']}`",
                        f"`{lifecycle_map[endpoint_id]['removedIn'] or ''}`",
                        render_type_link(endpoint_docs[endpoint_id]["requestType"], from_path=package_path, type_page_map=type_page_map),
                        render_type_link(endpoint_docs[endpoint_id]["responseType"], from_path=package_path, type_page_map=type_page_map),
                        md_link("file", endpoint_docs[endpoint_id].get("sourceUrl")),
                    ]
                    for endpoint_id in sorted(service["endpointIds"])
                ],
                "endpoint_details": [
                    {
                        "anchor": endpoint_anchor(endpoint_id),
                        "title": f"{endpoint_docs[endpoint_id]['service']}.{endpoint_docs[endpoint_id]['name']}",
                        "summary_items": [
                            f"Introduced in: `{lifecycle_map[endpoint_id]['introducedIn']}`",
                            f"Last changed in: `{lifecycle_map[endpoint_id]['lastChangedIn']}`",
                            f"Removed in: `{lifecycle_map[endpoint_id]['removedIn'] or '-'}`",
                            f"Status: `{'current' if lifecycle_map[endpoint_id]['current'] else 'removed'}`",
                            f"Source: {md_link(endpoint_docs[endpoint_id]['file'], endpoint_docs[endpoint_id].get('sourceUrl'))}",
                        ],
                        "signature": f"rpc {render_endpoint_signature(endpoint_docs[endpoint_id])};",
                        "description": render_description(endpoint_docs[endpoint_id]["description"]),
                        "history_table": render_history_table(lifecycle_map[endpoint_id]),
                        "request_type": render_type_link(
                            endpoint_docs[endpoint_id]["requestType"],
                            from_path=package_path,
                            type_page_map=type_page_map,
                        ),
                        "response_type": render_type_link(
                            endpoint_docs[endpoint_id]["responseType"],
                            from_path=package_path,
                            type_page_map=type_page_map,
                        ),
                    }
                    for endpoint_id in sorted(service["endpointIds"])
                ],
            }
        )

    type_reference_blocks: list[str] = []
    if package_messages or package_enums:
        seen: set[str] = set()
        for message in package_messages:
            block_lines = render_message_block(
                message,
                ctx,
                current_page=package_path,
                type_page_map=type_page_map,
                seen=seen,
            )
            if block_lines:
                type_reference_blocks.append("\n".join(block_lines))
        for enum_doc in package_enums:
            block_lines = render_enum_block(
                enum_doc,
                ctx,
                current_page=package_path,
                type_page_map=type_page_map,
                seen=seen,
            )
            if block_lines:
                type_reference_blocks.append("\n".join(block_lines))

    return markdown_page(
        path=package_path.relative_to(overview_path.parent.parent).as_posix(),
        title=package_doc["package"],
        description=f"Descriptor-backed protobuf API history for package {package_doc['package']}.",
        template_name="protobuf/package.md.j2",
        package_title=f"Package `{package_doc['package']}`",
        overview_link=relative_page_link(package_path, overview_path),
        snapshot_items=[
            f"Current files: `{package_doc['fileCount']}`",
            f"Current services: `{package_doc['serviceCount']}`",
            f"Current endpoints: `{package_doc['endpointCount']}`",
            f"Current messages: `{package_doc['messageCount']}`",
            f"Current enums: `{package_doc['enumCount']}`",
            f"Lifecycle endpoints tracked: `{len(package_entries)}`",
        ],
        source_file_rows=[
            [
                escape_md_cell(file_doc["repoPath"]),
                f"`{len(file_doc['serviceIds'])}`",
                f"`{len(file_doc['messageIds'])}`",
                f"`{len(file_doc['enumIds'])}`",
                md_link("file", file_doc.get("sourceUrl")),
            ]
            for file_doc in package_files
        ],
        service_rows=service_rows,
        services=service_contexts,
        type_reference_blocks=type_reference_blocks,
    )


def build_pages(report: dict[str, Any], *, output_dir: Path) -> tuple[Path, list[Page]]:
    root = output_dir.parent
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
    overview_path = output_dir / "index.mdx"
    package_docs = build_package_docs(report)
    package_page_map = build_package_page_map(report, output_dir=output_dir)
    type_page_map = build_type_page_map(report, package_page_map=package_page_map)
    endpoint_docs = endpoint_snapshot_map(report)

    pages = [
        render_overview_page(
            report,
            output_dir=output_dir,
            overview_path=overview_path,
            package_page_map=package_page_map,
            package_docs=package_docs,
        )
    ]
    for package_doc in package_docs:
        package_path = package_page_map[package_doc["package"]]
        pages.append(
            render_package_page(
                package_doc,
                report,
                package_path=package_path,
                overview_path=overview_path,
                ctx=ctx,
                endpoint_docs=endpoint_docs,
                type_page_map=type_page_map,
            )
        )

    return root, pages
