"""Render JVM doc lifecycle reports into MDX pages."""

from __future__ import annotations

import hashlib
import html
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from x2mdx.jvm_docs.models import JvmDocArtifactLifecycle, JvmDocLifecycleReport, JvmDocSymbolLifecycle
from x2mdx.output import BulletList, Heading, Page, Paragraph, RawMarkdown, Table


def slugify(value: str) -> str:
    out = value.lower()
    out = re.sub(r"[^a-z0-9]+", "-", out)
    return re.sub(r"-{2,}", "-", out).strip("-")


def md_code(text: str) -> str:
    out = str(text).replace("`", "\\`")
    return out.replace("|", "\\|").replace("\n", " ").strip()


def md_text(text: str) -> str:
    out = html.escape(str(text), quote=False)
    return out.replace("|", "\\|").replace("\n", " ").strip()


def page_path(root: Path, target: Path) -> str:
    return Path(os.path.relpath(target, start=root)).as_posix()


def relative_page_link(from_path: Path, to_path: Path) -> str:
    relative = os.path.relpath(to_path.with_suffix(""), start=from_path.parent)
    return Path(relative).as_posix()


def compute_output_root(overview_output: Path, details_dir: Path) -> Path:
    common = os.path.commonpath([os.path.abspath(str(overview_output)), os.path.abspath(str(details_dir))])
    return Path(common)


def latest_doc_link(symbol: JvmDocSymbolLifecycle) -> str:
    if not symbol.versions_present:
        return ""
    latest_version = symbol.versions_present[-1]
    return symbol.doc_links.get(latest_version, "")


def changed_symbols(artifact: JvmDocArtifactLifecycle) -> list[JvmDocSymbolLifecycle]:
    base_version = artifact.versions[0]
    return [
        symbol
        for symbol in artifact.symbols
        if symbol.introduced_version != base_version
        or symbol.deprecated_version is not None
        or symbol.removed_version is not None
    ]


def summarize_changes(artifact: JvmDocArtifactLifecycle) -> dict[str, int]:
    base_version = artifact.versions[0]
    return {
        "introduced": sum(1 for symbol in artifact.symbols if symbol.introduced_version != base_version),
        "deprecated": sum(1 for symbol in artifact.symbols if symbol.deprecated_version is not None),
        "removed": sum(1 for symbol in artifact.symbols if symbol.removed_version is not None),
    }


def format_lifecycle_value(value: str | None) -> str:
    if not value:
        return "-"
    return f"`{md_code(value)}`"


def java_member_owner(symbol: JvmDocSymbolLifecycle) -> str:
    if "#" not in symbol.symbol:
        return ""
    return symbol.symbol.split("#", 1)[0]


def java_member_label(symbol: JvmDocSymbolLifecycle) -> str:
    if "#" not in symbol.symbol:
        return symbol.symbol
    return symbol.symbol.split("#", 1)[1]


def scala_member_owner_and_label(symbol: JvmDocSymbolLifecycle) -> tuple[str, str]:
    if "member:" not in symbol.symbol_key:
        return "", symbol.symbol
    payload = symbol.symbol_key.split("member:", 1)[1]
    parts = payload.split("|", 2)
    member_fqn = parts[0]
    tail = parts[1] if len(parts) > 1 else ""
    owner = member_fqn.rsplit(".", 1)[0] if "." in member_fqn else ""
    member_name = member_fqn.rsplit(".", 1)[-1]
    label = f"{member_name}{tail}" if tail else member_name
    return owner, label


def package_name_for_symbol(symbol: JvmDocSymbolLifecycle) -> str:
    doc_path = symbol.latest_doc_path.strip("/")
    package_path = Path(doc_path).parent.as_posix().strip(".")
    if package_path and package_path != ".":
        return package_path.replace("/", ".")
    if symbol.kind == "type" and "." in symbol.symbol:
        return symbol.symbol.rsplit(".", 1)[0]
    if symbol.kind == "member":
        if symbol.language == "java":
            owner = java_member_owner(symbol)
        else:
            owner, _ = scala_member_owner_and_label(symbol)
        if "." in owner:
            return owner.rsplit(".", 1)[0]
    return "(root package)"


def type_anchor(symbol: JvmDocSymbolLifecycle) -> str:
    return f"type-{slugify(symbol.symbol)}"


def build_type_entries(
    artifact: JvmDocArtifactLifecycle,
) -> list[dict[str, Any]]:
    type_symbols = sorted((symbol for symbol in artifact.symbols if symbol.kind == "type"), key=lambda symbol: symbol.symbol)
    member_symbols = [symbol for symbol in artifact.symbols if symbol.kind == "member"]
    type_by_symbol = {symbol.symbol: symbol for symbol in type_symbols}
    members_by_type: dict[str, list[JvmDocSymbolLifecycle]] = defaultdict(list)
    type_flags: dict[str, dict[str, bool]] = {
        symbol.symbol_key: {
            "deprecated": symbol.deprecated_version is not None,
            "removed": symbol.removed_version is not None,
        }
        for symbol in type_symbols
    }

    for member in member_symbols:
        if artifact.language == "java":
            owner = java_member_owner(member)
            type_symbol = type_by_symbol.get(owner)
            if type_symbol is None:
                continue
            members_by_type[type_symbol.symbol_key].append(member)
            if member.deprecated_version is not None:
                type_flags[type_symbol.symbol_key]["deprecated"] = True
            if member.removed_version is not None:
                type_flags[type_symbol.symbol_key]["removed"] = True
            continue

        owner, _ = scala_member_owner_and_label(member)
        best_match: JvmDocSymbolLifecycle | None = None
        best_length = -1
        for type_symbol in type_symbols:
            if owner == type_symbol.symbol or owner.startswith(type_symbol.symbol + "."):
                if len(type_symbol.symbol) > best_length:
                    best_match = type_symbol
                    best_length = len(type_symbol.symbol)
        if best_match is None:
            continue
        members_by_type[best_match.symbol_key].append(member)
        if member.deprecated_version is not None:
            type_flags[best_match.symbol_key]["deprecated"] = True
        if member.removed_version is not None:
            type_flags[best_match.symbol_key]["removed"] = True

    type_entries: list[dict[str, Any]] = []

    for type_symbol in type_symbols:
        upstream = latest_doc_link(type_symbol)
        type_members = sorted(members_by_type.get(type_symbol.symbol_key, []), key=lambda symbol: symbol.symbol)
        flags = type_flags[type_symbol.symbol_key]

        member_rows: list[list[str]] = []
        for member in type_members:
            if artifact.language == "java":
                member_label = java_member_label(member)
            else:
                _, member_label = scala_member_owner_and_label(member)
            upstream_link = latest_doc_link(member)
            member_rows.append(
                [
                    f"[Open]({upstream_link})" if upstream_link else "-",
                    f"`{md_code(member_label)}`",
                    format_lifecycle_value(member.introduced_version),
                    format_lifecycle_value(member.deprecated_version),
                    format_lifecycle_value(member.removed_version),
                ]
            )

        type_entries.append(
            {
                "anchor": type_anchor(type_symbol),
                "upstream": f"[Open]({upstream})" if upstream else "-",
                "type": f"`{md_code(type_symbol.symbol)}`",
                "type_text": type_symbol.symbol,
                "summary": md_text(type_symbol.latest_summary or ""),
                "introduced": format_lifecycle_value(type_symbol.introduced_version),
                "deprecated": format_lifecycle_value(type_symbol.deprecated_version),
                "removed": format_lifecycle_value(type_symbol.removed_version),
                "package": package_name_for_symbol(type_symbol),
                "symbol": type_symbol,
                "member_rows": member_rows,
                "has_deprecated": "true" if flags["deprecated"] else "false",
                "has_removed": "true" if flags["removed"] else "false",
            }
        )

    return type_entries


def build_package_rows_and_pages(
    artifact: JvmDocArtifactLifecycle,
    *,
    root: Path,
    details_dir: Path,
    artifact_page_path: Path,
) -> tuple[list[dict[str, str]], list[Page]]:
    type_entries = build_type_entries(artifact)
    package_pages_dir = details_dir / f"{slugify(artifact.artifact)}-packages"
    package_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in type_entries:
        package_groups[str(entry["package"])].append(entry)

    rows: list[dict[str, str]] = []
    pages: list[Page] = []

    for package_name in sorted(package_groups):
        package_entries = sorted(package_groups[package_name], key=lambda item: str(item["type_text"]))
        package_page_path = package_pages_dir / f"{slugify(package_name)}.mdx"

        introduced_count = sum(1 for entry in package_entries if entry["introduced"] != format_lifecycle_value(artifact.versions[0]))
        deprecated_count = sum(1 for entry in package_entries if entry["has_deprecated"] == "true")
        removed_count = sum(1 for entry in package_entries if entry["has_removed"] == "true")

        blocks: list[Any] = [
            Paragraph(f"Back to [artifact page]({relative_page_link(package_page_path, artifact_page_path)})."),
            Heading(2, "Package"),
            BulletList(
                items=[
                    f"Artifact: `{md_code(f'{artifact.group}:{artifact.artifact}')}`",
                    f"Language: `{md_code(artifact.language)}`",
                    f"Package: `{md_code(package_name)}`",
                    f"Types in package: `{len(package_entries)}`",
                ]
            ),
            Heading(2, "Type Reference"),
            Table(
                headers=["Type", "Upstream", "Summary", "Introduced", "Deprecated", "Removed"],
                rows=[
                    [
                        f"[`{md_code(str(entry['type_text']))}`](#{entry['anchor']})",
                        str(entry["upstream"]),
                        str(entry["summary"]),
                        str(entry["introduced"]),
                        str(entry["deprecated"]),
                        str(entry["removed"]),
                    ]
                    for entry in package_entries
                ],
            ),
        ]

        for entry in package_entries:
            symbol = entry["symbol"]
            blocks.extend(
                [
                    RawMarkdown(f'<a id="{entry["anchor"]}"></a>'),
                    Heading(2, f"`{md_code(symbol.symbol)}`"),
                    BulletList(
                        items=[
                            f"Introduced: {entry['introduced']}",
                            f"Deprecated: {entry['deprecated']}",
                            f"Removed: {entry['removed']}",
                        ]
                    ),
                ]
            )
            if entry["upstream"] != "-":
                blocks.append(Paragraph(f"Upstream docs: {entry['upstream']}"))
            if symbol.latest_signature:
                blocks.extend(
                    [
                        Paragraph("**Signature**"),
                        RawMarkdown(f"```text\n{symbol.latest_signature}\n```"),
                    ]
                )
            if symbol.latest_summary:
                blocks.extend([Paragraph("**Summary**"), Paragraph(md_text(symbol.latest_summary))])
            blocks.append(Paragraph("**Members**"))
            if entry["member_rows"]:
                blocks.append(
                    Table(
                        headers=["Docs", "Member", "Introduced", "Deprecated", "Removed"],
                        rows=entry["member_rows"],
                    )
                )
            else:
                blocks.append(Paragraph("No members found for this type in the configured artifacts."))

        pages.append(
            Page(
                path=page_path(root, package_page_path),
                title=package_name,
                description="Generated package reference page from local Javadoc/Scaladoc snapshots",
                blocks=blocks,
            )
        )
        rows.append(
            {
                "local": f"[Open]({relative_page_link(artifact_page_path, package_page_path)})",
                "package": f"`{md_code(package_name)}`",
                "types": f"`{len(package_entries)}`",
                "introduced": f"`{introduced_count}`",
                "deprecated": f"`{deprecated_count}`",
                "removed": f"`{removed_count}`",
            }
        )

    return rows, pages


def build_artifact_page(
    artifact: JvmDocArtifactLifecycle,
    *,
    root: Path,
    overview_output: Path,
    details_dir: Path,
) -> tuple[Page, list[Page]]:
    artifact_slug = slugify(artifact.artifact)
    artifact_page_path = details_dir / f"{artifact_slug}.mdx"
    package_rows, package_pages = build_package_rows_and_pages(
        artifact,
        root=root,
        details_dir=details_dir,
        artifact_page_path=artifact_page_path,
    )
    change_summary = summarize_changes(artifact)

    changed_rows = [
        [
            f"[Open]({latest_doc_link(symbol)})" if latest_doc_link(symbol) else "-",
            f"`{md_code(symbol.symbol)}`",
            f"`{md_code(symbol.kind)}`",
            format_lifecycle_value(symbol.introduced_version),
            format_lifecycle_value(symbol.deprecated_version),
            format_lifecycle_value(symbol.removed_version),
        ]
        for symbol in changed_symbols(artifact)
    ]

    blocks = [
        Paragraph(f"Back to [overview]({relative_page_link(artifact_page_path, overview_output)})."),
        Heading(2, "Artifact"),
        BulletList(
            items=[
                f"Group: `{md_code(artifact.group)}`",
                f"Artifact: `{md_code(artifact.artifact)}`",
                f"Language: `{md_code(artifact.language)}`",
                f"Versions: `{md_code(', '.join(artifact.versions))}`",
                f"Total symbols tracked: `{artifact.symbol_count}`",
                f"Types: `{artifact.type_count}`",
                f"Members: `{artifact.member_count}`",
            ]
        ),
        Heading(2, "Lifecycle Summary"),
        BulletList(
            items=[
                f"Introduced in range: `{change_summary['introduced']}`",
                f"Deprecated in range: `{change_summary['deprecated']}`",
                f"Removed in range: `{change_summary['removed']}`",
            ]
        ),
        Heading(2, "Package Reference"),
        Table(
            headers=["Local Page", "Package", "Types", "Introduced", "Deprecated", "Removed"],
            rows=[
                [row["local"], row["package"], row["types"], row["introduced"], row["deprecated"], row["removed"]]
                for row in package_rows
            ],
        )
        if package_rows
        else Paragraph("No package-level symbols were found for this artifact."),
        Heading(2, "Changed Symbols"),
        Table(
            headers=["Docs", "Symbol", "Kind", "Introduced", "Deprecated", "Removed"],
            rows=changed_rows,
        )
        if changed_rows
        else Paragraph("No lifecycle changes were detected in the configured version range."),
    ]

    deprecations = [symbol for symbol in changed_symbols(artifact) if symbol.deprecated_version]
    if deprecations:
        blocks.extend(
            [
                Heading(2, "Deprecation Notes"),
                Table(
                    headers=["Symbol", "Deprecated", "Note"],
                    rows=[
                        [
                            f"`{md_code(symbol.symbol)}`",
                            format_lifecycle_value(symbol.deprecated_version),
                            md_text(symbol.deprecation_note or "-"),
                        ]
                        for symbol in deprecations
                    ],
                ),
            ]
        )

    if artifact.failures:
        blocks.extend(
            [
                Heading(2, "Input Failures"),
                Table(
                    headers=["Version", "Jar", "Error"],
                    rows=[
                        [
                            f"`{md_code(failure.get('version', '-'))}`",
                            f"`{md_code(failure.get('jar_path', '-'))}`",
                            md_text(failure.get("error", "-")),
                        ]
                        for failure in artifact.failures
                    ],
                ),
            ]
        )

    artifact_page = Page(
        path=page_path(root, artifact_page_path),
        title=f"{artifact.artifact} lifecycle",
        description="Generated lifecycle timeline and type index from local Javadoc/Scaladoc snapshots",
        blocks=blocks,
    )
    return artifact_page, package_pages


def build_pages(
    report: JvmDocLifecycleReport,
    *,
    overview_output: Path,
    details_dir: Path,
    overview_title: str = "JVM API Lifecycle",
) -> tuple[Path, list[Page]]:
    root = compute_output_root(overview_output, details_dir)
    pages: list[Page] = []

    artifact_pages: list[tuple[JvmDocArtifactLifecycle, Page]] = []
    extra_pages: list[Page] = []
    for artifact in report.artifacts:
        artifact_page, type_pages = build_artifact_page(
            artifact,
            root=root,
            overview_output=overview_output,
            details_dir=details_dir,
        )
        artifact_pages.append((artifact, artifact_page))
        extra_pages.extend(type_pages)

    overview_rows = []
    for artifact, artifact_page in artifact_pages:
        summary = summarize_changes(artifact)
        overview_rows.append(
            [
                f"[View]({relative_page_link(overview_output, root / artifact_page.path)})",
                f"`{md_code(f'{artifact.group}:{artifact.artifact}')}`",
                f"`{md_code(artifact.language)}`",
                f"`{md_code(', '.join(artifact.versions))}`",
                f"`{artifact.symbol_count}`",
                f"`{summary['introduced']}`",
                f"`{summary['deprecated']}`",
                f"`{summary['removed']}`",
            ]
        )

    overview_page = Page(
        path=page_path(root, overview_output),
        title=overview_title,
        description="Generated lifecycle timeline and reference pages for local Javadoc/Scaladoc artifacts",
        blocks=[
            Paragraph("This page is generated from supplied local Javadoc/Scaladoc jars."),
            Heading(2, "Source"),
            BulletList(
                items=[
                    f"Generated at (UTC): `{md_code(report.generated_at_utc)}`",
                    f"Source name: `{md_code(report.source_name)}`",
                    f"Version filter: `{md_code(report.version_filter)}`",
                    f"Artifacts: `{report.summary['artifact_count']}`",
                    f"Types: `{report.summary['type_count']}`",
                    f"Members: `{report.summary['member_count']}`",
                ]
            ),
            Heading(2, "Artifacts"),
            Table(
                headers=["Details", "Artifact", "Language", "Versions", "Symbols", "Introduced", "Deprecated", "Removed"],
                rows=overview_rows,
            ),
            Heading(2, "Notes"),
            BulletList(items=[md_text(note) for note in report.notes]),
        ],
    )

    pages.append(overview_page)
    pages.extend(page for _, page in artifact_pages)
    pages.extend(extra_pages)
    return root, pages
