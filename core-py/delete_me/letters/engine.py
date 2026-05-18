"""Render CCPA / state-DSAR / GDPR deletion letters from broker + consumer data.

Phase 0 produces Markdown and an HTML render; PDF output via WeasyPrint is
optional (gated on import) so the package still imports on systems missing the
WeasyPrint native deps. PDF is opt-in via LetterEngine(render_pdf=True).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from delete_me.paths import templates_dir
from delete_me.registry import Broker, Statute


@dataclass(frozen=True)
class ConsumerProfile:
    """The PII the consumer provides to populate letters.

    Lives only in memory in Phase 0 — nothing is written off-device unless the
    consumer explicitly asks the engine to render to a file.
    """

    full_legal_name: str
    current_address: str
    email: str | None = None
    phone: str | None = None
    dob_year: int | None = None
    prior_addresses: tuple[str, ...] = ()
    former_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderedLetter:
    broker_id: str
    template: str
    markdown: str
    generated_at: datetime
    user_submit_only: bool


class LetterEngine:
    """Render letters using Jinja2 templates under letters/templates/."""

    DEFAULT_TEMPLATE = "ccpa_authorized_agent.j2"

    def __init__(self, render_pdf: bool = False) -> None:
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir())),
            autoescape=select_autoescape(["html"]),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.render_pdf = render_pdf

    def render(
        self,
        broker: Broker,
        consumer: ConsumerProfile,
        statutes: dict[str, Statute],
    ) -> RenderedLetter:
        template_name = broker.letter_template or self.DEFAULT_TEMPLATE
        template = self.env.get_template(template_name)
        cited = [statutes[s] for s in broker.statutes if s in statutes]
        markdown = template.render(
            broker=broker,
            consumer=consumer,
            statutes=cited,
            generated_at=datetime.now(UTC),
        )
        return RenderedLetter(
            broker_id=broker.id,
            template=template_name,
            markdown=markdown,
            generated_at=datetime.now(UTC),
            user_submit_only=broker.user_submit_only or not broker.accepts_authorized_agent,
        )

    def write_markdown(self, letter: RenderedLetter, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"{letter.broker_id}.md"
        path.write_text(letter.markdown, encoding="utf-8")
        return path

    def write_pdf(self, letter: RenderedLetter, output_dir: Path) -> Path:
        """Optional PDF render. Imports WeasyPrint lazily.

        Will raise ImportError if WeasyPrint's native deps are missing — the
        CLI catches this and tells the user to fall back to markdown output.
        """
        if not self.render_pdf:
            raise RuntimeError("LetterEngine was constructed with render_pdf=False")
        from weasyprint import HTML  # noqa: WPS433  lazy import

        output_dir.mkdir(parents=True, exist_ok=True)
        html = _markdown_to_minimal_html(letter.markdown)
        path = output_dir / f"{letter.broker_id}.pdf"
        HTML(string=html).write_pdf(str(path))
        return path


def _markdown_to_minimal_html(markdown: str) -> str:
    """Wrap markdown in a minimal HTML envelope for WeasyPrint.

    Phase 0 keeps this deliberately tiny — we don't want a full Markdown→HTML
    pipeline yet. Templates already produce mostly-printable text; the HTML
    shell adds whitespace-preserving styling and a print stylesheet.
    """
    escaped = markdown.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>delete-me letter</title>
  <style>
    @page {{ size: Letter; margin: 1in; }}
    body {{
      font-family: 'Times New Roman', Times, serif;
      font-size: 11pt;
      line-height: 1.5;
      white-space: pre-wrap;
    }}
  </style>
</head>
<body>{escaped}</body>
</html>"""
