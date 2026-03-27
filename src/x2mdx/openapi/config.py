"""Build and validate OpenAPI lifecycle config."""

from __future__ import annotations

from x2mdx.openapi.models import OpenApiLifecycleConfig


def _parse_mapping_entries(values: list[str], field_name: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for value in values:
        key, separator, mapped = value.partition("=")
        if not separator or not key or not mapped:
            raise ValueError(f"`{field_name}` entries must use SOURCE=TARGET format")
        out[key] = mapped
    return out


def build_openapi_lifecycle_config(
    *,
    roots: list[str],
    include_spec_patterns: list[str] | None = None,
    canonical_path_entries: list[str] | None = None,
    priority_prefixes: list[str] | None = None,
) -> OpenApiLifecycleConfig:
    if not roots or not all(isinstance(item, str) and item for item in roots):
        raise ValueError("`roots` must be a non-empty list of strings")

    return OpenApiLifecycleConfig(
        roots=list(roots),
        include_spec_patterns=list(include_spec_patterns or []),
        canonical_path_map=_parse_mapping_entries(list(canonical_path_entries or []), "canonical_path_entries"),
        priority_prefixes=list(priority_prefixes or []),
    )
