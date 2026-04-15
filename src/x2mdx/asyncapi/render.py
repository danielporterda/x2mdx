"""Render AsyncAPI lifecycle reports into MDX pages."""

from __future__ import annotations

import json
import html
import re
from pathlib import Path
from typing import Any

from x2mdx.asyncapi.models import AsyncApiChannelLifecycle, AsyncApiReport
from x2mdx.output import Page
from x2mdx.presentation import (
    CollectionPageModel,
    DetailCodeBlock,
    DetailTable,
    LifecycleStatus,
    ProtocolInteraction,
    ProtocolSubject,
    VersionDeltaRow,
    version_delta_row_cells,
)
from x2mdx.templating import markdown_page


def escape_md_cell(text: str) -> str:
    return text.replace("|", r"\|").replace("\n", "<br/>")


def slugify(value: str) -> str:
    output = value.lower()
    output = re.sub(r"[^a-z0-9]+", "-", output)
    output = re.sub(r"-{2,}", "-", output).strip("-")
    return output


def md_code(text: Any) -> str:
    output = str(text).replace("`", "\\`").replace("|", "\\|").replace("\n", " ").strip()
    return f"`{output}`"


def channel_anchor(channel: str) -> str:
    return f"channel-{slugify(channel)}"


def channel_link(channel: str) -> str:
    escaped = html.escape(channel, quote=False)
    return f"[`{escaped}`](#{channel_anchor(channel)})"


def render_change_summary(change_details: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for entry in change_details:
        version = str(entry["version"])
        changes = entry["changes"] if isinstance(entry.get("changes"), list) else []
        rendered_changes = "; ".join(str(change) for change in changes) if changes else "details updated"
        parts.append(f"`{version}`: {rendered_changes}")
    return "<br/>".join(parts) if parts else "-"


def action_list(channel: AsyncApiChannelLifecycle) -> str:
    actions = channel.latest.get("action_names", [])
    if not actions:
        return "-"
    return ", ".join(md_code(action) for action in actions)


def compact_text(text: str, *, limit: int = 120) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return "-"
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _channel_context_legacy(channel: AsyncApiChannelLifecycle) -> dict[str, Any]:
    lifecycle_bits = [
        f"Actions: {action_list(channel)}",
        f"Introduced: `{channel.introduced_version}`",
    ]
    if channel.change_details:
        lifecycle_bits.append("Changed in: " + ", ".join(f"`{entry['version']}`" for entry in channel.change_details))
    if channel.removed_version:
        lifecycle_bits.append(f"Removed in: `{channel.removed_version}`")
        lifecycle_bits.append("Shown for historical reference.")

    return {
        "anchor": channel.anchor,
        "name": channel.channel,
        "lifecycle_bits": lifecycle_bits,
        "description": str(channel.latest.get("description") or ""),
        "change_rows": [
            [
                md_code(str(entry["version"])),
                escape_md_cell("; ".join(str(change) for change in entry["changes"])),
            ]
            for entry in channel.change_details
        ],
        "actions": [
            {
                "heading": str(action["action"]).capitalize(),
                "detail_items": [
                    item
                    for item in [
                        f"Operation ID: `{action['operation_id']}`" if action["operation_id"] else "",
                        f"WebSocket method: `{action['ws_method']}`" if action["ws_method"] else "",
                        (
                            f"Message: `{action['message']['name']}`"
                            if action["message"]["name"] and action["message"]["name"] != "-"
                            else ""
                        ),
                        (
                            f"Content type: `{action['message']['content_type']}`"
                            if action["message"]["content_type"] and action["message"]["content_type"] != "-"
                            else ""
                        ),
                    ]
                    if item
                ],
                "description": action["description"],
                "payload_row": [
                    md_code(action["message"]["payload_schema"]),
                    (
                        ", ".join(md_code(field) for field in action["message"]["required_fields"])
                        if action["message"]["required_fields"]
                        else "-"
                    ),
                ],
                "sample": action["message"]["sample"],
            }
            for action in channel.latest.get("actions", [])
        ],
    }


def build_page_legacy(
    report: AsyncApiReport,
    *,
    output_path: str,
    page_title: str,
    page_description: str,
) -> Page:
    return markdown_page(
        path=Path(output_path).as_posix(),
        title=page_title,
        description=page_description,
        template_name="asyncapi/page.md.j2",
        report=report,
        version_timeline_rows=[
            [
                md_code(version),
                str(report.per_version_deltas[version]["added_count"]),
                str(report.per_version_deltas[version]["changed_count"]),
                str(report.per_version_deltas[version]["removed_count"]),
            ]
            for version in report.versions
        ],
        channel_summary_rows=[
            [
                channel_link(channel.channel),
                action_list(channel),
                escape_md_cell(compact_text(str(channel.latest.get("description") or ""))),
                md_code(channel.introduced_version),
                escape_md_cell(render_change_summary(channel.change_details)),
                "-",
                md_code(channel.removed_version) if channel.removed_version else "-",
            ]
            for channel in report.channels
        ],
        channels=[_channel_context_legacy(channel) for channel in report.channels],
    )


def _channel_subject(channel: AsyncApiChannelLifecycle) -> ProtocolSubject:
    lifecycle_items = [
        f"Actions: {action_list(channel)}",
        f"Introduced: `{channel.introduced_version}`",
    ]
    if channel.change_details:
        lifecycle_items.append("Changed in: " + ", ".join(f"`{entry['version']}`" for entry in channel.change_details))
    if channel.removed_version:
        lifecycle_items.append(f"Removed in: `{channel.removed_version}`")
        lifecycle_items.append("Shown for historical reference.")
    interactions: list[ProtocolInteraction] = []
    for action in channel.latest.get("actions", []):
        detail_items = tuple(
            item
            for item in [
                f"Operation ID: `{action['operation_id']}`" if action["operation_id"] else "",
                f"WebSocket method: `{action['ws_method']}`" if action["ws_method"] else "",
                (
                    f"Message: `{action['message']['name']}`"
                    if action["message"]["name"] and action["message"]["name"] != "-"
                    else ""
                ),
                (
                    f"Content type: `{action['message']['content_type']}`"
                    if action["message"]["content_type"] and action["message"]["content_type"] != "-"
                    else ""
                ),
            ]
            if item
        )
        detail_blocks: list[DetailTable | DetailCodeBlock] = [
            DetailTable(
                headers=("Payload Schema", "Required Fields"),
                rows=(
                    (
                        md_code(action["message"]["payload_schema"]),
                        ", ".join(md_code(field) for field in action["message"]["required_fields"])
                        if action["message"]["required_fields"]
                        else "-",
                    ),
                ),
            )
        ]
        if action["message"]["sample"] is not None:
            detail_blocks.append(
                DetailCodeBlock(
                    title="Message Example",
                    language="json",
                    body=json.dumps(action["message"]["sample"], indent=2),
                )
            )
        interactions.append(
            ProtocolInteraction(
                label=str(action["action"]).capitalize(),
                detail_items=detail_items,
                description=str(action["description"] or ""),
                detail_blocks=tuple(detail_blocks),
            )
        )
    return ProtocolSubject(
        anchor=channel.anchor,
        title=channel.channel,
        kind=action_list(channel),
        summary=escape_md_cell(compact_text(str(channel.latest.get("description") or ""))),
        lifecycle=LifecycleStatus.from_values(
            introduced=channel.introduced_version,
            changed_versions=[str(entry["version"]) for entry in channel.change_details],
            removed=channel.removed_version,
        ),
        lifecycle_items=tuple(lifecycle_items),
        description=str(channel.latest.get("description") or ""),
        version_changes=tuple(
            (
                md_code(str(entry["version"])),
                escape_md_cell("; ".join(str(change) for change in entry["changes"])),
            )
            for entry in channel.change_details
        ),
        interactions=tuple(interactions),
    )


def _channel_context(channel: ProtocolSubject) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for action in channel.interactions:
        payload = next(
            block for block in action.detail_blocks if isinstance(block, DetailTable) and block.headers == ("Payload Schema", "Required Fields")
        )
        sample = next((block for block in action.detail_blocks if isinstance(block, DetailCodeBlock)), None)
        actions.append(
            {
                "heading": action.label,
                "detail_items": list(action.detail_items),
                "description": action.description,
                "payload_row": list(payload.rows[0]),
                "sample": json.loads(sample.body) if sample else None,
            }
        )
    return {
        "anchor": channel.anchor,
        "name": channel.title,
        "lifecycle_bits": list(channel.lifecycle_items),
        "description": channel.description,
        "change_rows": [list(row) for row in channel.version_changes],
        "actions": actions,
    }


def build_page(
    report: AsyncApiReport,
    *,
    output_path: str,
    page_title: str,
    page_description: str,
) -> Page:
    channels = tuple(_channel_subject(channel) for channel in report.channels)
    page_model = CollectionPageModel(
        path=Path(output_path).as_posix(),
        title=page_title,
        description=page_description,
        version_rows=tuple(
            VersionDeltaRow(
                version=version,
                added=str(report.per_version_deltas[version]["added_count"]),
                changed=str(report.per_version_deltas[version]["changed_count"]),
                removed=str(report.per_version_deltas[version]["removed_count"]),
            )
            for version in report.versions
        ),
        toc_rows=tuple(
            (
                channel_link(channel.title),
                channel.kind,
                channel.summary,
                md_code(channel.lifecycle.introduced or "-"),
                "<br/>".join(f"{version}: {changes}" for version, changes in channel.version_changes)
                if channel.version_changes
                else "-",
                "-",
                md_code(channel.lifecycle.removed) if channel.lifecycle.removed else "-",
            )
            for channel in channels
        ),
    )
    return markdown_page(
        path=page_model.path,
        title=page_model.title,
        description=page_model.description,
        template_name="asyncapi/page.md.j2",
        report=report,
        version_timeline_rows=[version_delta_row_cells(row) for row in page_model.version_rows],
        channel_summary_rows=[list(row) for row in page_model.toc_rows],
        channels=[_channel_context(channel) for channel in channels],
    )
