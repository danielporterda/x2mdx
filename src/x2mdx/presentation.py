"""Shared output-side presentation models for renderer refactors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from x2mdx.templating import compact_version_label, compact_version_sequence, render_status_badges, render_status_cell, render_status_legend


def _normalized_versions(values: Sequence[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in seen:
            seen.append(text)
    return tuple(seen)


def _normalized_state(value: str | None) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"alpha", "beta", "stable", "deprecated"}:
        return text
    return None


def _normalized_states(values: Sequence[str]) -> tuple[str, ...]:
    seen: list[str] = []
    for value in values:
        if text := _normalized_state(value):
            if text not in seen:
                seen.append(text)
    return tuple(seen)


@dataclass(frozen=True)
class LifecycleStatus:
    introduced: str | None = None
    changed_versions: tuple[str, ...] = field(default_factory=tuple)
    states: tuple[str, ...] = field(default_factory=tuple)
    deprecated: str | None = None
    removed: str | None = None

    @classmethod
    def from_values(
        cls,
        *,
        introduced: str | None = None,
        changed_versions: Sequence[str] = (),
        state: str | None = None,
        states: Sequence[str] = (),
        deprecated: str | None = None,
        removed: str | None = None,
    ) -> "LifecycleStatus":
        explicit_states: list[str] = list(states)
        if state:
            explicit_states.insert(0, state)
        return cls(
            introduced=introduced,
            changed_versions=_normalized_versions(changed_versions),
            states=_normalized_states(explicit_states),
            deprecated=deprecated,
            removed=removed,
        )

    @property
    def state(self) -> str | None:
        if len(self.states) == 1:
            return self.states[0]
        return None


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


def status_token_payloads(lifecycle: LifecycleStatus) -> tuple[dict[str, str], ...]:
    tokens: list[dict[str, str]] = []
    introduced_text = str(lifecycle.introduced or "").strip()
    deprecated_text = str(lifecycle.deprecated or "").strip()
    removed_text = str(lifecycle.removed or "").strip()
    if introduced_text and introduced_text != "-":
        tokens.append({"kind": "introduced", "label": compact_version_label(introduced_text)})
    changed_versions: list[str] = []
    for value in lifecycle.changed_versions:
        text = str(value).strip()
        if not text or text == "-" or text in {introduced_text, deprecated_text, removed_text}:
            continue
        if text not in changed_versions:
            changed_versions.append(text)
    if changed_versions:
        tokens.append({"kind": "changed", "label": compact_version_sequence(changed_versions)})
    for state in lifecycle.states:
        if state == "deprecated":
            continue
        tokens.append({"kind": state, "label": state})
    if deprecated_text and deprecated_text != "-":
        tokens.append({"kind": "deprecated", "label": compact_version_label(deprecated_text)})
    elif "deprecated" in lifecycle.states:
        tokens.append({"kind": "deprecated", "label": "deprecated"})
    if removed_text and removed_text != "-":
        tokens.append({"kind": "removed", "label": compact_version_label(removed_text)})
    return tuple(tokens)


def status_row_context(row: StatusRow) -> dict[str, object]:
    return {
        "link": row.link,
        "summary": row.summary,
        "status_tokens": list(status_token_payloads(row.lifecycle)),
    }


def status_legend_items(
    rows: Sequence[StatusRow],
    *,
    include_changed: bool = True,
    include_removed: bool = True,
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = [{"kind": "introduced", "label": "Active Since"}]
    states = {state for row in rows for state in row.lifecycle.states}
    if include_changed and any(row.lifecycle.changed_versions for row in rows):
        items.append({"kind": "changed", "label": "Changed"})
    for state in ("alpha", "beta", "stable"):
        if state in states:
            items.append({"kind": state, "label": state.capitalize()})
    if "deprecated" in states or any(str(row.lifecycle.deprecated or "").strip() for row in rows):
        items.append({"kind": "deprecated", "label": "Deprecated"})
    if include_removed and any(str(row.lifecycle.removed or "").strip() for row in rows):
        items.append({"kind": "removed", "label": "Removed"})
    return items


def version_delta_row_cells(row: VersionDeltaRow, *, include_active: bool = False) -> list[str]:
    cells: list[str] = [f"`{row.version}`"]
    if include_active:
        cells.append(row.active or "0")
    cells.extend([row.added, row.changed, row.removed])
    return cells
