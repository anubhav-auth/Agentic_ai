"""Pluggable text-extraction backends.

The extraction step -- turning a document's text into Markdown -- is swappable.
Two backends are provided:

  markitdown  (default)  Microsoft MarkItDown. Fast, no ML models, wide format
                         support. What docprep was built on.
  docling                IBM Docling, the engine named in the lab. Layout-aware:
                         better tables and reading order, and it emits an
                         `<!-- image -->` marker where a figure sits -- but it
                         does not describe the figure. That gap is exactly what
                         docprep's vision layer fills on top.

Selected with PARSER=markitdown|docling (see config). Neither backend describes
diagrams; the triage + vision path does that regardless of which is chosen.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .config import settings


class TextParser(Protocol):
    name: str

    def to_markdown(self, path: Path) -> str: ...


class MarkItDownParser:
    name = "markitdown"

    def __init__(self) -> None:
        from markitdown import MarkItDown

        # No LLM here on purpose -- docprep drives vision itself so the gate
        # stays in our hands rather than MarkItDown's.
        self._md = MarkItDown(enable_plugins=False)

    def to_markdown(self, path: Path) -> str:
        return self._md.convert(str(path)).markdown


class DoclingParser:
    name = "docling"

    def __init__(self) -> None:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError as exc:
            raise RuntimeError(
                "PARSER=docling but docling is not installed. "
                'Install it with:  pip install -e ".[docling]"'
            ) from exc
        # The converter loads layout models once (slow); reuse it across files.
        self._conv = DocumentConverter()

    def to_markdown(self, path: Path) -> str:
        return self._conv.convert(str(path)).document.export_to_markdown()


def get_parser(name: str | None = None) -> TextParser:
    name = (name or settings.parser).lower()
    if name == "docling":
        return DoclingParser()
    if name == "markitdown":
        return MarkItDownParser()
    raise ValueError(f"Unknown PARSER {name!r}; use 'markitdown' or 'docling'.")
