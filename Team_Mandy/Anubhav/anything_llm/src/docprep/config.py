"""Tunable settings for the ingest pipeline.

Everything here can be overridden with environment variables (or a .env file),
so you can retune the triage gate without touching code.
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _f(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _i(name: str, default: int) -> int:
    return int(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    # --- Vision backend ---
    # Any OpenAI-compatible endpoint. Ollama serves one on /v1, so does
    # OpenRouter -- swapping providers is just these three values.
    #   local   : http://localhost:11434/v1  + qwen2.5vl:3b
    #   remote  : https://openrouter.ai/api/v1 + x-ai/grok-4.20
    llm_base_url: str = os.getenv(
        "LLM_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    )
    vision_model: str = os.getenv("VISION_MODEL", "qwen2.5vl:3b")
    # Ollama ignores the key but the OpenAI SDK refuses to start without one.
    llm_api_key: str = os.getenv(
        "LLM_API_KEY", os.getenv("OPENROUTER_API_KEY", "ollama")
    )
    request_timeout: float = _f("REQUEST_TIMEOUT", 180.0)
    # Cap the reply. A description needs ~500 tokens; without a cap OpenRouter
    # reserves the model's full output window against your credit balance and
    # rejects the call outright ("requested up to 65536 tokens, can afford...").
    max_tokens: int = _i("MAX_TOKENS", 1024)
    # Ollama defaults to a 4096-token context. A full A4 page rendered at 200 DPI
    # is ~4200 image tokens on its own, so the default cannot fit a single
    # scanned page and every such call fails with exceed_context_size_error.
    # Ollama-specific: only sent to a local endpoint (see is_local).
    num_ctx: int = _i("NUM_CTX", 8192)

    # --- Text-extraction backend ---
    # markitdown (default, fast, no ML) or docling (the lab's engine, layout-
    # aware, heavier). Neither describes figures -- the vision path does that.
    parser: str = os.getenv("PARSER", "markitdown")

    @property
    def is_local(self) -> bool:
        """True when nothing leaves the machine.

        Gates the Ollama-only num_ctx option, and drives the warning shown
        before documents are uploaded to a third party.
        """
        return any(
            host in self.llm_base_url
            for host in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")
        )

    # --- Triage: what counts as a "figure" ---
    # A picture must cover at least this fraction of the page. Kills logos,
    # icons, bullet glyphs, and signature scans.
    min_area_ratio: float = _f("MIN_AREA_RATIO", 0.015)
    # ...and be at least this many points on a side (1pt = 1/72 inch).
    min_side_pt: float = _f("MIN_SIDE_PT", 40.0)
    # Long thin things are rules/banners/borders, not diagrams.
    max_aspect_ratio: float = _f("MAX_ASPECT_RATIO", 20.0)

    # --- Triage: vector art (matplotlib, draw.io, TikZ, Visio) ---
    # Vector diagrams contain NO embedded image -- they are a swarm of little
    # paths. But so is a ruled table, so counting paths alone false-positives on
    # every table. The discriminator: only *2D shapes and curves* count toward
    # the threshold. A table is built from 1D rules, which score zero.
    # Lines still help decide a figure's extent (arrows), they just don't vote.
    vector_min_shapes: int = _i("VECTOR_MIN_SHAPES", 4)
    # A path needs this much size on BOTH axes to count as a 2D shape.
    vector_min_shape_pt: float = _f("VECTOR_MIN_SHAPE_PT", 3.0)
    # Two paths this close together belong to the same drawing.
    vector_cluster_gap_pt: float = _f("VECTOR_CLUSTER_GAP_PT", 18.0)

    # --- Triage: scanned pages ---
    # Almost no text + a picture covering most of the page = a scan.
    scanned_max_chars: int = _i("SCANNED_MAX_CHARS", 50)
    scanned_min_cover: float = _f("SCANNED_MIN_COVER", 0.6)

    # --- Rendering ---
    # DPI used when rasterising a figure for the vision model. 200 is a good
    # balance; higher mostly costs tokens without helping small models.
    render_dpi: int = _i("RENDER_DPI", 200)
    # Hard cap on the long side in pixels, applied after the DPI zoom and to
    # any uploaded image. Vision models bill by pixel area (~28x28 per token),
    # so an unbounded render silently overruns the context window. This is the
    # backstop that keeps a call from failing regardless of page or photo size.
    max_render_px: int = _i("MAX_RENDER_PX", 1400)
    # Padding around a figure's bbox so labels near the edge survive.
    # Generous on purpose: a figure's caption ("Figure 1: request flow") is a
    # separate text object sitting just outside the drawing's bounds, so a tight
    # crop cuts it off and the model loses the one line that says what it is.
    render_pad_pt: float = _f("RENDER_PAD_PT", 26.0)

    # --- AnythingLLM ---
    # The desktop app serves its API on 3001 only while the window is open.
    anythingllm_url: str = os.getenv("ANYTHINGLLM_URL", "http://localhost:3001")
    # Settings -> Tools -> Developer API -> Generate New API Key.
    anythingllm_api_key: str = os.getenv("ANYTHINGLLM_API_KEY", "")
    anythingllm_timeout: float = _f("ANYTHINGLLM_TIMEOUT", 120.0)
    anythingllm_workspace: str = os.getenv("ANYTHINGLLM_WORKSPACE", "docprep")

    # Formats that are already text. We leave these alone.
    passthrough_suffixes: tuple = (".md", ".markdown", ".txt")
    image_suffixes: tuple = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif")


settings = Settings()
