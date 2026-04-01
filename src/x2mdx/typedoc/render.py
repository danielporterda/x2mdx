"""Render TypeDoc reports into MDX pages."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from x2mdx.output import Heading, Page, RawMarkdown, Table


def escape_md_cell(text: str) -> str:
    return text.replace("|", r"\|").replace("\n", "<br/>")


def build_page(
    report,
    *,
    output_path: str,
    page_title: str,
    page_description: str,
) -> Page:
    blocks: list[object] = [
        RawMarkdown(
            "\n".join(
                [
                    f"Generated from published `{report.package_name}` TypeDoc snapshots.",
                    "",
                    f"- Publish version: `{report.publish_version}`",
                    f"- Versions compared: {', '.join(f'`{version}`' for version in report.versions)}",
                    f"- Source: `{report.source_name}`",
                    f"- Version filter: `{report.version_filter}`",
                ]
            )
        ),
        Heading(level=2, text="Export Diff Summary"),
        Table(
            headers=["Export", "Kind", "Introduced", "Changed In", "Removed"],
            rows=[
                [
                    f"[`{escape_md_cell(export['name'])}`](#{export['anchor']})",
                    escape_md_cell(export["kind_label"]),
                    f"`{export['introduced_in']}`",
                    ", ".join(f"`{version}`" for version in export["changed_in"]) if export["changed_in"] else "-",
                    f"`{export['removed_in']}`" if export["removed_in"] else "-",
                ]
                for export in report.exports
            ],
        ),
    ]

    exports_by_group: dict[str, list[dict[str, object]]] = defaultdict(list)
    for export in report.exports:
        exports_by_group[export["group"]].append(export)

    for group_title in report.export_groups:
        exports = exports_by_group.get(group_title)
        if not exports:
            continue
        blocks.append(Heading(level=2, text=group_title))
        for export in exports:
            blocks.append(RawMarkdown(f'<a id="{export["anchor"]}"></a>'))
            blocks.append(Heading(level=3, text=str(export["name"])))
            lifecycle_bits = [
                f"Kind: `{export['kind_label']}`",
                f"Introduced: `{export['introduced_in']}`",
            ]
            if export["changed_in"]:
                lifecycle_bits.append("Changed in: " + ", ".join(f"`{version}`" for version in export["changed_in"]))
            if export["removed_in"]:
                lifecycle_bits.append(f"Removed in: `{export['removed_in']}`")
                lifecycle_bits.append("Shown for historical reference.")
            if export["source_location"]:
                lifecycle_bits.append(f"Source: `{export['source_location']}`")
            blocks.append(RawMarkdown("\n".join(f"- {item}" for item in lifecycle_bits)))

            if export["signature"]:
                blocks.append(RawMarkdown(f"**Signature**\n\n```ts\n{export['signature']}\n```"))
            if export["summary"]:
                blocks.append(RawMarkdown(str(export["summary"])))

            if export["type_parameters"]:
                blocks.append(RawMarkdown("**Type Parameters**"))
                blocks.append(
                    Table(
                        headers=["Name", "Constraint", "Default", "Description"],
                        rows=[
                            [
                                f"`{escape_md_cell(item['name'])}`",
                                f"`{escape_md_cell(item['constraint'])}`" if item["constraint"] else "-",
                                f"`{escape_md_cell(item['default'])}`" if item["default"] else "-",
                                escape_md_cell(item["description"]) if item["description"] else "-",
                            ]
                            for item in export["type_parameters"]
                        ],
                    )
                )

            signature_docs = export["signature_docs"]
            if signature_docs:
                blocks.append(RawMarkdown("**Call Signatures**"))
                for index, signature in enumerate(signature_docs, start=1):
                    if len(signature_docs) > 1:
                        blocks.append(RawMarkdown(f"Overload {index}:"))
                    blocks.append(RawMarkdown(f"```ts\n{signature['declaration']}\n```"))
                    if signature["summary"]:
                        blocks.append(RawMarkdown(signature["summary"]))
                    if signature["type_parameters"]:
                        blocks.append(
                            Table(
                                headers=["Type Parameter", "Constraint", "Default", "Description"],
                                rows=[
                                    [
                                        f"`{escape_md_cell(item['name'])}`",
                                        f"`{escape_md_cell(item['constraint'])}`" if item["constraint"] else "-",
                                        f"`{escape_md_cell(item['default'])}`" if item["default"] else "-",
                                        escape_md_cell(item["description"]) if item["description"] else "-",
                                    ]
                                    for item in signature["type_parameters"]
                                ],
                            )
                        )
                    if signature["parameters"]:
                        blocks.append(
                            Table(
                                headers=["Parameter", "Type", "Required", "Description"],
                                rows=[
                                    [
                                        f"`{escape_md_cell(item['name'])}`",
                                        f"`{escape_md_cell(item['type'])}`",
                                        item["required"],
                                        escape_md_cell(item["description"]) if item["description"] else "-",
                                    ]
                                    for item in signature["parameters"]
                                ],
                            )
                        )
                    blocks.append(RawMarkdown(f"Returns: `{signature['returns']}`"))

            if export["members"]:
                blocks.append(RawMarkdown("**Members**"))
                blocks.append(
                    Table(
                        headers=["Member", "Type", "Description"],
                        rows=[
                            [
                                f"`{escape_md_cell(item['name'])}`",
                                f"`{escape_md_cell(item['type'])}`",
                                escape_md_cell(item["summary"]) if item["summary"] else "-",
                            ]
                            for item in export["members"]
                        ],
                    )
                )

    return Page(
        path=output_path,
        title=page_title,
        description=page_description,
        blocks=blocks,
    )
