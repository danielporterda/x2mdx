"""Shared Jinja-based markdown templating helpers."""

from __future__ import annotations

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
