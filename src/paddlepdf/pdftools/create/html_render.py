"""Styled HTML -> PDF rendering through xhtml2pdf, shared by the conversion tools."""

import re
from pathlib import Path
from typing import Final

from xhtml2pdf import pisa
from xhtml2pdf.config.resources import ResourceAccessPolicy

from paddlepdf.pdftools.contract import PdfToolError

_HEAD_CLOSE: Final = re.compile(r"</head\s*>", re.IGNORECASE)


def inject_css(html: str, css: str) -> str:
    style = f'<style id="paperpilot-injected-css">\n{css}\n</style>'
    match = _HEAD_CLOSE.search(html)
    if match is None:
        return f"<!DOCTYPE html><html><head>{style}</head><body>{html}</body></html>"
    return f"{html[: match.start()]}{style}{html[match.start() :]}"


def render_html(html: str, css: str, source: Path, target: Path) -> list[str]:
    """Render ``html`` with ``css`` injected; return renderer warnings.

    Relative resources resolve against ``source``'s folder and local reads stay
    confined to it; remote fetches are refused so conversion never hits the network.
    """
    policy = ResourceAccessPolicy(allow_remote=False, base_dir=source.parent)
    with target.open("wb") as handle:
        context = pisa.CreatePDF(
            inject_css(html, css),
            dest=handle,
            path=str(source),
            encoding="utf-8",
            resource_policy=policy,
        )
    if context.err:
        target.unlink(missing_ok=True)
        problems = "; ".join(entry[2] for entry in context.log if entry[0] == "error")
        msg = f"HTML rendering failed: {problems or 'unknown xhtml2pdf error'}"
        raise PdfToolError(msg)
    return [entry[2] for entry in context.log if entry[0] == "warning"]
