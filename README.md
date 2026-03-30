# x2mdx

`x2mdx` is a Python tool for converting reference-doc source artifacts into MDX.

Architectural boundary:

- `x2mdx` core takes supplied artifacts and emits lifecycle/MDX output.
- fetching and published-doc extraction live in harnesses outside the core transform path.

Current implementation priority:

- `OpenAPI -> MDX`
- `JVM docs (Javadoc/Scaladoc) -> MDX`
- `DAML JSON -> MDX` later

The tool is designed around:

- format-specific input models and parsers
- shared output-side page/block data structures
- reusable MDX rendering utilities
- version-aware lifecycle diffing where the source format supports it

## CLI

```bash
x2mdx list-formats
x2mdx openapi build-api-pages-from-manifest --manifest fixtures/manifest.json --root published --output-dir ./out
x2mdx jvm-docs build-api-pages-from-manifest --manifest fixtures/jvm-docs.json --overview-file ./out/jvm/index.mdx --details-dir ./out/jvm/details
```

## OpenAPI Build Flags

OpenAPI API page building is CLI-driven. The build command accepts flags for:

- which path roots to strip when deriving normalized spec ids
- which normalized spec ids to include
- how moved or renamed spec paths are canonicalized
- which file paths win when multiple variants map to the same canonical spec id

These map to repeated CLI args such as:

- `--root`
- `--include-spec-pattern`
- `--canonical-path SOURCE=TARGET`
- `--priority-prefix`

## Published Ledger API Fixtures

The primary OpenAPI fixture set now comes from published JSON Ledger API OpenAPI pages on `docs.digitalasset.com`, captured into checked-in local fixtures under `/Users/danielporter/control/tests/fixtures/openapi/ledger_api/`.

Refresh them with:

```bash
direnv exec . python3 tests/harness/refresh_ledger_api_openapi_fixtures.py --captured-on 2026-03-25
```

The checked-in source set currently includes:

- `3.4`
- `3.5`

Build API pages from the stored `3.4`/`3.5` fixtures with:

```bash
direnv exec . x2mdx openapi build-api-pages-from-manifest \
  --manifest ./tests/fixtures/openapi/ledger_api/manifest.json \
  --root published \
  --include-spec-pattern '^json-ledger-api/openapi\.yaml$' \
  --output-dir ./out/ledger-api/pages \
  --version 3.4 \
  --version 3.5 \
  --source-name "docs.digitalasset.com JSON Ledger API OpenAPI fixtures" \
  --version-filter "published docs major versions"
```

`build-api-pages-from-manifest` is the only OpenAPI CLI build command exposed right now. It writes MDX pages directly; preview-site generation is not part of the public CLI surface at the moment.

## JVM Docs

`jvm-docs build-api-pages-from-manifest` consumes a local manifest of Javadoc/Scaladoc jars and renders:

- one overview page
- one artifact page per configured jar family
- one type page per discovered type

The intended split is:

- downstream docs repos fetch or cache jars and write manifests
- `x2mdx` parses those supplied local jars and renders MDX

## Running In `digital-asset/docs`

From inside `/Users/danielporter/control/docs`, you can write a single generated page into `docs-main/` and update `docs-main/docs.json` in one step:

```bash
PATH=/Users/danielporter/control/.venv/bin:$PATH \
x2mdx openapi build-api-pages-from-manifest \
  --manifest ../tests/fixtures/openapi/ledger_api/manifest.json \
  --root published \
  --include-spec-pattern '^json-ledger-api/openapi\.yaml$' \
  --version 3.4 \
  --version 3.5 \
  --output-file ./docs-main/appdev/reference/json-api-reference.mdx \
  --docs-json ./docs-main/docs.json \
  --nav-dropdown "App Development" \
  --nav-group "Reference" \
  --source-name "docs.digitalasset.com JSON Ledger API OpenAPI fixtures" \
  --version-filter "published docs major versions"
```

This mode is intended for downstream docs repos:

- `--output-file` writes one MDX page instead of an output directory tree
- `--docs-json` updates the Mintlify nav in place
- `--nav-dropdown` selects the dropdown to edit
- `--nav-version` can be repeated to target specific versions; if omitted, all versions under the dropdown are updated
- `--nav-group` can be repeated to create or target nested groups under that dropdown/version

## direnv / Nix

This repo now includes [.envrc](/Users/danielporter/control/.envrc) and [shell.nix](/Users/danielporter/control/shell.nix) so `direnv` can give you a Mintlify-compatible Node runtime.

Activate it with:

```bash
direnv allow
node -v
```

The shell pins Node 22, which works with Mintlify and avoids the local Node 25 incompatibility.
