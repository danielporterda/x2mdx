# x2mdx

`x2mdx` is a Python tool for converting reference-doc source artifacts into MDX.

Architectural boundary:

- `x2mdx` core takes supplied artifacts and emits lifecycle/MDX output.
- fetching and published-doc extraction live in harnesses outside the core transform path.

Current implementation priority:

- `JVM docs (Javadoc/Scaladoc) -> MDX`
- `DAML JSON -> MDX`
- `protobuf descriptor images -> MDX`
- `TypeDoc JSON -> MDX`
- `AsyncAPI -> MDX`
- `OpenRPC -> MDX`

The tool is designed around:

- format-specific input models and parsers
- shared output-side page/block data structures
- reusable MDX rendering utilities
- version-aware lifecycle diffing where the source format supports it

## CLI

```bash
x2mdx list-formats
x2mdx jvm-docs build-api-pages-from-manifest --manifest fixtures/jvm-docs.json --overview-file ./out/jvm/index.mdx --details-dir ./out/jvm/details
x2mdx daml-json build-api-pages-from-manifest --manifest fixtures/daml.json --output-dir ./out/daml
x2mdx protobuf build-api-pages-from-manifest --manifest fixtures/protobuf.json --output-dir ./out/protobuf
x2mdx typedoc build-api-pages-from-manifest --manifest fixtures/typedoc.json --output-file ./out/typescript.mdx
x2mdx asyncapi build-api-pages-from-manifest --manifest fixtures/asyncapi.json --output-file ./out/asyncapi.mdx
x2mdx openrpc build-api-pages-from-manifest --manifest fixtures/openrpc.json --output-dir ./out/openrpc
```

Run the tool through the pinned shell so `python`, `pytest`, and `x2mdx` all come from the same environment:

```bash
direnv allow
direnv exec . x2mdx list-formats
direnv exec . pytest
```

## JVM Docs

`jvm-docs build-api-pages-from-manifest` consumes a local manifest of Javadoc/Scaladoc jars and renders:

- one overview page
- one artifact page per configured jar family
- one type page per discovered type

The intended split is:

- downstream docs repos fetch or cache jars and write manifests
- `x2mdx` parses those supplied local jars and renders MDX

## Daml JSON Docs

`daml-json build-api-pages-from-manifest` consumes a local manifest of versioned Daml docs JSON snapshots and renders:

- one overview page
- one page per published module in the selected publish version
- lifecycle metadata for introduced, deprecated, and removed modules

The intended split is:

- downstream docs repos invoke `damlc docs` or equivalent SDK-local tooling and cache the JSON
- `x2mdx` turns those supplied snapshots into MDX and lifecycle summaries

## Protobuf Docs

`protobuf build-api-pages-from-manifest` consumes a local manifest of descriptor images plus import-path metadata and renders:

- one overview page
- one page per endpoint in the latest snapshot
- lifecycle history for endpoints, messages, enums, and files across versions

The intended split is:

- downstream docs repos clone/fetch the source repo, materialize descriptor images, and write the manifest
- `x2mdx` parses those supplied local descriptor artifacts and renders MDX

## TypeDoc Docs

`typedoc build-api-pages-from-manifest` consumes a local manifest of versioned TypeDoc JSON snapshots and renders:

- one generated MDX page for the selected package surface
- version-aware lifecycle metadata for introduced, changed, and removed exports
- grouped export reference sections based on the latest published snapshot

The intended split is:

- downstream docs repos fetch published npm tarballs or other package artifacts and run TypeDoc locally
- `x2mdx` consumes those supplied local TypeDoc JSON snapshots and renders MDX

## AsyncAPI Docs

`asyncapi build-api-pages-from-manifest` consumes a local manifest of versioned AsyncAPI snapshots and renders:

- one generated MDX page for the selected websocket surface
- version-aware lifecycle metadata for introduced, changed, and removed channels
- per-channel publish/subscribe message details, required fields, and example payloads

The intended split is:

- downstream docs repos fetch or materialize local `asyncapi.yaml` snapshots and write the manifest
- `x2mdx` consumes those supplied local AsyncAPI snapshots and renders MDX

## OpenRPC Docs

`openrpc build-api-pages-from-manifest` consumes a local manifest of versioned OpenRPC snapshots and renders:

- one overview page for the selected OpenRPC surfaces
- one page per spec in the selected publish version
- version-aware lifecycle metadata for introduced, changed, and removed JSON-RPC methods

The intended split is:

- downstream docs repos fetch or materialize local OpenRPC JSON snapshots and write the manifest
- `x2mdx` consumes those supplied local OpenRPC snapshots and renders MDX

## direnv / Nix

This repo includes [`flake.nix`](./flake.nix), [`flake.lock`](./flake.lock), [`.envrc`](./.envrc), and [`shell.nix`](./shell.nix) so the development shell is pinned and reproducible.

Activate it with:

```bash
direnv allow
direnv exec . x2mdx list-formats
direnv exec . pytest
```

The shell pins:

- Node 22 for Mintlify compatibility
- Python 3.12 plus the runtime and test dependencies used by `x2mdx`
- the `x2mdx` CLI itself, built from the checked-out source tree

GitHub Actions uses the same flake via `.github/workflows/ci.yml`, so local `direnv` and CI exercise the same bootstrap path.
