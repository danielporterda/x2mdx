# x2mdx

`x2mdx` is a Python tool for converting reference-doc source artifacts into MDX.

Architectural boundary:

- `x2mdx` core takes supplied artifacts and emits lifecycle/MDX output.
- fetching and published-doc extraction live in harnesses outside the core transform path.

Current implementation priority:

- `OpenAPI -> MDX`
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

The primary OpenAPI fixture set now comes from published JSON Ledger API OpenAPI pages on `docs.digitalasset.com`, captured into checked-in local fixtures under `tests/fixtures/openapi/ledger_api/`.

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

## Running In `digital-asset/docs`

If `x2mdx` is on your `PATH`, you can run it from inside a downstream docs repo and write a single generated page into `docs-main/` while updating `docs-main/docs.json` in one step:

```bash
x2mdx openapi build-api-pages-from-manifest \
  --manifest /path/to/x2mdx/tests/fixtures/openapi/ledger_api/manifest.json \
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

This repo includes `.envrc` and `shell.nix` so `direnv` can give you a Mintlify-compatible Node runtime.

Activate it with:

```bash
direnv allow
node -v
```

The shell pins Node 22, which works with Mintlify and avoids the local Node 25 incompatibility.
