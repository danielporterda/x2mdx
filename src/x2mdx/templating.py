"""Shared Jinja-based markdown templating helpers."""

from __future__ import annotations

import html
import re
from functools import lru_cache
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined

from x2mdx.output import Page, RawMarkdown


def heading(level: int, text: str) -> str:
    return f"{'#' * level} {text}"


def paragraph(text: str) -> str:
    return text


def bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def code_block(language: str, body: str) -> str:
    return f"```{language}\n{body}\n```"


def anchor(anchor_id: str) -> str:
    return f'<a id="{anchor_id}"></a>'


def admonition(kind: str, body: str) -> str:
    return f"<{kind}>\n{body}\n</{kind}>"


def accordion_list(title: str, items: list[str]) -> str:
    lines = ["<AccordionGroup>", f'<Accordion title="{title}">']
    lines.extend(f"- {item}" for item in items)
    lines.extend(["</Accordion>", "</AccordionGroup>"])
    return "\n".join(lines)


def render_card_group(cards: list[dict[str, Any]], cols: int = 2) -> str:
    lines = [f"<CardGroup cols={{{cols}}}>"]
    for card in cards:
        lines.append(f'<Card title="{card["title"]}">')
        body = str(card["body"]).strip("\n")
        if body:
            lines.extend(body.splitlines())
        lines.append("</Card>")
    lines.append("</CardGroup>")
    return "\n".join(lines)


def pretty_json(value: Any) -> str:
    import json

    return json.dumps(value, indent=2)


def compact_version_label(value: Any) -> str:
    text = str(value).strip()
    if not text or text == "-":
        return "-"
    if text.startswith("v"):
        return text
    match = re.fullmatch(r"(\d+)\.(\d+)(?:\.(\d+))?(?:[-+].*)?", text)
    if match:
        return f"v{match.group(1)}.{match.group(2)}"
    return f"v{text}"


def compact_version_sequence(values: list[Any]) -> str:
    labels = [compact_version_label(value) for value in values if str(value).strip() and str(value).strip() != "-"]
    if not labels:
        return "-"
    if len(labels) == 1:
        return labels[0]
    return f"{labels[-1]} +{len(labels) - 1}"


STATUS_TOKEN_META: dict[str, dict[str, str]] = {
    "introduced": {"color": "#16a34a", "label": "Active Since"},
    "changed": {"color": "#2563eb", "label": "Changed"},
    "alpha": {"color": "#7c3aed", "label": "Alpha"},
    "beta": {"color": "#d97706", "label": "Beta"},
    "stable": {"color": "#0f766e", "label": "Stable"},
    "deprecated": {"color": "#ea580c", "label": "Deprecated"},
    "removed": {"color": "#dc2626", "label": "Removed"},
}


def _jsx_style(styles: dict[str, str]) -> str:
    return "{{" + ", ".join(f'{key}: "{value}"' for key, value in styles.items()) + "}}"


def _status_dot(kind: str) -> str:
    color = STATUS_TOKEN_META[kind]["color"]
    return (
        '<span aria-hidden="true" '
        f'style={_jsx_style({"display": "inline-block", "width": "0.72em", "height": "0.72em", "borderRadius": "9999px", "background": color, "flex": "none"})}></span>'
    )


def render_status_badges(tokens: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> str:
    if not tokens:
        return "-"
    rendered: list[str] = []
    for token in tokens:
        if not isinstance(token, dict):
            continue
        kind = str(token.get("kind") or "").strip().lower()
        if kind not in STATUS_TOKEN_META:
            continue
        raw_label = str(token.get("label") or "").strip()
        label = raw_label or STATUS_TOKEN_META[kind]["label"]
        rendered.append(
            '<span title="{}" style={}>{}{}</span>'.format(
                html.escape(STATUS_TOKEN_META[kind]["label"], quote=True),
                _jsx_style(
                    {
                        "display": "inline-flex",
                        "alignItems": "center",
                        "gap": "0.35em",
                        "whiteSpace": "nowrap",
                        "marginRight": "0.65em",
                    }
                ),
                _status_dot(kind),
                f"<code>{html.escape(label)}</code>",
            )
        )
    return " ".join(rendered) or "-"


def render_status_legend_items(items: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None) -> str:
    if not items:
        return ""
    rendered: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        kind = str(item.get("kind") or "").strip().lower()
        if kind not in STATUS_TOKEN_META:
            continue
        label = str(item.get("label") or "").strip() or STATUS_TOKEN_META[kind]["label"]
        rendered.append(
            '<span style={}>{}{}</span>'.format(
                _jsx_style(
                    {
                        "display": "inline-flex",
                        "alignItems": "center",
                        "gap": "0.35em",
                        "whiteSpace": "nowrap",
                        "marginRight": "0.85em",
                    }
                ),
                _status_dot(kind),
                html.escape(label),
            )
        )
    return " ".join(rendered)


def render_status_cell(
    *,
    introduced: Any | None = None,
    changed: list[Any] | None = None,
    deprecated: Any | None = None,
    removed: Any | None = None,
) -> str:
    parts: list[str] = []
    introduced_text = str(introduced).strip() if introduced is not None else ""
    deprecated_text = str(deprecated).strip() if deprecated is not None else ""
    removed_text = str(removed).strip() if removed is not None else ""
    if introduced_text and introduced_text != "-":
        parts.append(f"🟢 `{compact_version_label(introduced_text)}`")
    changed_versions: list[str] = []
    for value in changed or []:
        text = str(value).strip()
        if not text or text == "-":
            continue
        if text in {introduced_text, deprecated_text, removed_text}:
            continue
        if text not in changed_versions:
            changed_versions.append(text)
    if changed_versions:
        parts.append(f"🔵 `{compact_version_sequence(changed_versions)}`")
    if deprecated_text and deprecated_text != "-":
        parts.append(f"🟠 `{compact_version_label(deprecated_text)}`")
    if removed_text and removed_text != "-":
        parts.append(f"🔴 `{compact_version_label(removed_text)}`")
    return " ".join(parts) or "-"


def render_status_legend(
    *,
    include_changed: bool = True,
    include_deprecated: bool = True,
    include_removed: bool = True,
) -> str:
    items = ["🟢 Active Since"]
    if include_changed:
        items.append("🔵 Changed")
    if include_deprecated:
        items.append("🟠 Deprecated")
    if include_removed:
        items.append("🔴 Removed")
    return "  ".join(items)


def _finalize(value: Any) -> Any:
    return "" if value is None else value


@lru_cache(maxsize=1)
def template_environment() -> Environment:
    environment = Environment(
        loader=PackageLoader("x2mdx", "templates"),
        autoescape=False,
        keep_trailing_newline=True,
        lstrip_blocks=False,
        trim_blocks=False,
        undefined=StrictUndefined,
        finalize=_finalize,
    )
    environment.globals.update(
        heading=heading,
        paragraph=paragraph,
        bullet_list=bullet_list,
        table=table,
        code_block=code_block,
        anchor=anchor,
        admonition=admonition,
        accordion_list=accordion_list,
        render_card_group=render_card_group,
        pretty_json=pretty_json,
        compact_version_label=compact_version_label,
        compact_version_sequence=compact_version_sequence,
        render_status_badges=render_status_badges,
        render_status_cell=render_status_cell,
        render_status_legend_items=render_status_legend_items,
        render_status_legend=render_status_legend,
    )
    return environment


def render_template(name: str, /, **context: Any) -> str:
    collapse_blank_lines = bool(context.pop("collapse_blank_lines", True))
    rendered = template_environment().get_template(name).render(**context)
    if collapse_blank_lines:
        rendered = re.sub(r"\n{3,}", "\n\n", rendered)
    return rendered.strip()


def markdown_page(
    *,
    path: str,
    title: str,
    description: str | None,
    template_name: str,
    **context: Any,
) -> Page:
    return Page(
        path=path,
        title=title,
        description=description,
        blocks=[RawMarkdown(render_template(template_name, **context))],
    )
