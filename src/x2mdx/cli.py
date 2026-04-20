"""CLI for x2mdx."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
import shutil


def add_openapi_config_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--root",
        action="append",
        required=True,
        help="Root prefix to strip when deriving spec ids. Repeat for multiple roots.",
    )
    parser.add_argument(
        "--include-spec-pattern",
        action="append",
        default=[],
        help="Regex for spec ids to include. Repeat for multiple patterns.",
    )
    parser.add_argument(
        "--canonical-path",
        action="append",
        default=[],
        help="Canonicalize a relative source path with SOURCE=TARGET. Repeat for multiple mappings.",
    )
    parser.add_argument(
        "--priority-prefix",
        action="append",
        default=[],
        help="Prefer source paths with this prefix when variants collide. Repeat for multiple prefixes.",
    )


def build_openapi_config_from_args(args: argparse.Namespace):
    from x2mdx.openapi.config import build_openapi_lifecycle_config

    return build_openapi_lifecycle_config(
        roots=args.root,
        include_spec_patterns=args.include_spec_pattern,
        canonical_path_entries=args.canonical_path,
        priority_prefixes=args.priority_prefix,
    )


def build_openapi_report_from_manifest_args(args: argparse.Namespace):
    from x2mdx.openapi.lifecycle import build_openapi_lifecycle_report_from_snapshots
    from x2mdx.openapi.snapshots import load_openapi_source_snapshots

    manifest_path = Path(args.manifest)
    include_versions = set(args.version) if args.version else None
    fixture_root = Path(args.fixture_root) if args.fixture_root else None
    snapshots = load_openapi_source_snapshots(
        manifest_path,
        fixture_root=fixture_root,
        include_versions=include_versions,
    )
    return build_openapi_lifecycle_report_from_snapshots(
        snapshots,
        build_openapi_config_from_args(args),
        source_name=args.source_name or str(manifest_path),
        version_filter=args.version_filter or ("selected manifest versions" if include_versions else "manifest versions"),
    )


def build_jvm_doc_report_from_manifest_args(args: argparse.Namespace):
    from x2mdx.jvm_docs.lifecycle import build_jvm_doc_lifecycle_report_from_sources
    from x2mdx.jvm_docs.snapshots import load_jvm_doc_sources

    manifest_path = Path(args.manifest)
    include_versions = set(args.version) if args.version else None
    fixture_root = Path(args.fixture_root) if args.fixture_root else None
    sources = load_jvm_doc_sources(
        manifest_path,
        fixture_root=fixture_root,
        include_versions=include_versions,
    )
    return build_jvm_doc_lifecycle_report_from_sources(
        sources,
        source_name=args.source_name or str(manifest_path),
        version_filter=args.version_filter or ("selected manifest versions" if include_versions else "manifest versions"),
    )


def build_daml_doc_report_from_manifest_args(args: argparse.Namespace):
    from x2mdx.daml_json.lifecycle import build_daml_doc_report_from_sources
    from x2mdx.daml_json.snapshots import load_daml_doc_sources

    manifest_path = Path(args.manifest)
    include_versions = set(args.version) if args.version else None
    fixture_root = Path(args.fixture_root) if args.fixture_root else None
    sources = load_daml_doc_sources(
        manifest_path,
        fixture_root=fixture_root,
        include_versions=include_versions,
    )
    return build_daml_doc_report_from_sources(
        sources,
        source_name=args.source_name or sources.source or str(manifest_path),
        version_filter=args.version_filter or ("selected manifest versions" if include_versions else "manifest versions"),
        publish_version=args.publish_version,
    )


def build_protobuf_report_from_manifest_args(args: argparse.Namespace):
    from x2mdx.protobuf.lifecycle import build_protobuf_history_report_from_sources
    from x2mdx.protobuf.snapshots import load_protobuf_sources

    manifest_path = Path(args.manifest)
    include_versions = set(args.version) if args.version else None
    fixture_root = Path(args.fixture_root) if args.fixture_root else None
    sources = load_protobuf_sources(
        manifest_path,
        fixture_root=fixture_root,
        include_versions=include_versions,
    )
    return build_protobuf_history_report_from_sources(
        sources,
        source_name=args.source_name or sources.source or str(manifest_path),
        version_filter=args.version_filter or ("selected manifest versions" if include_versions else "manifest versions"),
    )


def build_typedoc_report_from_manifest_args(args: argparse.Namespace):
    from x2mdx.typedoc.lifecycle import build_typedoc_report_from_sources
    from x2mdx.typedoc.snapshots import load_typedoc_sources

    manifest_path = Path(args.manifest)
    include_versions = set(args.version) if args.version else None
    fixture_root = Path(args.fixture_root) if args.fixture_root else None
    sources = load_typedoc_sources(
        manifest_path,
        fixture_root=fixture_root,
        include_versions=include_versions,
    )
    return build_typedoc_report_from_sources(
        sources,
        source_name=args.source_name or sources.source or str(manifest_path),
        version_filter=args.version_filter or ("selected manifest versions" if include_versions else "manifest versions"),
        publish_version=args.publish_version,
    )


def build_asyncapi_report_from_manifest_args(args: argparse.Namespace):
    from x2mdx.asyncapi.lifecycle import build_asyncapi_report_from_sources
    from x2mdx.asyncapi.snapshots import load_asyncapi_source_snapshots

    manifest_path = Path(args.manifest)
    include_versions = set(args.version) if args.version else None
    fixture_root = Path(args.fixture_root) if args.fixture_root else None
    sources = load_asyncapi_source_snapshots(
        manifest_path,
        fixture_root=fixture_root,
        include_versions=include_versions,
    )
    return build_asyncapi_report_from_sources(
        sources,
        source_name=args.source_name or str(manifest_path),
        version_filter=args.version_filter or ("selected manifest versions" if include_versions else "manifest versions"),
        publish_version=args.publish_version,
    )


def build_openrpc_report_from_manifest_args(args: argparse.Namespace):
    from x2mdx.openrpc.lifecycle import build_openrpc_report_from_sources
    from x2mdx.openrpc.snapshots import load_openrpc_source_snapshots

    manifest_path = Path(args.manifest)
    include_versions = set(args.version) if args.version else None
    fixture_root = Path(args.fixture_root) if args.fixture_root else None
    sources = load_openrpc_source_snapshots(
        manifest_path,
        fixture_root=fixture_root,
        include_versions=include_versions,
    )
    return build_openrpc_report_from_sources(
        sources,
        source_name=args.source_name or str(manifest_path),
        version_filter=args.version_filter or ("selected manifest versions" if include_versions else "manifest versions"),
        publish_version=args.publish_version,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="x2mdx")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-formats", help="List supported input formats")

    openapi = subparsers.add_parser("openapi", help="OpenAPI commands")
    openapi_subparsers = openapi.add_subparsers(dest="openapi_command", required=True)

    build_lifecycle = openapi_subparsers.add_parser(
        "build-api-pages-from-manifest",
        help="Build API MDX pages directly from local OpenAPI snapshots",
    )
    build_lifecycle.add_argument(
        "--manifest",
        required=True,
        help="Path to a JSON/YAML manifest that lists local OpenAPI snapshots",
    )
    add_openapi_config_args(build_lifecycle)
    build_lifecycle.add_argument(
        "--output-dir",
        help="Directory where MDX files should be written",
    )
    build_lifecycle.add_argument(
        "--output-file",
        help="Exact MDX file path to write when generating a single page",
    )
    build_lifecycle.add_argument(
        "--overview-name",
        default="overview.mdx",
        help="Filename for the overview page inside the output directory",
    )
    build_lifecycle.add_argument(
        "--spec-dir-name",
        default="specs",
        help="Directory name for per-spec pages inside the output directory.",
    )
    build_lifecycle.add_argument(
        "--overview-title",
        default="OpenAPI Lifecycle Overview",
        help="Title to use for the generated overview page.",
    )
    build_lifecycle.add_argument(
        "--link-prefix",
        help="Optional root-relative URL prefix to use for overview/spec links.",
    )
    build_lifecycle.add_argument(
        "--primary-spec-id",
        help="Optional spec id to promote to the top-level overview page.",
    )
    build_lifecycle.add_argument(
        "--fixture-root",
        help="Directory to resolve manifest fixture paths from; defaults to the manifest directory",
    )
    build_lifecycle.add_argument(
        "--version",
        action="append",
        default=[],
        help="Version to include from the manifest. Repeat to include multiple versions.",
    )
    build_lifecycle.add_argument(
        "--source-name",
        help="Optional source label to record in the lifecycle report",
    )
    build_lifecycle.add_argument(
        "--version-filter",
        help="Optional label describing the selected version set",
    )
    build_lifecycle.add_argument(
        "--docs-json",
        help="Optional docs.json file to update with the generated page; requires --output-file",
    )
    build_lifecycle.add_argument(
        "--nav-dropdown",
        help="Dropdown label in docs.json where the generated page should be inserted",
    )
    build_lifecycle.add_argument(
        "--nav-version",
        action="append",
        default=[],
        help="Version label under the selected dropdown to update. Repeat to target multiple versions. Defaults to all versions in the dropdown.",
    )
    build_lifecycle.add_argument(
        "--nav-group",
        action="append",
        default=[],
        help="Group label path under the selected dropdown/version where the page should be inserted. Repeat for nested groups.",
    )

    jvm_docs = subparsers.add_parser("jvm-docs", help="Javadoc/Scaladoc commands")
    jvm_docs_subparsers = jvm_docs.add_subparsers(dest="jvm_docs_command", required=True)

    build_jvm_docs = jvm_docs_subparsers.add_parser(
        "build-api-pages-from-manifest",
        help="Build JVM API lifecycle pages directly from local Javadoc/Scaladoc jars",
    )
    build_jvm_docs.add_argument(
        "--manifest",
        required=True,
        help="Path to a JSON/YAML manifest that lists local Javadoc/Scaladoc jars",
    )
    build_jvm_docs.add_argument(
        "--overview-file",
        required=True,
        help="Exact MDX file path to write for the overview page",
    )
    build_jvm_docs.add_argument(
        "--details-dir",
        required=True,
        help="Directory where artifact and type pages should be written",
    )
    build_jvm_docs.add_argument(
        "--fixture-root",
        help="Directory to resolve manifest jar paths from; defaults to the manifest directory",
    )
    build_jvm_docs.add_argument(
        "--version",
        action="append",
        default=[],
        help="Version to include from the manifest. Repeat to include multiple versions.",
    )
    build_jvm_docs.add_argument(
        "--source-name",
        help="Optional source label to record in the lifecycle report",
    )
    build_jvm_docs.add_argument(
        "--version-filter",
        help="Optional label describing the selected version set",
    )
    build_jvm_docs.add_argument(
        "--overview-title",
        default="JVM API Lifecycle",
        help="Title to use for the generated overview page.",
    )
    build_jvm_docs.add_argument(
        "--docs-json",
        help="Optional docs.json file to update with the generated overview page",
    )
    build_jvm_docs.add_argument(
        "--nav-dropdown",
        help="Dropdown label in docs.json where the generated overview page should be inserted",
    )
    build_jvm_docs.add_argument(
        "--nav-version",
        action="append",
        default=[],
        help="Version label under the selected dropdown to update. Repeat to target multiple versions. Defaults to all versions in the dropdown.",
    )
    build_jvm_docs.add_argument(
        "--nav-group",
        action="append",
        default=[],
        help="Group label path under the selected dropdown/version where the page should be inserted. Repeat for nested groups.",
    )

    daml_json = subparsers.add_parser("daml-json", help="Daml docs JSON commands")
    daml_json_subparsers = daml_json.add_subparsers(dest="daml_json_command", required=True)

    build_daml_json = daml_json_subparsers.add_parser(
        "build-api-pages-from-manifest",
        help="Build Daml docs MDX pages directly from local docs JSON snapshots",
    )
    build_daml_json.add_argument(
        "--manifest",
        required=True,
        help="Path to a JSON/YAML manifest that lists local Daml docs JSON snapshots",
    )
    build_daml_json.add_argument(
        "--output-dir",
        required=True,
        help="Directory where generated MDX pages should be written",
    )
    build_daml_json.add_argument(
        "--fixture-root",
        help="Directory to resolve manifest JSON paths from; defaults to the manifest directory",
    )
    build_daml_json.add_argument(
        "--version",
        action="append",
        default=[],
        help="Version to include from the manifest. Repeat to include multiple versions.",
    )
    build_daml_json.add_argument(
        "--publish-version",
        help="Version whose module tree should be published; defaults to the manifest or latest selected version.",
    )
    build_daml_json.add_argument(
        "--source-name",
        help="Optional source label to record in the generated pages.",
    )
    build_daml_json.add_argument(
        "--version-filter",
        help="Optional label describing the selected version set.",
    )
    build_daml_json.add_argument(
        "--overview-title",
        default="Daml Standard Library",
        help="Title to use for the generated overview page.",
    )
    build_daml_json.add_argument(
        "--link-prefix",
        help="Optional root-relative URL prefix to use for overview-page module links.",
    )

    protobuf = subparsers.add_parser("protobuf", help="Descriptor-backed protobuf commands")
    protobuf_subparsers = protobuf.add_subparsers(dest="protobuf_command", required=True)

    build_protobuf = protobuf_subparsers.add_parser(
        "build-api-pages-from-manifest",
        help="Build protobuf history and package pages directly from local descriptor-image snapshots",
    )
    build_protobuf.add_argument(
        "--manifest",
        required=True,
        help="Path to a JSON/YAML manifest that lists local protobuf descriptor-image snapshots",
    )
    build_protobuf.add_argument(
        "--output-dir",
        required=True,
        help="Directory where generated MDX pages should be written",
    )
    build_protobuf.add_argument(
        "--fixture-root",
        help="Directory to resolve manifest paths from; defaults to the manifest directory",
    )
    build_protobuf.add_argument(
        "--version",
        action="append",
        default=[],
        help="Version to include from the manifest. Repeat to include multiple versions.",
    )
    build_protobuf.add_argument(
        "--source-name",
        help="Optional source label to record in the generated pages.",
    )
    build_protobuf.add_argument(
        "--version-filter",
        help="Optional label describing the selected version set.",
    )

    typedoc = subparsers.add_parser("typedoc", help="TypeDoc-based TypeScript bindings commands")
    typedoc_subparsers = typedoc.add_subparsers(dest="typedoc_command", required=True)

    build_typedoc = typedoc_subparsers.add_parser(
        "build-api-pages-from-manifest",
        help="Build TypeScript bindings MDX directly from local TypeDoc JSON snapshots",
    )
    build_typedoc.add_argument(
        "--manifest",
        required=True,
        help="Path to a JSON/YAML manifest that lists local TypeDoc JSON snapshots",
    )
    build_typedoc.add_argument(
        "--output-file",
        required=True,
        help="Exact MDX file path to write for the generated TypeScript bindings page",
    )
    build_typedoc.add_argument(
        "--fixture-root",
        help="Directory to resolve manifest JSON paths from; defaults to the manifest directory",
    )
    build_typedoc.add_argument(
        "--version",
        action="append",
        default=[],
        help="Version to include from the manifest. Repeat to include multiple versions.",
    )
    build_typedoc.add_argument(
        "--publish-version",
        help="Version whose bindings surface should be published; defaults to the manifest or latest selected version.",
    )
    build_typedoc.add_argument(
        "--source-name",
        help="Optional source label to record in the generated page.",
    )
    build_typedoc.add_argument(
        "--version-filter",
        help="Optional label describing the selected version set.",
    )
    build_typedoc.add_argument(
        "--page-title",
        default="TypeScript/JavaScript",
        help="Title to use for the generated page.",
    )
    build_typedoc.add_argument(
        "--page-description",
        default="TypeScript and JavaScript language bindings for Canton.",
        help="Description to use for the generated page.",
    )

    asyncapi = subparsers.add_parser("asyncapi", help="AsyncAPI websocket commands")
    asyncapi_subparsers = asyncapi.add_subparsers(dest="asyncapi_command", required=True)

    build_asyncapi = asyncapi_subparsers.add_parser(
        "build-api-pages-from-manifest",
        help="Build AsyncAPI MDX directly from local AsyncAPI snapshots",
    )
    build_asyncapi.add_argument(
        "--manifest",
        required=True,
        help="Path to a JSON/YAML manifest that lists local AsyncAPI snapshots",
    )
    build_asyncapi.add_argument(
        "--output-file",
        required=True,
        help="Exact MDX file path to write for the generated AsyncAPI page",
    )
    build_asyncapi.add_argument(
        "--fixture-root",
        help="Directory to resolve manifest files from; defaults to the manifest directory",
    )
    build_asyncapi.add_argument(
        "--version",
        action="append",
        default=[],
        help="Version to include from the manifest. Repeat to include multiple versions.",
    )
    build_asyncapi.add_argument(
        "--publish-version",
        help="Version whose websocket surface should be published; defaults to the manifest or latest selected version.",
    )
    build_asyncapi.add_argument(
        "--source-name",
        help="Optional source label to record in the generated page.",
    )
    build_asyncapi.add_argument(
        "--version-filter",
        help="Optional label describing the selected version set.",
    )
    build_asyncapi.add_argument(
        "--page-title",
        default="AsyncAPI WebSocket Reference",
        help="Title to use for the generated page.",
    )
    build_asyncapi.add_argument(
        "--page-description",
        default="WebSocket AsyncAPI reference and version history.",
        help="Description to use for the generated page.",
    )
    build_asyncapi.add_argument(
        "--docs-json",
        help="Optional docs.json file to update with the generated page",
    )
    build_asyncapi.add_argument(
        "--nav-dropdown",
        help="Dropdown label in docs.json where the generated page should be inserted",
    )
    build_asyncapi.add_argument(
        "--nav-version",
        action="append",
        default=[],
        help="Version label under the selected dropdown to update. Repeat to target multiple versions. Defaults to all versions in the dropdown.",
    )
    build_asyncapi.add_argument(
        "--nav-group",
        action="append",
        default=[],
        help="Group label path under the selected dropdown/version where the page should be inserted. Repeat for nested groups.",
    )

    openrpc = subparsers.add_parser("openrpc", help="OpenRPC JSON-RPC commands")
    openrpc_subparsers = openrpc.add_subparsers(dest="openrpc_command", required=True)

    build_openrpc = openrpc_subparsers.add_parser(
        "build-api-pages-from-manifest",
        help="Build OpenRPC MDX pages directly from local OpenRPC snapshots",
    )
    build_openrpc.add_argument(
        "--manifest",
        required=True,
        help="Path to a JSON/YAML manifest that lists local OpenRPC snapshots",
    )
    build_openrpc.add_argument(
        "--output-dir",
        required=True,
        help="Directory where generated MDX pages should be written",
    )
    build_openrpc.add_argument(
        "--fixture-root",
        help="Directory to resolve manifest fixture paths from; defaults to the manifest directory",
    )
    build_openrpc.add_argument(
        "--version",
        action="append",
        default=[],
        help="Version to include from the manifest. Repeat to include multiple versions.",
    )
    build_openrpc.add_argument(
        "--publish-version",
        help="Version whose OpenRPC surface should be published; defaults to the manifest or latest selected version.",
    )
    build_openrpc.add_argument(
        "--source-name",
        help="Optional source label to record in the report",
    )
    build_openrpc.add_argument(
        "--version-filter",
        help="Optional label describing the selected version set.",
    )
    build_openrpc.add_argument(
        "--overview-name",
        default="index.mdx",
        help="Filename for the overview page inside the output directory",
    )
    build_openrpc.add_argument(
        "--spec-dir-name",
        default="specs",
        help="Directory name for per-spec pages inside the output directory.",
    )
    build_openrpc.add_argument(
        "--overview-title",
        default="Wallet Gateway OpenRPC",
        help="Title to use for the generated overview page.",
    )
    build_openrpc.add_argument(
        "--link-prefix",
        help="Optional root-relative URL prefix to use for overview/spec links.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list-formats":
        print("openapi")
        print("jvm-docs")
        print("daml-json")
        print("protobuf")
        print("typedoc")
        print("asyncapi")
        print("openrpc")
        return 0

    if args.command == "openapi":
        if args.openapi_command == "build-api-pages-from-manifest":
            from x2mdx.mintlify import MintlifyNavTarget, update_docs_json_navigation
            from x2mdx.openapi.render import build_api_page, build_pages
            from x2mdx.render import write_page, write_pages

            if not args.output_dir and not args.output_file:
                parser.error("build-api-pages-from-manifest requires --output-dir or --output-file")
            if args.output_dir and args.output_file:
                parser.error("build-api-pages-from-manifest accepts only one of --output-dir or --output-file")
            if args.docs_json and not args.output_file:
                parser.error("--docs-json requires --output-file")
            if (args.nav_dropdown or args.nav_version or args.nav_group) and not args.docs_json:
                parser.error("--nav-dropdown/--nav-version/--nav-group require --docs-json")
            if args.docs_json and not args.nav_dropdown:
                parser.error("--docs-json requires --nav-dropdown")

            report = build_openapi_report_from_manifest_args(args)
            if args.output_file:
                page = build_api_page(
                    report,
                    output_path=Path(args.output_file).name,
                    primary_spec_id=args.primary_spec_id,
                )
                output_file = Path(args.output_file)
                write_page(page, output_file)
                if args.docs_json:
                    update_docs_json_navigation(
                        Path(args.docs_json),
                        output_file=output_file,
                        target=MintlifyNavTarget(
                            dropdown=args.nav_dropdown,
                            versions=args.nav_version or None,
                            groups=args.nav_group,
                        ),
                    )
                return 0

            write_pages(
                build_pages(
                    report,
                    overview_name=args.overview_name,
                    spec_dir_name=args.spec_dir_name,
                    overview_title=args.overview_title,
                    link_prefix=args.link_prefix,
                    primary_spec_id=args.primary_spec_id,
                ),
                Path(args.output_dir),
            )
            return 0

    if args.command == "jvm-docs":
        if args.jvm_docs_command == "build-api-pages-from-manifest":
            from x2mdx.jvm_docs.render import build_pages
            from x2mdx.mintlify import MintlifyNavTarget, update_docs_json_navigation
            from x2mdx.render import write_pages

            if (args.nav_dropdown or args.nav_version or args.nav_group) and not args.docs_json:
                parser.error("--nav-dropdown/--nav-version/--nav-group require --docs-json")
            if args.docs_json and not args.nav_dropdown:
                parser.error("--docs-json requires --nav-dropdown")

            report = build_jvm_doc_report_from_manifest_args(args)
            overview_file = Path(args.overview_file)
            details_dir = Path(args.details_dir)
            if overview_file.exists():
                overview_file.unlink()
            if details_dir.exists():
                shutil.rmtree(details_dir)
            output_root, pages = build_pages(
                report,
                overview_output=overview_file,
                details_dir=details_dir,
                overview_title=args.overview_title,
            )
            write_pages(pages, output_root)
            if args.docs_json:
                update_docs_json_navigation(
                    Path(args.docs_json),
                    output_file=overview_file,
                    target=MintlifyNavTarget(
                        dropdown=args.nav_dropdown,
                        versions=args.nav_version or None,
                        groups=args.nav_group,
                    ),
                )
            return 0

    if args.command == "daml-json":
        if args.daml_json_command == "build-api-pages-from-manifest":
            from x2mdx.daml_json.render import build_pages
            from x2mdx.render import write_pages

            report = build_daml_doc_report_from_manifest_args(args)
            output_root, pages = build_pages(
                report,
                output_dir=Path(args.output_dir),
                overview_title=args.overview_title,
                link_prefix=args.link_prefix,
            )
            write_pages(pages, output_root)
            return 0

    if args.command == "protobuf":
        if args.protobuf_command == "build-api-pages-from-manifest":
            from x2mdx.protobuf.render import build_pages
            from x2mdx.render import write_pages

            report = build_protobuf_report_from_manifest_args(args)
            output_dir = Path(args.output_dir)
            if output_dir.exists():
                shutil.rmtree(output_dir)
            output_root, pages = build_pages(report, output_dir=output_dir)
            write_pages(pages, output_root)
            return 0

    if args.command == "typedoc":
        if args.typedoc_command == "build-api-pages-from-manifest":
            from x2mdx.render import write_page
            from x2mdx.typedoc.render import build_page

            report = build_typedoc_report_from_manifest_args(args)
            output_file = Path(args.output_file)
            page = build_page(
                report,
                output_path=output_file.name,
                page_title=args.page_title,
                page_description=args.page_description,
            )
            write_page(page, output_file)
            return 0

    if args.command == "asyncapi":
        if args.asyncapi_command == "build-api-pages-from-manifest":
            from x2mdx.asyncapi.render import build_page
            from x2mdx.mintlify import MintlifyNavTarget, update_docs_json_navigation
            from x2mdx.render import write_page

            if (args.nav_dropdown or args.nav_version or args.nav_group) and not args.docs_json:
                parser.error("--nav-dropdown/--nav-version/--nav-group require --docs-json")
            if args.docs_json and not args.nav_dropdown:
                parser.error("--docs-json requires --nav-dropdown")

            report = build_asyncapi_report_from_manifest_args(args)
            output_file = Path(args.output_file)
            page = build_page(
                report,
                output_path=output_file.name,
                page_title=args.page_title,
                page_description=args.page_description,
            )
            write_page(page, output_file)
            if args.docs_json:
                update_docs_json_navigation(
                    Path(args.docs_json),
                    output_file=output_file,
                    target=MintlifyNavTarget(
                        dropdown=args.nav_dropdown,
                        versions=args.nav_version or None,
                        groups=args.nav_group,
                    ),
                )
            return 0

    if args.command == "openrpc":
        if args.openrpc_command == "build-api-pages-from-manifest":
            from x2mdx.openrpc.render import build_pages
            from x2mdx.render import write_pages

            report = build_openrpc_report_from_manifest_args(args)
            output_dir = Path(args.output_dir)
            if output_dir.exists():
                shutil.rmtree(output_dir)
            output_root, pages = build_pages(
                report,
                output_dir=output_dir,
                overview_name=args.overview_name,
                spec_dir_name=args.spec_dir_name,
                overview_title=args.overview_title,
                link_prefix=args.link_prefix,
            )
            write_pages(pages, output_root)
            return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
