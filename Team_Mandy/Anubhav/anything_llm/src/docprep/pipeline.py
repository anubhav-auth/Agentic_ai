"""Orchestration: triage -> convert -> (only if needed) describe -> .md

The routing rule, which is the whole idea of the project:

    text-only  ->  parser text conversion (markitdown or docling). Zero LLM.
    has-figures->  page text PLUS a vision description of each figure, inlined
                   at the point on the page where it appears.
    scanned    ->  every page rendered and read by the vision model.
    .md/.txt   ->  left exactly as it is.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from .config import settings
from .triage import DocReport, UnreadableDocument, Verdict, inspect_pdf
from .vision import VisionDescriber, VisionUnavailable, render_figure


@dataclass
class Result:
    source: Path
    verdict: str
    output: Path | None
    figures_described: int = 0
    llm_calls: int = 0
    seconds: float = 0.0
    skipped: bool = False
    note: str = ""

    def summary(self) -> str:
        if self.skipped:
            return f"SKIP  {self.source.name} -- {self.note}"
        out = self.output.name if self.output else "(none)"
        return (
            f"OK    {self.source.name} -> {out} "
            f"[{self.verdict}, {self.figures_described} figures, "
            f"{self.llm_calls} llm calls, {self.seconds:.1f}s]"
        )


def _front_matter(source: Path, report: DocReport | None, verdict: str) -> str:
    """YAML header. AnythingLLM keeps this in the chunk, so the model can cite it."""
    lines = [
        "---",
        f'source_file: "{source.name}"',
        f"verdict: {verdict}",
    ]
    if report:
        lines.append(f"pages: {len(report.pages)}")
        lines.append(f"figures: {report.figure_count}")
    lines.append(f"converted_by: docprep ({settings.vision_model})")
    lines.append("---\n")
    return "\n".join(lines)


class Pipeline:
    def __init__(
        self,
        out_dir: Path,
        describer: VisionDescriber | None = None,
        parser: str | None = None,
    ):
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._describer = describer
        # The text-extraction backend (markitdown or docling). Built lazily so
        # importing the pipeline never pays docling's model-load cost unasked.
        self._parser_name = parser or settings.parser
        self._parser = None

    @property
    def describer(self) -> VisionDescriber:
        if self._describer is None:
            self._describer = VisionDescriber()
        return self._describer

    @property
    def parser(self):
        if self._parser is None:
            from .parsers import get_parser

            self._parser = get_parser(self._parser_name)
        return self._parser

    def process(self, path: Path) -> Result:
        started = time.perf_counter()
        suffix = path.suffix.lower()

        if suffix in settings.passthrough_suffixes:
            return Result(
                path,
                "passthrough",
                None,
                skipped=True,
                note="already text; left untouched",
            )

        if suffix == ".pdf":
            result = self._process_pdf(path)
        elif suffix in settings.image_suffixes:
            result = self._process_image(path)
        else:
            result = self._process_other(path)

        result.seconds = time.perf_counter() - started
        return result

    # ---------- PDF: the interesting path ----------

    def _process_pdf(self, path: Path) -> Result:
        try:
            report = inspect_pdf(path)  # <-- the gate. Cheap. No LLM.
        except UnreadableDocument as exc:
            # Skip loudly. Emitting an empty .md here would put a silently
            # blank document into the RAG corpus, which is worse than nothing.
            return Result(path, "unreadable", None, skipped=True, note=str(exc))

        if report.verdict is Verdict.TEXT_ONLY:
            return self._pdf_text_only(path, report)
        return self._pdf_with_figures(path, report)

    def _pdf_text_only(self, path: Path, report: DocReport) -> Result:
        """No diagrams found -> hand the whole file to the text parser and stop."""
        md = self.parser.to_markdown(path)
        out = self._write(path, _front_matter(path, report, "text-only") + md)
        return Result(path, "text-only", out, 0, 0)

    def _pdf_with_figures(self, path: Path, report: DocReport) -> Result:
        """Diagrams found -> rebuild page by page, inlining a description each time.

        We assemble from PyMuPDF page text rather than MarkItDown's whole-file
        output for one reason: placement. MarkItDown returns one flat string with
        no page boundaries, so there is nowhere to put "Figure on page 7". Going
        page by page lets each description sit next to the prose that refers to
        it, which is what makes the chunk useful once it is retrieved.
        """
        described = 0
        calls = 0
        errors: list[str] = []
        chunks: list[str] = []

        with fitz.open(path) as doc:
            for page_report in report.pages:
                page = doc[page_report.page_number - 1]
                chunks.append(f"\n\n## Page {page_report.page_number}\n")

                if not page_report.is_scanned:
                    text = page.get_text("text").strip()
                    if text:
                        chunks.append(text + "\n")

                for index, figure in enumerate(page_report.figures, start=1):
                    try:
                        png = render_figure(page, figure)
                        description = self.describer.describe(png)
                        calls += 1
                        described += 1
                    except VisionUnavailable as exc:
                        calls += 1
                        errors.append(f"p{figure.page_number}: {exc}")
                        chunks.append(
                            f"\n> **[Figure {index} on page {figure.page_number} "
                            f"could not be described: {exc}]**\n"
                        )
                        continue

                    heading = (
                        "Page content (scanned)"
                        if figure.kind.value == "full-page"
                        else f"Figure {index} ({figure.kind.value})"
                    )
                    chunks.append(
                        f"\n### {heading} -- page {figure.page_number}\n\n"
                        f"{description}\n"
                    )

        verdict = report.verdict.value
        body = _front_matter(path, report, verdict) + "".join(chunks)
        out = self._write(path, body)
        result = Result(path, verdict, out, described, calls)
        if errors:
            result.note = f"{len(errors)} figure(s) failed"
        return result

    # ---------- standalone images ----------

    def _process_image(self, path: Path) -> Result:
        """An uploaded image IS the figure -- no triage needed."""
        try:
            # describe_file, not describe: it downscales first, and an uploaded
            # photo can be far larger than the model's context allows.
            description = self.describer.describe_file(path)
        except VisionUnavailable as exc:
            return Result(path, "image", None, skipped=True, note=str(exc))

        body = (
            _front_matter(path, None, "image")
            + f"# {path.stem}\n\n{description}\n"
        )
        return Result(path, "image", self._write(path, body), 1, 1)

    # ---------- docx / pptx / xlsx / html / ... ----------

    def _process_other(self, path: Path) -> Result:
        """Text conversion via MarkItDown.

        Figure detection inside Office formats is not wired up yet -- see the
        README. MarkItDown extracts the text correctly; embedded pictures are
        dropped, same as they are today in AnythingLLM.
        """
        try:
            md = self.parser.to_markdown(path)
        except Exception as exc:
            return Result(path, "unsupported", None, skipped=True, note=str(exc))

        body = _front_matter(path, None, "text-only") + md
        return Result(path, "text-only", self._write(path, body), 0, 0)

    # ---------- io ----------

    def _write(self, source: Path, body: str) -> Path:
        out = self.out_dir / (source.stem + ".md")
        out.write_text(body, encoding="utf-8")
        return out
