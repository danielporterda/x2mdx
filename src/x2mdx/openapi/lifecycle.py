"""Build lifecycle metadata for OpenAPI specs across release tags."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import yaml

from x2mdx.openapi.models import (
    OpenApiEntityLifecycle,
    OpenApiLifecycleConfig,
    OpenApiLifecycleReport,
    OpenApiSourceSnapshot,
    OpenApiSpecLifecycle,
)

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
REQUEST_SAMPLE_MAX_DEPTH = 4
REQUEST_SAMPLE_MAX_PROPERTIES = 8


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def version_key(version: str) -> tuple[tuple[int, int | str], ...]:
    version_text = version[1:] if version.startswith("v") else version
    parts = re.split(r"[.\-+]", version_text)
    key: list[tuple[int, int | str]] = []
    for part in parts:
        if part.isdigit():
            key.append((0, int(part)))
        else:
            key.append((1, part))
    return tuple(key)

def parse_openapi(raw_text: str) -> dict[str, Any]:
    obj = yaml.safe_load(raw_text)
    if not isinstance(obj, dict):
        raise ValueError("OpenAPI document is not an object")
    if "openapi" not in obj:
        raise ValueError("Document does not contain top-level `openapi` key")
    return obj


def normalize_relative_path(path: str, roots: list[str]) -> str:
    for prefix in roots:
        marker = prefix.rstrip("/") + "/"
        if path.startswith(marker):
            return path[len(marker) :]
    return path


def canonical_spec_id(path: str, config: OpenApiLifecycleConfig) -> str:
    relative = normalize_relative_path(path, config.roots)
    return config.canonical_path_map.get(relative, relative)


def path_priority(path: str, prefixes: list[str]) -> int:
    for index, prefix in enumerate(prefixes):
        if path.startswith(prefix):
            return len(prefixes) - index
    return 0


def include_spec(spec_id: str, include_patterns: list[str]) -> bool:
    if not include_patterns:
        return True
    return any(re.search(pattern, spec_id) for pattern in include_patterns)


def entity_name(entity_type: str, key_parts: tuple[str, ...]) -> str:
    if entity_type == "operation":
        method, path = key_parts
        return f"{method.upper()} {path}"
    if entity_type == "path":
        return key_parts[0]
    if entity_type == "component":
        kind, name = key_parts
        return f"{kind}.{name}"
    if entity_type == "tag":
        return key_parts[0]
    return ":".join(key_parts)


def extract_entities(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    entities: dict[str, dict[str, Any]] = {}

    paths = doc.get("paths", {})
    if isinstance(paths, dict):
        for path in sorted(paths):
            path_item = paths[path]
            if not isinstance(path_item, dict):
                continue

            path_key = f"path::{path}"
            entities[path_key] = {
                "entity_key": path_key,
                "entity_type": "path",
                "name": entity_name("path", (path,)),
                "hash": sha256_json(path_item),
                "path": path,
            }

            for method in sorted(path_item):
                operation = path_item[method]
                method_name = str(method).lower()
                if method_name not in HTTP_METHODS or not isinstance(operation, dict):
                    continue
                operation_key = f"operation::{method_name.upper()}::{path}"
                entities[operation_key] = {
                    "entity_key": operation_key,
                    "entity_type": "operation",
                    "name": entity_name("operation", (method_name, path)),
                    "hash": sha256_json(operation),
                    "method": method_name.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId"),
                }

    components = doc.get("components", {})
    if isinstance(components, dict):
        for component_kind in sorted(components):
            component_map = components[component_kind]
            if not isinstance(component_map, dict):
                continue
            for component_name in sorted(component_map):
                component_value = component_map[component_name]
                component_key = f"component::{component_kind}::{component_name}"
                entities[component_key] = {
                    "entity_key": component_key,
                    "entity_type": "component",
                    "name": entity_name("component", (component_kind, component_name)),
                    "hash": sha256_json(component_value),
                    "component_kind": component_kind,
                    "component_name": component_name,
                }

    tags = doc.get("tags", [])
    if isinstance(tags, list):
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            tag_name = tag.get("name")
            if not isinstance(tag_name, str) or not tag_name.strip():
                continue
            tag_key = f"tag::{tag_name}"
            entities[tag_key] = {
                "entity_key": tag_key,
                "entity_type": "tag",
                "name": entity_name("tag", (tag_name,)),
                "hash": sha256_json(tag),
                "tag_name": tag_name,
            }

    return entities


def resolve_local_ref(doc: dict[str, Any], node: Any, max_depth: int = 6) -> Any:
    current = node
    depth = 0
    while isinstance(current, dict) and "$ref" in current and depth < max_depth:
        ref = current["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            break
        target: Any = doc
        parts = ref[2:].split("/")
        valid = True
        for part in parts:
            if isinstance(target, dict) and part in target:
                target = target[part]
            else:
                valid = False
                break
        if not valid:
            break
        current = target
        depth += 1
    return current


def schema_brief(doc: dict[str, Any], schema: Any) -> str:
    resolved = resolve_local_ref(doc, schema)
    if not isinstance(resolved, dict):
        return "-"

    type_name = resolved.get("type")
    if isinstance(type_name, str):
        if type_name == "array":
            return f"array[{schema_brief(doc, resolved.get('items'))}]"
        return type_name

    if isinstance(resolved.get("oneOf"), list):
        return "oneOf"
    if isinstance(resolved.get("anyOf"), list):
        return "anyOf"
    if isinstance(resolved.get("allOf"), list):
        return "allOf"
    if isinstance(resolved.get("properties"), dict):
        return "object"
    return "-"


def object_schema_properties_and_required(
    doc: dict[str, Any],
    schema: Any,
    *,
    max_depth: int = 6,
) -> tuple[dict[str, Any], set[str]]:
    if max_depth <= 0:
        return {}, set()

    resolved = resolve_local_ref(doc, schema)
    if not isinstance(resolved, dict):
        return {}, set()

    properties: dict[str, Any] = {}
    required: set[str] = set()

    all_of = resolved.get("allOf")
    if isinstance(all_of, list):
        for item in all_of:
            item_properties, item_required = object_schema_properties_and_required(
                doc,
                item,
                max_depth=max_depth - 1,
            )
            properties.update(item_properties)
            required.update(item_required)

    raw_properties = resolved.get("properties")
    if isinstance(raw_properties, dict):
        properties.update(raw_properties)

    raw_required = resolved.get("required")
    if isinstance(raw_required, list):
        required.update(str(name) for name in raw_required if isinstance(name, str))

    return properties, required


def schema_required_field_names(doc: dict[str, Any], schema: Any) -> list[str]:
    properties, required = object_schema_properties_and_required(doc, schema)
    if not required:
        return []

    known = sorted(name for name in required if name in properties)
    unknown = sorted(name for name in required if name not in properties)
    return [*known, *unknown]


def schema_type_token(doc: dict[str, Any], schema: Any) -> Any:
    resolved = resolve_local_ref(doc, schema)
    if not isinstance(resolved, dict):
        return "<value>"

    one_of = resolved.get("oneOf")
    if isinstance(one_of, list) and one_of:
        return schema_type_token(doc, one_of[0])

    any_of = resolved.get("anyOf")
    if isinstance(any_of, list) and any_of:
        return schema_type_token(doc, any_of[0])

    type_name = resolved.get("type")
    if type_name == "string":
        return "<string>"
    if type_name == "integer":
        return "<integer>"
    if type_name == "number":
        return "<number>"
    if type_name == "boolean":
        return "<boolean>"
    if type_name == "array":
        return [schema_type_token(doc, resolved.get("items"))]

    properties, _required = object_schema_properties_and_required(doc, resolved)
    if type_name == "object" or properties or isinstance(resolved.get("allOf"), list):
        return "<object>"

    return "<value>"


def schema_sample_value(
    doc: dict[str, Any],
    schema: Any,
    *,
    max_depth: int = REQUEST_SAMPLE_MAX_DEPTH,
    max_properties: int = REQUEST_SAMPLE_MAX_PROPERTIES,
    required_only: bool = True,
    seen_refs: set[str] | None = None,
) -> Any:
    if max_depth <= 0:
        return schema_type_token(doc, schema)

    if seen_refs is None:
        seen_refs = set()

    if isinstance(schema, dict):
        ref = schema.get("$ref")
        if isinstance(ref, str):
            if ref in seen_refs:
                return schema_type_token(doc, schema)
            return schema_sample_value(
                doc,
                resolve_local_ref(doc, schema),
                max_depth=max_depth,
                max_properties=max_properties,
                required_only=required_only,
                seen_refs=seen_refs | {ref},
            )

    resolved = resolve_local_ref(doc, schema)
    if not isinstance(resolved, dict):
        return schema_type_token(doc, schema)

    one_of = resolved.get("oneOf")
    if isinstance(one_of, list) and one_of:
        return schema_sample_value(
            doc,
            one_of[0],
            max_depth=max_depth,
            max_properties=max_properties,
            required_only=required_only,
            seen_refs=seen_refs,
        )

    any_of = resolved.get("anyOf")
    if isinstance(any_of, list) and any_of:
        return schema_sample_value(
            doc,
            any_of[0],
            max_depth=max_depth,
            max_properties=max_properties,
            required_only=required_only,
            seen_refs=seen_refs,
        )

    properties, required = object_schema_properties_and_required(doc, resolved, max_depth=max_depth)
    type_name = resolved.get("type")
    if type_name == "object" or properties or isinstance(resolved.get("allOf"), list):
        property_names = list(properties.keys())
        required_names = [name for name in property_names if name in required]
        optional_names = [name for name in property_names if name not in required]
        unknown_required_names = sorted(name for name in required if name not in properties)

        names_to_render = required_names if required_only and required_names else property_names
        if not names_to_render and unknown_required_names:
            names_to_render = unknown_required_names

        names_to_render = names_to_render[:max_properties]

        sample: dict[str, Any] = {}
        for name in names_to_render:
            if name in properties:
                sample[name] = schema_sample_value(
                    doc,
                    properties[name],
                    max_depth=max_depth - 1,
                    max_properties=max_properties,
                    required_only=required_only,
                    seen_refs=seen_refs,
                )
            else:
                sample[name] = "<value>"
        return sample

    if type_name == "array":
        return [
            schema_sample_value(
                doc,
                resolved.get("items"),
                max_depth=max_depth - 1,
                max_properties=max_properties,
                required_only=required_only,
                seen_refs=seen_refs,
            )
        ]

    if type_name == "string":
        return "<string>"
    if type_name == "integer":
        return "<integer>"
    if type_name == "number":
        return "<number>"
    if type_name == "boolean":
        return "<boolean>"

    return schema_type_token(doc, resolved)


def extract_latest_operation_details(doc: dict[str, Any]) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    paths = doc.get("paths", {})
    if not isinstance(paths, dict):
        return operations

    for path in sorted(paths):
        path_item = paths[path]
        if not isinstance(path_item, dict):
            continue

        path_parameters = path_item.get("parameters", [])
        if not isinstance(path_parameters, list):
            path_parameters = []

        for method in sorted(path_item):
            operation = path_item[method]
            method_name = str(method).lower()
            if method_name not in HTTP_METHODS or not isinstance(operation, dict):
                continue

            parameters: list[dict[str, Any]] = []
            operation_parameters = operation.get("parameters", [])
            if not isinstance(operation_parameters, list):
                operation_parameters = []

            for parameter in path_parameters + operation_parameters:
                resolved = resolve_local_ref(doc, parameter)
                if not isinstance(resolved, dict):
                    continue
                parameters.append(
                    {
                        "name": resolved.get("name"),
                        "in": resolved.get("in"),
                        "required": bool(resolved.get("required", False)),
                        "description": resolved.get("description", ""),
                        "schema": schema_brief(doc, resolved.get("schema")),
                    }
                )

            request_body: dict[str, Any] = {}
            raw_request_body = operation.get("requestBody")
            if raw_request_body is not None:
                resolved_request_body = resolve_local_ref(doc, raw_request_body)
                if isinstance(resolved_request_body, dict):
                    content = resolved_request_body.get("content", {})
                    content_types: list[str] = []
                    schema_by_content_type: dict[str, str] = {}
                    required_fields_by_content_type: dict[str, list[str]] = {}
                    sample_by_content_type: dict[str, Any] = {}
                    if isinstance(content, dict):
                        for content_type in sorted(content):
                            content_types.append(content_type)
                            media_type = content[content_type]
                            if isinstance(media_type, dict):
                                schema = media_type.get("schema")
                                schema_by_content_type[content_type] = schema_brief(doc, schema)
                                required_fields_by_content_type[content_type] = schema_required_field_names(doc, schema)
                                sample_by_content_type[content_type] = schema_sample_value(doc, schema)
                            else:
                                schema_by_content_type[content_type] = "-"
                                required_fields_by_content_type[content_type] = []
                                sample_by_content_type[content_type] = "..."
                    request_body = {
                        "required": bool(resolved_request_body.get("required", False)),
                        "content_types": content_types,
                        "schema_by_content_type": schema_by_content_type,
                        "required_fields_by_content_type": required_fields_by_content_type,
                        "sample_by_content_type": sample_by_content_type,
                    }

            responses: list[dict[str, Any]] = []
            raw_responses = operation.get("responses", {})
            if isinstance(raw_responses, dict):
                for code in sorted(raw_responses):
                    response = resolve_local_ref(doc, raw_responses[code])
                    if not isinstance(response, dict):
                        continue
                    content = response.get("content", {})
                    content_types: list[str] = []
                    schema_by_content_type: dict[str, str] = {}
                    if isinstance(content, dict):
                        for content_type in sorted(content):
                            content_types.append(content_type)
                            media_type = content[content_type]
                            if isinstance(media_type, dict):
                                schema_by_content_type[content_type] = schema_brief(doc, media_type.get("schema"))
                            else:
                                schema_by_content_type[content_type] = "-"
                    responses.append(
                        {
                            "code": code,
                            "description": response.get("description", ""),
                            "content_types": content_types,
                            "schema_by_content_type": schema_by_content_type,
                        }
                    )

            tags = operation.get("tags", [])
            if not isinstance(tags, list):
                tags = []

            operations.append(
                {
                    "entity_key": f"operation::{method_name.upper()}::{path}",
                    "method": method_name.upper(),
                    "path": path,
                    "operation_id": operation.get("operationId"),
                    "summary": operation.get("summary", ""),
                    "description": operation.get("description", ""),
                    "tags": [str(tag) for tag in tags],
                    "parameters": parameters,
                    "request_body": request_body,
                    "responses": responses,
                }
            )

    return operations


def extract_operation_details_by_key(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(operation["entity_key"]): dict(operation)
        for operation in extract_latest_operation_details(doc)
    }


def pick_spec_variant(
    existing: dict[str, Any],
    candidate: dict[str, Any],
    config: OpenApiLifecycleConfig,
) -> dict[str, Any]:
    if existing["spec_hash"] == candidate["spec_hash"]:
        existing["aliases"] = sorted(set(existing.get("aliases", []) + [candidate["source_path"]]))
        return existing

    keep = existing
    other = candidate
    if path_priority(candidate["source_path"], config.priority_prefixes) > path_priority(
        existing["source_path"],
        config.priority_prefixes,
    ):
        keep, other = candidate, existing

    keep["aliases"] = sorted(set(keep.get("aliases", []) + [keep["source_path"], other["source_path"]]))
    keep.setdefault("shadowed_variants", []).append(
        {
            "source_path": other["source_path"],
            "spec_hash": other["spec_hash"],
            "info_title": other.get("info_title"),
        }
    )
    return keep


def next_tag_after(tags: list[str], tag: str) -> str | None:
    index = tags.index(tag)
    if index + 1 < len(tags):
        return tags[index + 1]
    return None


def entity_lifecycle_for_spec(spec_versions: dict[str, dict[str, Any]], tags: list[str]) -> list[OpenApiEntityLifecycle]:
    entity_keys: set[str] = set()
    for tag in tags:
        snapshot = spec_versions.get(tag)
        if snapshot:
            entity_keys.update(snapshot["entities"].keys())

    rows: list[OpenApiEntityLifecycle] = []
    for entity_key in sorted(entity_keys):
        versions_present = [tag for tag in tags if tag in spec_versions and entity_key in spec_versions[tag]["entities"]]
        if not versions_present:
            continue

        changed_in_versions: list[str] = []
        previous_hash: str | None = None
        for tag in versions_present:
            current_hash = spec_versions[tag]["entities"][entity_key]["hash"]
            if previous_hash is not None and current_hash != previous_hash:
                changed_in_versions.append(tag)
            previous_hash = current_hash

        latest = spec_versions[versions_present[-1]]["entities"][entity_key]
        rows.append(
            OpenApiEntityLifecycle(
                entity_key=entity_key,
                entity_type=latest["entity_type"],
                name=latest["name"],
                introduced_version=versions_present[0],
                changed_in_versions=changed_in_versions,
                removed_version=next_tag_after(tags, versions_present[-1]),
                versions_present=versions_present,
                latest={key: value for key, value in latest.items() if key != "hash"},
            )
        )
    return rows


def per_version_entity_deltas(spec_versions: dict[str, dict[str, Any]], tags: list[str]) -> dict[str, dict[str, int | list[str]]]:
    deltas: dict[str, dict[str, int | list[str]]] = {}
    previous_entities: dict[str, dict[str, Any]] = {}

    for tag in tags:
        current_entities = spec_versions.get(tag, {}).get("entities", {})
        added = sorted(set(current_entities) - set(previous_entities))
        removed = sorted(set(previous_entities) - set(current_entities))
        changed = sorted(
            entity_key
            for entity_key in (set(current_entities) & set(previous_entities))
            if current_entities[entity_key]["hash"] != previous_entities[entity_key]["hash"]
        )
        if added or removed or changed:
            deltas[tag] = {
                "added_count": len(added),
                "removed_count": len(removed),
                "changed_count": len(changed),
                "added": added,
                "removed": removed,
                "changed": changed,
            }
        previous_entities = current_entities
    return deltas


def summarize_latest_entities(
    entity_records: list[OpenApiEntityLifecycle],
    latest_version: str,
) -> dict[str, list[dict[str, Any]]]:
    summary = {"operations": [], "components": [], "paths": [], "tags": []}
    for record in entity_records:
        if latest_version not in record.versions_present:
            continue
        row = {
            "entity_key": record.entity_key,
            "name": record.name,
            "introduced_version": record.introduced_version,
            "changed_in_versions": record.changed_in_versions,
            "removed_version": record.removed_version,
            "latest": record.latest,
        }
        if record.entity_type == "operation":
            summary["operations"].append(row)
        elif record.entity_type == "component":
            summary["components"].append(row)
        elif record.entity_type == "path":
            summary["paths"].append(row)
        elif record.entity_type == "tag":
            summary["tags"].append(row)

    for key in summary:
        summary[key].sort(key=lambda row: str(row["name"]))
    return summary


def snapshot_candidate(
    *,
    source_path: str,
    document: dict[str, Any],
    config: OpenApiLifecycleConfig,
) -> dict[str, Any] | None:
    spec_id = canonical_spec_id(source_path, config)
    if not include_spec(spec_id, config.include_spec_patterns):
        return None

    entities = extract_entities(document)
    info = document.get("info", {}) if isinstance(document.get("info"), dict) else {}
    return {
        "spec_id": spec_id,
        "source_path": source_path,
        "aliases": [source_path],
        "openapi_version": document.get("openapi"),
        "info_title": info.get("title"),
        "spec_hash": sha256_json(document),
        "entity_count": len(entities),
        "entities": entities,
        "doc": document,
    }


def build_openapi_lifecycle_report_from_snapshots(
    snapshots: list[OpenApiSourceSnapshot],
    config: OpenApiLifecycleConfig,
    *,
    source_name: str,
    version_filter: str = "provided snapshots",
) -> OpenApiLifecycleReport:
    tags = sorted({snapshot.version for snapshot in snapshots}, key=version_key)
    if not tags:
        raise RuntimeError("No OpenAPI snapshots were provided")

    spec_snapshots: dict[str, dict[str, dict[str, Any]]] = {}
    spec_docs: dict[str, dict[str, dict[str, Any]]] = {}

    snapshots_by_version: dict[str, dict[str, dict[str, Any]]] = {}
    for snapshot in snapshots:
        try:
            candidate = snapshot_candidate(
                source_path=snapshot.source_path,
                document=snapshot.document,
                config=config,
            )
        except ValueError:
            continue
        if candidate is None:
            continue

        version_snapshots = snapshots_by_version.setdefault(snapshot.version, {})
        spec_id = candidate["spec_id"]
        if spec_id in version_snapshots:
            version_snapshots[spec_id] = pick_spec_variant(version_snapshots[spec_id], candidate, config)
        else:
            version_snapshots[spec_id] = candidate

    for tag in tags:
        for spec_id, snapshot in snapshots_by_version.get(tag, {}).items():
            spec_snapshots.setdefault(spec_id, {})[tag] = {key: value for key, value in snapshot.items() if key != "doc"}
            spec_docs.setdefault(spec_id, {})[tag] = snapshot["doc"]

    specs: list[OpenApiSpecLifecycle] = []
    total_entities = 0
    total_entity_change_events = 0

    for spec_id in sorted(spec_snapshots):
        versions = spec_snapshots[spec_id]
        versions_present = [tag for tag in tags if tag in versions]
        if not versions_present:
            continue

        latest_version = versions_present[-1]
        latest_snapshot = versions[latest_version]
        latest_doc = spec_docs[spec_id][latest_version]

        changed_in_versions: list[str] = []
        previous_hash: str | None = None
        for tag in versions_present:
            current_hash = versions[tag]["spec_hash"]
            if previous_hash is not None and current_hash != previous_hash:
                changed_in_versions.append(tag)
            previous_hash = current_hash

        entity_records = entity_lifecycle_for_spec(versions, tags)
        total_entities += len(entity_records)
        total_entity_change_events += sum(len(record.changed_in_versions) for record in entity_records)

        version_snapshots = {
            tag: {
                "source_path": snapshot["source_path"],
                "aliases": snapshot.get("aliases", []),
                "openapi_version": snapshot.get("openapi_version"),
                "info_title": snapshot.get("info_title"),
                "spec_hash": snapshot.get("spec_hash"),
                "entity_count": snapshot.get("entity_count", 0),
                "shadowed_variants": snapshot.get("shadowed_variants", []),
            }
            for tag, snapshot in versions.items()
        }
        operation_details_by_version = {
            tag: extract_operation_details_by_key(spec_docs[spec_id][tag])
            for tag in versions_present
        }

        specs.append(
            OpenApiSpecLifecycle(
                spec_id=spec_id,
                display_name=latest_snapshot.get("info_title") or spec_id,
                latest_source_path=latest_snapshot["source_path"],
                aliases=sorted(set(latest_snapshot.get("aliases", []) + [latest_snapshot["source_path"]])),
                introduced_version=versions_present[0],
                changed_in_versions=changed_in_versions,
                removed_version=next_tag_after(tags, versions_present[-1]),
                versions_present=versions_present,
                latest_version=latest_version,
                latest_openapi_version=latest_snapshot.get("openapi_version"),
                info_title=latest_snapshot.get("info_title"),
                version_snapshots=version_snapshots,
                entity_count=len(entity_records),
                entity_lifecycle=entity_records,
                latest_entities=summarize_latest_entities(entity_records, latest_version),
                latest_operation_details=extract_latest_operation_details(latest_doc),
                operation_details_by_version=operation_details_by_version,
                per_version_entity_deltas=per_version_entity_deltas(versions, tags),
            )
        )

    return OpenApiLifecycleReport(
        source_name=source_name,
        tag_filter=version_filter,
        tags=tags,
        summary={
            "tag_count": len(tags),
            "spec_count": len(specs),
            "total_entities": total_entities,
            "total_entity_change_events": total_entity_change_events,
        },
        notes=[
            "Entity types tracked: path, operation, component, tag.",
            "changed_in_versions is computed by hash diff against the previous observed presence.",
            "removed_version is the first matching tag after the last observed presence.",
            "Input-side canonicalization and variant selection are config-driven.",
        ],
        specs=specs,
    )
