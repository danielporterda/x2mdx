"""Serialize and deserialize OpenAPI lifecycle models."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from x2mdx.openapi.models import (
    OpenApiEntityLifecycle,
    OpenApiLifecycleReport,
    OpenApiSourceSnapshot,
    OpenApiSpecLifecycle,
)


def snapshot_from_json_data(data: dict[str, Any]) -> OpenApiSourceSnapshot:
    return OpenApiSourceSnapshot(
        version=data["version"],
        source_path=data["source_path"],
        document=dict(data["document"]),
    )


def report_to_json_data(report: OpenApiLifecycleReport) -> dict[str, Any]:
    return asdict(report)


def report_from_json_data(data: dict[str, Any]) -> OpenApiLifecycleReport:
    specs = [
        OpenApiSpecLifecycle(
            spec_id=spec["spec_id"],
            display_name=spec["display_name"],
            latest_source_path=spec["latest_source_path"],
            aliases=list(spec.get("aliases", [])),
            introduced_version=spec["introduced_version"],
            changed_in_versions=list(spec.get("changed_in_versions", [])),
            removed_version=spec.get("removed_version"),
            versions_present=list(spec.get("versions_present", [])),
            latest_version=spec["latest_version"],
            latest_openapi_version=spec.get("latest_openapi_version"),
            info_title=spec.get("info_title"),
            version_snapshots=dict(spec.get("version_snapshots", {})),
            entity_count=int(spec.get("entity_count", 0)),
            entity_lifecycle=[
                OpenApiEntityLifecycle(
                    entity_key=entity["entity_key"],
                    entity_type=entity["entity_type"],
                    name=entity["name"],
                    introduced_version=entity["introduced_version"],
                    changed_in_versions=list(entity.get("changed_in_versions", [])),
                    removed_version=entity.get("removed_version"),
                    versions_present=list(entity.get("versions_present", [])),
                    latest=dict(entity.get("latest", {})),
                )
                for entity in spec.get("entity_lifecycle", [])
            ],
            latest_entities={
                key: list(value)
                for key, value in dict(spec.get("latest_entities", {})).items()
            },
            latest_operation_details=list(spec.get("latest_operation_details", [])),
            operation_details_by_version={
                version: {
                    entity_key: dict(details)
                    for entity_key, details in dict(version_details).items()
                }
                for version, version_details in dict(spec.get("operation_details_by_version", {})).items()
            },
            per_version_entity_deltas=dict(spec.get("per_version_entity_deltas", {})),
        )
        for spec in data.get("specs", [])
    ]

    return OpenApiLifecycleReport(
        generated_at_utc=data["generated_at_utc"],
        source_name=data["source_name"],
        tag_filter=data["tag_filter"],
        tags=list(data.get("tags", [])),
        summary=dict(data.get("summary", {})),
        notes=list(data.get("notes", [])),
        specs=specs,
    )
