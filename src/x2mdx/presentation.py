"""Shared output-side presentation models for renderer refactors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from x2mdx.templating import render_status_cell, render_status_legend


def _normalized_versions(values: Sequence[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.append(text)
    return tuple(seen)


@dataclass(frozen=True)
class LifecycleStatus:
    introduced: str | None = None
    changed_versions: tuple[str, ...] = field(default_factory=tuple)
    deprecated: str | None = None
    removed: str | None = None

    @classmethod
    def from_values(
        cls,
        *,
        introduced: str | None = None,
        changed_versions: Sequence[str] = (),
        deprecated: str | None = None,
        removed: str | None = None,
    ) -> "LifecycleStatus":
        return cls(
            introduced=introduced,
            changed_versions=_normalized_versions(changed_versions),
            deprecated=deprecated,
            removed=removed,
        )


@dataclass(frozen=True)
class StatusRow:
    link: str
    summary: str
    lifecycle: LifecycleStatus = field(default_factory=LifecycleStatus)


@dataclass(frozen=True)
class VersionDeltaRow:
    version: str
    added: str
    changed: str
    removed: str
    active: str | None = None


@dataclass(frozen=True)
class DetailParagraph:
    text: str
    title: str | None = None


@dataclass(frozen=True)
class DetailBulletList:
    items: tuple[str, ...]
    title: str | None = None


@dataclass(frozen=True)
class DetailTable:
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    title: str | None = None
    empty_message: str | None = None


@dataclass(frozen=True)
class DetailCodeBlock:
    language: str
    body: str
    title: str | None = None


@dataclass(frozen=True)
class DetailCallout:
    kind: str
    body: str


@dataclass(frozen=True)
class DetailAccordion:
    title: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class DetailCardGroup:
    cards: tuple[dict[str, str], ...]
    cols: int = 2


@dataclass(frozen=True)
class DetailRawMarkdown:
    text: str


DetailBlock = (
    DetailParagraph
    | DetailBulletList
    | DetailTable
    | DetailCodeBlock
    | DetailCallout
    | DetailAccordion
    | DetailCardGroup
    | DetailRawMarkdown
)


@dataclass(frozen=True)
class ProtocolInteraction:
    label: str
    detail_items: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""
    detail_blocks: tuple[DetailBlock, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProtocolSubject:
    anchor: str
    title: str
    kind: str = "-"
    summary: str = "-"
    lifecycle: LifecycleStatus = field(default_factory=LifecycleStatus)
    lifecycle_items: tuple[str, ...] = field(default_factory=tuple)
    description: str = ""
    version_changes: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    interactions: tuple[ProtocolInteraction, ...] = field(default_factory=tuple)
    detail_blocks: tuple[DetailBlock, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SymbolEntry:
    anchor: str
    title: str
    kind: str
    summary: str = ""
    lifecycle: LifecycleStatus = field(default_factory=LifecycleStatus)
    lifecycle_items: tuple[str, ...] = field(default_factory=tuple)
    source_link: str = ""
    signature: str = ""
    version_changes: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    detail_blocks: tuple[DetailBlock, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SymbolGroup:
    title: str
    entries: tuple[SymbolEntry, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CollectionPageModel:
    path: str
    title: str
    description: str | None = None
    intro_paragraphs: tuple[str, ...] = field(default_factory=tuple)
    metadata_items: tuple[str, ...] = field(default_factory=tuple)
    toc_rows: tuple[tuple[str, ...], ...] = field(default_factory=tuple)
    status_rows: tuple[StatusRow, ...] = field(default_factory=tuple)
    version_rows: tuple[VersionDeltaRow, ...] = field(default_factory=tuple)


def status_row_cells(row: StatusRow) -> list[str]:
    return [
        row.link,
        render_status_cell(
            introduced=row.lifecycle.introduced,
            changed=list(row.lifecycle.changed_versions),
            deprecated=row.lifecycle.deprecated,
            removed=row.lifecycle.removed,
        ),
        row.summary,
    ]


def status_legend(
    *,
    include_changed: bool = True,
    include_deprecated: bool = True,
    include_removed: bool = True,
) -> str:
    return render_status_legend(
        include_changed=include_changed,
        include_deprecated=include_deprecated,
        include_removed=include_removed,
    )


def version_delta_row_cells(row: VersionDeltaRow, *, include_active: bool = False) -> list[str]:
    cells: list[str] = [f"`{row.version}`"]
    if include_active:
        cells.append(row.active or "0")
    cells.extend([row.added, row.changed, row.removed])
    return cells
