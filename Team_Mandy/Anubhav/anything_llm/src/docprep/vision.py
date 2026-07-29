"""Describe a figure using the local vision model, via Ollama.

Ollama exposes an OpenAI-compatible API at /v1, so we use the official openai
SDK pointed at localhost. Nothing leaves the laptop.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import fitz  # PyMuPDF
from openai import OpenAI

from .config import settings
from .triage import Figure

# Aimed at RAG: we want prose a retriever can match a question against, not
# "This image shows...". Small models pad and hedge, so the prompt is blunt.
PROMPT = """You are converting a figure from a technical document into text for a search index.

Describe what this figure actually shows, so that someone who cannot see it
understands it completely. Be specific and factual.

- If it is a diagram or flowchart: name every box/node and state how they connect,
  including the direction of arrows.
- If it is a chart or graph: state the chart type, the axes and their units, and
  the trend or comparison it demonstrates. Give concrete values where readable.
- If it is a screenshot or photo: describe the salient content and transcribe any
  visible text.
- If it is a table rendered as a picture: reproduce it as a markdown table.

Do not begin with "This image shows" or similar. Do not speculate about anything
that is not visible. Output plain prose or markdown only."""


class VisionUnavailable(RuntimeError):
    """Raised when the local model cannot be reached or is not a vision model."""


# Magic bytes -> MIME. Ollama sniffs the payload and ignores what we declare,
# but a stricter OpenAI-compatible server (vLLM, the real OpenAI API) honours
# the declared type and rejects a JPEG announced as image/png.
_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
    (b"BM", "image/bmp"),
)


def _mime_of(data: bytes) -> str:
    for magic, mime in _MAGIC:
        if data.startswith(magic):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] in (b"II*\x00", b"MM\x00*"):
        return "image/tiff"
    return "image/png"  # our own renders are always PNG


def render_figure(page: fitz.Page, figure: Figure) -> bytes:
    """Rasterise a figure's region of the page to PNG bytes.

    We render the *page region* rather than pulling the embedded bitmap out.
    That is deliberate: a vector diagram has no bitmap to pull, and even for
    raster figures the region keeps any text drawn on top of the image (axis
    labels and callouts are very often separate text objects layered above it).
    """
    clip = fitz.Rect(figure.bbox)
    pad = settings.render_pad_pt
    clip += (-pad, -pad, pad, pad)
    clip &= page.rect  # never render outside the sheet

    zoom = settings.render_dpi / 72.0
    # Clamp to the pixel budget. A full A4 page at 200 DPI is ~1650x2340, which
    # on its own exceeds a 4096-token context -- so full-page (scanned) renders
    # MUST be scaled down or the request is rejected outright.
    longest = max(clip.width, clip.height) * zoom
    if longest > settings.max_render_px:
        zoom *= settings.max_render_px / longest

    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip)
    return pix.tobytes("png")


def downscale(data: bytes, max_px: int | None = None) -> bytes:
    """Shrink an image so its long side fits the pixel budget.

    Needed for user-supplied images, which we did not render and so cannot
    bound: a phone photo is happily 4000px wide and would blow any context.
    """
    max_px = max_px or settings.max_render_px
    try:
        from PIL import Image
    except ImportError:
        return data  # Pillow absent; send as-is and let the server complain

    try:
        with Image.open(io.BytesIO(data)) as img:
            if max(img.size) <= max_px:
                return data
            scale = max_px / max(img.size)
            resized = img.convert("RGB").resize(
                (max(1, int(img.width * scale)), max(1, int(img.height * scale))),
                Image.LANCZOS,
            )
            buf = io.BytesIO()
            resized.save(buf, format="PNG")
            return buf.getvalue()
    except Exception:
        return data  # unreadable by PIL; let the model try anyway


class VisionDescriber:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.vision_model
        self._client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            timeout=settings.request_timeout,
        )

    def describe(self, image: bytes) -> str:
        b64 = base64.b64encode(image).decode("ascii")
        mime = _mime_of(image)
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": PROMPT},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{b64}"},
                            },
                        ],
                    }
                ],
                temperature=0.1,  # description, not creative writing
                max_tokens=settings.max_tokens,
                # num_ctx is an Ollama option. Only a local endpoint understands
                # it; sending it to a hosted provider is at best ignored.
                **(
                    {"extra_body": {"options": {"num_ctx": settings.num_ctx}}}
                    if settings.is_local
                    else {}
                ),
            )
        except Exception as exc:  # connection refused, model missing, OOM...
            detail = str(exc)
            if "context size" in detail or "exceed_context" in detail:
                raise VisionUnavailable(
                    f"image too large for {self.model}'s context "
                    f"(num_ctx={settings.num_ctx}). Lower MAX_RENDER_PX or "
                    f"raise NUM_CTX."
                ) from exc
            if "requires more credits" in detail or "402" in detail:
                raise VisionUnavailable(
                    f"{self.model}: out of credits on the hosted provider. "
                    f"Top up, lower MAX_TOKENS, or switch back to local with "
                    f"LLM_BASE_URL=http://localhost:11434/v1"
                ) from exc
            if "429" in detail or "rate limit" in detail.lower():
                # :free models share pooled provider capacity and are the first
                # thing shed under load. This is not a bug in the request.
                raise VisionUnavailable(
                    f"{self.model}: rate-limited (429). Free models share "
                    f"capacity and get throttled. Retry, pick another :free "
                    f"model, or fall back to local (qwen2.5vl:3b)."
                ) from exc
            raise VisionUnavailable(f"{self.model} failed: {detail}") from exc

        text = (resp.choices[0].message.content or "").strip()
        if not text:
            raise VisionUnavailable(f"{self.model} returned an empty description")
        return text

    def describe_file(self, path: Path) -> str:
        return self.describe(downscale(path.read_bytes()))


def preflight(model: str | None = None) -> None:
    """Fail loudly and early if the model can't see.

    Worth its own step: a text-only model (qwen2.5:7b) answers an image request
    perfectly happily by ignoring the image and hallucinating from the prompt.
    That failure is invisible in the output -- you just get plausible, wrong
    descriptions. So we send a known image and check the model reports it.
    """
    model = model or settings.vision_model

    # A 2x2 PNG: solid red. Any real vision model says "red".
    doc = fitz.open()
    page = doc.new_page(width=64, height=64)
    page.draw_rect(fitz.Rect(0, 0, 64, 64), color=(1, 0, 0), fill=(1, 0, 0))
    png = page.get_pixmap().tobytes("png")
    doc.close()

    client = OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        timeout=settings.request_timeout,
    )
    b64 = base64.b64encode(png).decode("ascii")
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What colour is this image? One word."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            temperature=0.0,
            max_tokens=settings.max_tokens,
            **(
                {"extra_body": {"options": {"num_ctx": settings.num_ctx}}}
                if settings.is_local
                else {}
            ),
        )
    except Exception as exc:
        detail = str(exc)
        if "multimodal" in detail.lower():
            raise VisionUnavailable(
                f"'{model}' is a text-only model -- it cannot accept images.\n"
                f"Pull a vision model instead:  ollama pull qwen2.5vl:3b\n"
                f"then set VISION_MODEL=qwen2.5vl:3b"
            ) from exc
        raise VisionUnavailable(
            f"Cannot reach '{model}' at {settings.ollama_base_url}: {detail}\n"
            f"Is Ollama running? Is the model pulled (`ollama pull {model}`)?"
        ) from exc

    answer = (resp.choices[0].message.content or "").lower()
    if "red" not in answer:
        raise VisionUnavailable(
            f"'{model}' does not appear to process images (said {answer!r} for a "
            f"solid red square). Text-only models silently ignore images instead "
            f"of erroring. Pull a vision model, e.g. `ollama pull qwen2.5vl:3b`."
        )
