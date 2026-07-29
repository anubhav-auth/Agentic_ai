"""Generate test PDFs so the triage gate can be checked without real documents.

    python tests/make_fixtures.py

Builds six cases that between them cover the ways the gate can be wrong:

  text_only.pdf      prose only                 -> must be TEXT_ONLY
  vector_diagram.pdf prose + a drawn flowchart  -> must be HAS_FIGURES
                     (no embedded bitmap at all -- this is the case a
                      get_images()-only check misses, and the one AnythingLLM
                      silently drops today)
  table.pdf          prose + a ruled table      -> must be TEXT_ONLY
                     (a table is a swarm of vector lines; naive path-counting
                      calls it a diagram. This is the false-positive guard.)
  logo.pdf           prose + a tiny 30pt mark   -> must be TEXT_ONLY
                     (small raster; the size filter must reject it)
  heavy_chart.pdf    400+ vector paths          -> must be HAS_FIGURES
                     (clustering stress: a real chart is hundreds of marks that
                      must collapse into ONE figure, not hundreds)
  scanned.pdf        one full-page image,
                     zero text layer            -> must be SCANNED
                     (MarkItDown extracts 0 chars from this. It also renders
                      full-page, which is what overran the model's context and
                      broke every scanned document until MAX_RENDER_PX existed.)
"""

from pathlib import Path

import fitz

OUT = Path(__file__).parent / "fixtures"

LOREM = (
    "Service oriented architecture decomposes an application into independently "
    "deployable services that communicate over a network. Each service owns its "
    "data and exposes a contract. This paragraph exists purely so the extractor "
    "has real text to pull out of the page. "
) * 4


def _prose(page, text=LOREM):
    page.insert_textbox(fitz.Rect(50, 50, 545, 220), text, fontsize=11)


def text_only():
    doc = fitz.open()
    page = doc.new_page()
    _prose(page)
    page.insert_textbox(fitz.Rect(50, 240, 545, 500), LOREM, fontsize=11)
    doc.save(OUT / "text_only.pdf")
    doc.close()


def vector_diagram():
    """A flowchart drawn with vector commands -- exactly what draw.io exports."""
    doc = fitz.open()
    page = doc.new_page()
    _prose(page)
    page.insert_text((50, 250), "Figure 1: request flow", fontsize=10)

    boxes = [
        (fitz.Rect(70, 280, 190, 340), "Client"),
        (fitz.Rect(240, 280, 360, 340), "API Gateway"),
        (fitz.Rect(410, 220, 530, 280), "Auth Service"),
        (fitz.Rect(410, 300, 530, 360), "Order Service"),
        (fitz.Rect(240, 420, 360, 480), "PostgreSQL"),
    ]
    for rect, label in boxes:
        page.draw_rect(rect, color=(0.1, 0.1, 0.5), width=1.5)
        page.insert_textbox(rect, "\n" + label, fontsize=10, align=fitz.TEXT_ALIGN_CENTER)

    arrows = [
        ((190, 310), (240, 310)),
        ((360, 300), (410, 260)),
        ((360, 320), (410, 330)),
        ((470, 360), (360, 440)),
        ((300, 340), (300, 420)),
    ]
    for start, end in arrows:
        page.draw_line(fitz.Point(*start), fitz.Point(*end), color=(0, 0, 0), width=1.2)
        page.draw_circle(fitz.Point(*end), 2.5, color=(0, 0, 0), fill=(0, 0, 0))

    doc.save(OUT / "vector_diagram.pdf")
    doc.close()


def table():
    """A ruled table. Lots of vector paths, but NOT a diagram."""
    doc = fitz.open()
    page = doc.new_page()
    _prose(page)
    page.insert_text((50, 250), "Table 1: service inventory", fontsize=10)

    top, left, row_h, col_w = 270, 60, 26, 120
    for r in range(7):  # horizontal rules
        y = top + r * row_h
        page.draw_line(fitz.Point(left, y), fitz.Point(left + col_w * 4, y), width=0.7)
    for c in range(5):  # vertical rules
        x = left + c * col_w
        page.draw_line(fitz.Point(x, top), fitz.Point(x, top + row_h * 6), width=0.7)
    for r in range(6):
        for c in range(4):
            page.insert_text(
                (left + c * col_w + 6, top + r * row_h + 17),
                f"cell {r}{c}",
                fontsize=9,
            )

    doc.save(OUT / "table.pdf")
    doc.close()


def logo():
    """A small raster mark in the corner. Must not trigger the vision model."""
    doc = fitz.open()
    page = doc.new_page()
    _prose(page)

    swatch = fitz.open()
    sp = swatch.new_page(width=64, height=64)
    sp.draw_rect(fitz.Rect(0, 0, 64, 64), color=(0.8, 0.2, 0.2), fill=(0.8, 0.2, 0.2))
    png = sp.get_pixmap().tobytes("png")
    swatch.close()

    page.insert_image(fitz.Rect(500, 20, 530, 50), stream=png)  # 30x30pt
    doc.save(OUT / "logo.pdf")
    doc.close()


def heavy_chart():
    """A matplotlib-style chart: hundreds of separate vector marks.

    Stresses the clustering. Every dot is far too small to be a figure alone;
    they must merge into a single drawing rather than 400 tiny ones.
    """
    import random

    random.seed(7)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 545, 120), "Chart page. " * 12, fontsize=11)

    page.draw_rect(fitz.Rect(70, 160, 520, 520), width=1)  # axes frame
    for i in range(11):  # gridlines -- 1D rules, must not vote
        y = 160 + i * 36
        page.draw_line(fitz.Point(70, y), fitz.Point(520, y), width=0.4)
        x = 70 + i * 45
        page.draw_line(fitz.Point(x, 160), fitz.Point(x, 520), width=0.4)
    for _ in range(400):  # markers -- curves, these do vote
        x = 70 + random.random() * 450
        y = 160 + random.random() * 360
        page.draw_circle(fitz.Point(x, y), 2.2, color=(0.2, 0.3, 0.8))

    doc.save(OUT / "heavy_chart.pdf")
    doc.close()


def scanned():
    """A page that is purely an image: no text layer at all.

    MarkItDown returns 0 characters for this and still reports success.
    """
    src = fitz.open()
    sp = src.new_page()
    sp.draw_rect(sp.rect, color=(1, 1, 1), fill=(1, 1, 1))
    sp.insert_text((70, 110), "QUARTERLY REPORT", fontsize=26)
    sp.insert_text((70, 160), "Revenue rose 18 percent", fontsize=15)
    sp.insert_text((70, 195), "Costs fell to 4.2 million", fontsize=15)
    sp.draw_rect(fitz.Rect(70, 240, 420, 470), width=2)
    sp.insert_text((90, 270), "Figure: growth by region", fontsize=12)
    for i, h in enumerate([60, 110, 150, 190]):
        sp.draw_rect(
            fitz.Rect(100 + i * 70, 440 - h, 150 + i * 70, 440), fill=(0.2, 0.4, 0.8)
        )
    png = sp.get_pixmap(matrix=fitz.Matrix(2, 2)).tobytes("png")
    src.close()

    # Re-embed as a flat image so the text layer is genuinely gone.
    out = fitz.open()
    page = out.new_page()
    page.insert_image(page.rect, stream=png)
    out.save(OUT / "scanned.pdf")
    out.close()


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    text_only()
    vector_diagram()
    table()
    logo()
    heavy_chart()
    scanned()
    for p in sorted(OUT.glob("*.pdf")):
        print(f"wrote {p.relative_to(Path(__file__).parent.parent)}")
