"""docprep -- diagram-aware document ingestion for AnythingLLM.

Detects whether a document actually contains diagrams before spending any
vision-model time on it, then converts it to Markdown with figures described
inline.
"""

from .pipeline import Pipeline, Result
from .triage import DocReport, Figure, UnreadableDocument, Verdict, inspect_pdf
from .vision import VisionDescriber, VisionUnavailable, preflight

__version__ = "0.1.0"

__all__ = [
    "Pipeline",
    "Result",
    "DocReport",
    "Figure",
    "UnreadableDocument",
    "Verdict",
    "inspect_pdf",
    "VisionDescriber",
    "VisionUnavailable",
    "preflight",
]
