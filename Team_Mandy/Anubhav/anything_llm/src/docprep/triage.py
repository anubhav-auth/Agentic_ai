"""The gate: does this document actually contain diagrams?

This is the cheap, deterministic step that runs BEFORE any LLM is touched.
No model, no network, no tokens -- just reading the PDF's internal structure.
If the answer is "no figures", the expensive vision path never runs.

Two kinds of picture have to be caught, and they look nothing alike inside a PDF:

  1. RASTER  -- a real embedded bitmap (a photo, a screenshot, a scan).
                Found via page.get_images().
  2. VECTOR  -- drawing commands, no bitmap anywhere. Anything exported from
                matplotlib, draw.io, Visio, PowerPoint or TikZ is this.
                Found via page.get_drawings().

Missing case 2 is the classic bug: a page full of architecture diagrams can
contain zero embedded images, so a get_images()-only check reports "text only"
and every diagram is silently dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import fitz  # PyMuPDF

from .config import settings


class UnreadableDocument(RuntimeError):
    """The file cannot be parsed at all: corrupt, truncated, or password-locked.

    Distinct from "no figures found". This means we never got to look, so the
    caller must report it rather than quietly emitting an empty .md.
    """


class Verdict(str, Enum):
    TEXT_ONLY = "text-only"  # nothing to look at; skip the vision model
    HAS_FIGURES = "has-figures"  # text + diagrams; describe the diagrams
    SCANNED = "scanned"  # little/no text; the page IS an image


class FigureKind(str, Enum):
    RASTER = "raster"
    VECTOR = "vector"
    FULL_PAGE = "full-page"


@dataclass
class Figure:
    page_number: int  # 1-based, matches what a human sees in a viewer
    bbox: tuple[float, float, float, float]
    kind: FigureKind
    area_ratio: float


@dataclass
class PageReport:
    page_number: int
    text_chars: int
    figures: list[Figure] = field(default_factory=list)
    is_scanned: bool = False


@dataclass
class DocReport:
    path: Path
    verdict: Verdict
    pages: list[PageReport] = field(default_factory=list)

    @property
    def figures(self) -> list[Figure]:
        return [f for p in self.pages for f in p.figures]

    @property
    def figure_count(self) -> int:
        return len(self.figures)

    @property
    def text_chars(self) -> int:
        return sum(p.text_chars for p in self.pages)

    def summary(self) -> str:
        return (
            f"{self.path.name}: {self.verdict.value} "
            f"({len(self.pages)} pages, {self.text_chars} chars, "
            f"{self.figure_count} figures)"
        )


def _rect_ok(rect: fitz.Rect, page_area: float) -> tuple[bool, float]:
    """Is this rectangle big and chunky enough to be a real figure?"""
    w, h = abs(rect.width), abs(rect.height)
    if w < settings.min_side_pt or h < settings.min_side_pt:
        return False, 0.0

    # A very long, very thin box is a horizontal rule or a page banner.
    short, long_ = min(w, h), max(w, h)
    if short > 0 and (long_ / short) > settings.max_aspect_ratio:
        return False, 0.0

    ratio = (w * h) / page_area if page_area else 0.0
    if ratio < settings.min_area_ratio:
        return False, 0.0
    return True, ratio


@dataclass
class _Path:
    """One vector drawing command's bounding box."""

    rect: fitz.Rect
    is_shape: bool  # 2D shape or curve (votes) vs 1D rule/arrow (doesn't)


def _touches(a: fitz.Rect, b: fitz.Rect, gap: float) -> bool:
    """Overlap test that tolerates zero-width/zero-height rects.

    fitz.Rect.intersects() returns False whenever either rect is "empty", and a
    perfectly horizontal line IS empty by that definition (height == 0). Since
    arrows are exactly that, using intersects() here silently drops every
    axis-aligned connector and diagrams come apart into fragments.
    """
    return (
        a.x0 - gap <= b.x1 and b.x0 - gap <= a.x1
        and a.y0 - gap <= b.y1 and b.y0 - gap <= a.y1
    )


def _union(a: fitz.Rect, b: fitz.Rect) -> fitz.Rect:
    """Bounding box of two rects. Done by hand for the same reason as _touches:
    fitz's |= operator ignores empty rects."""
    return fitz.Rect(
        min(a.x0, b.x0), min(a.y0, b.y0), max(a.x1, b.x1), max(a.y1, b.y1)
    )


def _cluster(paths: list[_Path], gap: float) -> list[list[_Path]]:
    """Group nearby paths into drawings.

    A vector diagram arrives as a swarm of tiny paths -- one per arrow and box.
    Individually each is too small to be a figure; grouped, they obviously are
    one. Repeat until stable, since two boxes may only become neighbours after
    a third path bridges them.
    """
    groups: list[list[_Path]] = [[p] for p in paths]
    bounds: list[fitz.Rect] = [fitz.Rect(p.rect) for p in paths]

    merged = True
    while merged:
        merged = False
        i = 0
        while i < len(groups):
            j = i + 1
            while j < len(groups):
                if _touches(bounds[i], bounds[j], gap):
                    groups[i].extend(groups[j])
                    bounds[i] = _union(bounds[i], bounds[j])
                    del groups[j], bounds[j]
                    merged = True
                else:
                    j += 1
            i += 1
    return groups


def _raster_figures(page: fitz.Page, page_area: float) -> list[Figure]:
    figures: list[Figure] = []
    for info in page.get_images(full=True):
        xref = info[0]
        try:
            rects = page.get_image_rects(xref)
        except Exception:
            continue  # malformed xref; not worth failing the whole document
        for rect in rects:
            ok, ratio = _rect_ok(rect, page_area)
            if ok:
                figures.append(
                    Figure(page.number + 1, tuple(rect), FigureKind.RASTER, ratio)
                )
    return figures


def _vector_figures(page: fitz.Page, page_area: float) -> list[Figure]:
    """Find vector drawings by clustering paths, then counting only real shapes.

    The table problem: a ruled table and a flowchart both consist of many vector
    paths, so any rule of the form "lots of paths => diagram" flags every table
    in the document and burns vision calls on them.

    What actually separates them is dimensionality. A table is drawn with 1D
    rules -- perfectly horizontal or vertical hairlines. A diagram contains 2D
    things: filled boxes, nodes, curved arrowheads. So lines are kept for
    working out how far a drawing extends (an arrow is part of the picture), but
    only 2D shapes and curves get a vote on whether it IS a picture.
    """
    paths: list[_Path] = []
    for drawing in page.get_drawings():
        rect = drawing.get("rect")
        if rect is None or rect.is_infinite:
            continue
        rect = fitz.Rect(rect)
        rect.normalize()  # guarantee x0<=x1, y0<=y1 before any comparison
        w, h = rect.width, rect.height
        if w < 1 and h < 1:
            continue  # a dot or rounding noise

        # A curve is never part of a table's grid.
        has_curve = any(item and item[0] == "c" for item in drawing.get("items", []))
        is_shape = (
            w >= settings.vector_min_shape_pt and h >= settings.vector_min_shape_pt
        ) or has_curve
        paths.append(_Path(rect, is_shape))

    # Cheap reject before clustering, which is the expensive part.
    if sum(p.is_shape for p in paths) < settings.vector_min_shapes:
        return []

    figures: list[Figure] = []
    for group in _cluster(paths, settings.vector_cluster_gap_pt):
        if sum(p.is_shape for p in group) < settings.vector_min_shapes:
            continue  # a few stray strokes, not a drawing
        bounds = group[0].rect
        for p in group[1:]:
            bounds = _union(bounds, p.rect)
        ok, ratio = _rect_ok(bounds, page_area)
        if ok:
            figures.append(
                Figure(page.number + 1, tuple(bounds), FigureKind.VECTOR, ratio)
            )
    return figures


def _dedupe(figures: list[Figure]) -> list[Figure]:
    """Drop vector figures that just trace an already-found raster one.

    Charts are often exported as a bitmap with a vector frame drawn around it;
    without this we would describe the same picture twice.
    """
    kept: list[Figure] = []
    for fig in sorted(figures, key=lambda f: f.area_ratio, reverse=True):
        box = fitz.Rect(fig.bbox)
        if any(
            (box & fitz.Rect(k.bbox)).get_area() > 0.7 * box.get_area() for k in kept
        ):
            continue
        kept.append(fig)
    return sorted(kept, key=lambda f: (f.page_number, f.bbox[1], f.bbox[0]))


def inspect_pdf(path: Path) -> DocReport:
    """Scan a PDF and decide whether it needs the vision model. No LLM calls.

    Raises UnreadableDocument if the file cannot be opened or is encrypted.
    """
    report = DocReport(path=path, verdict=Verdict.TEXT_ONLY)

    try:
        doc = fitz.open(path)
    except Exception as exc:
        raise UnreadableDocument(f"not a readable PDF ({exc})") from exc

    with doc:
        # A locked PDF opens fine and only explodes on the first page access,
        # so this has to be checked up front rather than caught later.
        if doc.needs_pass:
            raise UnreadableDocument("password-protected")

        for page in doc:
            page_area = abs(page.rect.width * page.rect.height) or 1.0
            text = page.get_text("text").strip()

            figures = _dedupe(
                _raster_figures(page, page_area) + _vector_figures(page, page_area)
            )

            # A scan: barely any text, and a picture covering most of the sheet.
            biggest = max((f.area_ratio for f in figures), default=0.0)
            is_scanned = (
                len(text) < settings.scanned_max_chars
                and biggest >= settings.scanned_min_cover
            )
            if is_scanned:
                # Describe the whole sheet, not the fragments on it.
                figures = [
                    Figure(page.number + 1, tuple(page.rect), FigureKind.FULL_PAGE, 1.0)
                ]

            report.pages.append(
                PageReport(page.number + 1, len(text), figures, is_scanned)
            )

    if any(p.is_scanned for p in report.pages):
        report.verdict = Verdict.SCANNED
    elif report.figure_count:
        report.verdict = Verdict.HAS_FIGURES
    else:
        report.verdict = Verdict.TEXT_ONLY
    return report
