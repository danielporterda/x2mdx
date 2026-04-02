"""Render AsyncAPI lifecycle reports into MDX pages."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from x2mdx.asyncapi.models import AsyncApiChannelLifecycle, AsyncApiReport
from x2mdx.output import Heading, Page, RawMarkdown, Table


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


def build_page(
    report: AsyncApiReport,
    *,
    output_path: str,
    page_title: str,
    page_description: str,
) -> Page:
    blocks: list[object] = [
        RawMarkdown(
            "\n".join(
                [
                    f"Generated from AsyncAPI snapshots for `{report.info_title or 'unknown spec'}`.",
                    "",
                    f"- Publish version: `{report.publish_version}`",
                    f"- Versions compared: {', '.join(f'`{version}`' for version in report.versions)}",
                    f"- Source: `{report.source_name}`",
                    f"- Version filter: `{report.version_filter}`",
                    f"- Latest source path: `{report.latest_source_path}`",
                    f"- AsyncAPI version: `{report.asyncapi_version or '-'}`",
                ]
            )
        ),
        Heading(level=2, text="Version Change Timeline"),
        Table(
            headers=["Version", "Active Channels", "Added", "Changed", "Removed"],
            rows=[
                [
                    md_code(version),
                    str(report.per_version_deltas[version]["active_count"]),
                    str(report.per_version_deltas[version]["added_count"]),
                    str(report.per_version_deltas[version]["changed_count"]),
                    str(report.per_version_deltas[version]["removed_count"]),
                ]
                for version in report.versions
            ],
        ),
        Heading(level=2, text="Channel Diff Summary"),
        Table(
            headers=["Channel", "Actions", "Introduced", "Changes", "Removed"],
            rows=[
                [
                    channel_link(channel.channel),
                    action_list(channel),
                    md_code(channel.introduced_version),
                    escape_md_cell(render_change_summary(channel.change_details)),
                    md_code(channel.removed_version) if channel.removed_version else "-",
                ]
                for channel in report.channels
            ],
        ),
    ]

    if report.info_description:
        blocks.insert(
            1,
            RawMarkdown(report.info_description),
        )

    blocks.append(Heading(level=2, text="Channels"))
    for channel in report.channels:
        blocks.append(RawMarkdown(f'<a id="{channel.anchor}"></a>'))
        blocks.append(Heading(level=3, text=channel.channel))
        lifecycle_bits = [
            f"Actions: {action_list(channel)}",
            f"Introduced: `{channel.introduced_version}`",
        ]
        if channel.change_details:
            lifecycle_bits.append("Changed in: " + ", ".join(f"`{entry['version']}`" for entry in channel.change_details))
        if channel.removed_version:
            lifecycle_bits.append(f"Removed in: `{channel.removed_version}`")
            lifecycle_bits.append("Shown for historical reference.")
        blocks.append(RawMarkdown("\n".join(f"- {item}" for item in lifecycle_bits)))

        description = str(channel.latest.get("description") or "")
        if description:
            blocks.append(RawMarkdown(description))

        if channel.change_details:
            blocks.append(RawMarkdown("**Version Changes**"))
            blocks.append(
                Table(
                    headers=["Version", "Changes"],
                    rows=[
                        [
                            md_code(str(entry["version"])),
                            escape_md_cell("; ".join(str(change) for change in entry["changes"])),
                        ]
                        for entry in channel.change_details
                    ],
                )
            )

        for action in channel.latest.get("actions", []):
            blocks.append(RawMarkdown(f"**{action['action'].capitalize()}**"))
            action_bits = []
            if action["operation_id"]:
                action_bits.append(f"Operation ID: `{action['operation_id']}`")
            if action["ws_method"]:
                action_bits.append(f"WebSocket method: `{action['ws_method']}`")

            message = action["message"]
            if message["name"] and message["name"] != "-":
                action_bits.append(f"Message: `{message['name']}`")
            if message["content_type"] and message["content_type"] != "-":
                action_bits.append(f"Content type: `{message['content_type']}`")
            if action_bits:
                blocks.append(RawMarkdown("\n".join(f"- {item}" for item in action_bits)))

            if action["description"]:
                blocks.append(RawMarkdown(action["description"]))

            blocks.append(
                Table(
                    headers=["Payload Schema", "Required Fields"],
                    rows=[
                        [
                            md_code(message["payload_schema"]),
                            ", ".join(md_code(field) for field in message["required_fields"]) if message["required_fields"] else "-",
                        ]
                    ],
                )
            )

            if message["sample"] is not None:
                blocks.append(RawMarkdown("**Message Example**"))
                blocks.append(RawMarkdown(f"```json\n{json.dumps(message['sample'], indent=2)}\n```"))

    return Page(
        path=Path(output_path).as_posix(),
        title=page_title,
        description=page_description,
        blocks=blocks,
    )
