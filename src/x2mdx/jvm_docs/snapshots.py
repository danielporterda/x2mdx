"""Load supplied JVM doc snapshots from local manifests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from x2mdx.jvm_docs.lifecycle import version_key
from x2mdx.jvm_docs.models import JvmDocArtifactSource, JvmDocVersionSource

DEFAULT_LIFECYCLE_MANIFEST = {
    "schemaVersion": 1,
    "symbols": {},
}


def _load_data(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(raw)
    return yaml.safe_load(raw)


def _load_lifecycle_manifest(path: Path | None) -> dict[str, object]:
    data = json.loads(json.dumps(DEFAULT_LIFECYCLE_MANIFEST))
    if path is None or not path.exists():
        return data
    raw = _load_data(path)
    if not isinstance(raw, dict):
        return data
    symbols = raw.get("symbols")
    if isinstance(symbols, dict):
        data["symbols"] = symbols
    schema_version = raw.get("schemaVersion")
    if isinstance(schema_version, int):
        data["schemaVersion"] = schema_version
    return data


def load_jvm_doc_manifest(path: Path) -> dict[str, Any]:
    data = _load_data(path)
    if not isinstance(data, dict):
        raise ValueError("JVM doc manifest must be a JSON/YAML object")
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        raise ValueError("JVM doc manifest must include an `artifacts` list")
    return data


def load_jvm_doc_sources(
    manifest_path: Path,
    *,
    fixture_root: Path | None = None,
    include_versions: set[str] | None = None,
) -> list[JvmDocArtifactSource]:
    manifest = load_jvm_doc_manifest(manifest_path)
    root = fixture_root or manifest_path.parent

    artifact_sources: list[JvmDocArtifactSource] = []
    for entry in manifest["artifacts"]:
        if not isinstance(entry, dict):
            continue

        group = entry.get("group")
        artifact = entry.get("artifact")
        language = entry.get("language")
        versions = entry.get("versions")
        include_prefixes = entry.get("include_prefixes") or []
        lifecycle_manifest_path = entry.get("lifecycle_manifest_path")
        if not isinstance(group, str) or not group:
            continue
        if not isinstance(artifact, str) or not artifact:
            continue
        if language not in {"java", "scala"}:
            continue
        if not isinstance(versions, list):
            continue

        version_sources: list[JvmDocVersionSource] = []
        for version_entry in versions:
            if not isinstance(version_entry, dict):
                continue
            version = version_entry.get("version")
            jar_path = version_entry.get("jar_path")
            if not isinstance(version, str) or not version:
                continue
            if include_versions is not None and version not in include_versions:
                continue
            if not isinstance(jar_path, str) or not jar_path:
                continue
            version_sources.append(
                JvmDocVersionSource(
                    version=version,
                    jar_path=str((root / jar_path).resolve()),
                )
            )

        if not version_sources:
            continue

        resolved_lifecycle_manifest_path: Path | None = None
        if isinstance(lifecycle_manifest_path, str) and lifecycle_manifest_path:
            resolved_lifecycle_manifest_path = Path(lifecycle_manifest_path)
            if not resolved_lifecycle_manifest_path.is_absolute():
                resolved_lifecycle_manifest_path = root / resolved_lifecycle_manifest_path

        version_sources.sort(key=lambda source: version_key(source.version))
        artifact_sources.append(
            JvmDocArtifactSource(
                group=group,
                artifact=artifact,
                language=language,
                include_prefixes=[str(prefix) for prefix in include_prefixes if isinstance(prefix, str)],
                versions=version_sources,
                lifecycle_manifest=_load_lifecycle_manifest(resolved_lifecycle_manifest_path),
            )
        )

    artifact_sources.sort(key=lambda source: (source.group, source.artifact, source.language))
    return artifact_sources
