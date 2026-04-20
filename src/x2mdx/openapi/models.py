"""Format-specific input-side models for OpenAPI processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OpenApiLifecycleConfig:
    roots: list[str]
    include_spec_patterns: list[str] = field(default_factory=list)
    canonical_path_map: dict[str, str] = field(default_factory=dict)
    priority_prefixes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class OpenApiSourceSnapshot:
    version: str
    source_path: str
    document: dict[str, Any]


@dataclass(frozen=True)
class OpenApiEntityLifecycle:
    entity_key: str
    entity_type: str
    name: str
    introduced_version: str
    changed_in_versions: list[str]
    removed_version: str | None
    versions_present: list[str]
    latest: dict[str, Any]


@dataclass(frozen=True)
class OpenApiSpecLifecycle:
    spec_id: str
    display_name: str
    latest_source_path: str
    aliases: list[str]
    introduced_version: str
    changed_in_versions: list[str]
    removed_version: str | None
    versions_present: list[str]
    latest_version: str
    latest_openapi_version: str | None
    info_title: str | None
    version_snapshots: dict[str, dict[str, Any]]
    entity_count: int
    entity_lifecycle: list[OpenApiEntityLifecycle]
    latest_entities: dict[str, list[dict[str, Any]]]
    latest_operation_details: list[dict[str, Any]]
    operation_details_by_version: dict[str, dict[str, dict[str, Any]]]
    per_version_entity_deltas: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class OpenApiLifecycleReport:
    source_name: str
    tag_filter: str
    tags: list[str]
    summary: dict[str, int]
    notes: list[str]
    specs: list[OpenApiSpecLifecycle]
