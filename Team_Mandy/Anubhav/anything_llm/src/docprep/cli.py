"""Command line entry point.

    python -m docprep check   <path>      # triage only -- no LLM, no writes
    python -m docprep convert <path>      # triage, then convert to .md
    python -m docprep watch   [docs]      # process anything dropped in docs/
    python -m docprep doctor              # verify Ollama + the vision model
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .config import settings
from .pipeline import Pipeline
from .triage import UnreadableDocument, inspect_pdf
from .vision import VisionUnavailable, preflight

# src/docprep/cli.py -> repo root is three levels up.
ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INBOX = ROOT / "docs"  # source data, per the lab's /docs pathway
DEFAULT_OUTPUT = ROOT / "output"


def _is_candidate(p: Path) -> bool:
    # Dotfiles (.gitkeep) and zero-byte placeholders aren't documents; without
    # this they surface as alarming "no converter attempted" errors.
    return p.is_file() and not p.name.startswith(".") and p.stat().st_size > 0


def _iter_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(p for p in target.rglob("*") if _is_candidate(p))


def cmd_check(args: argparse.Namespace) -> int:
    """Triage only. Deliberately runs no model, so it is instant and free."""
    target = Path(args.path)
    # A missing path and a path with no PDFs are different problems: reporting
    # "No PDFs found" for a typo'd path sends you hunting for the wrong thing.
    if not target.exists():
        print(f"Not found: {target}", file=sys.stderr)
        return 1

    files = [p for p in _iter_files(target) if p.suffix.lower() == ".pdf"]
    if not files:
        print(f"No PDFs in {target}")
        return 1

    failures = 0
    for path in files:
        try:
            report = inspect_pdf(path)
        except UnreadableDocument as exc:
            print(f"\n{path.name}: UNREADABLE -- {exc}")
            failures += 1
            continue
        print(f"\n{report.summary()}")
        if args.verbose:
            for page in report.pages:
                if not page.figures:
                    continue
                for fig in page.figures:
                    x0, y0, x1, y1 = (round(v) for v in fig.bbox)
                    print(
                        f"    p{page.page_number:<3} {fig.kind.value:<9} "
                        f"{int(fig.area_ratio * 100):>3}% of page  "
                        f"({x0},{y0})-({x1},{y1})"
                    )
    return 1 if failures else 0


def cmd_convert(args: argparse.Namespace) -> int:
    target = Path(args.path)
    if not target.exists():
        print(f"Not found: {target}", file=sys.stderr)
        return 1

    files = _iter_files(target)
    if not files:
        print("Nothing to do.")
        return 0

    pipeline = Pipeline(Path(args.out))
    failures = 0
    for path in files:
        try:
            result = pipeline.process(path)
        except Exception as exc:
            print(f"FAIL  {path.name} -- {exc}", file=sys.stderr)
            failures += 1
            continue
        print(result.summary())
        if result.note and not result.skipped:
            print(f"      warning: {result.note}", file=sys.stderr)
    return 1 if failures else 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """convert -> upload -> embed, into an AnythingLLM workspace."""
    from .anythingllm import AnythingLLM, AnythingLLMError

    target = Path(args.path)
    if not target.exists():
        print(f"Not found: {target}", file=sys.stderr)
        return 1

    try:
        client = AnythingLLM()
        client.ping()
    except AnythingLLMError as exc:
        print(f"FAILED\n{exc}", file=sys.stderr)
        return 1

    with client:
        slug = client.find_or_create_workspace(args.workspace)
        print(f"workspace: {args.workspace} ({slug})\n")

        pipeline = Pipeline(Path(args.out))
        locations: list[str] = []
        stems: set[str] = set()

        for path in _iter_files(target):
            result = pipeline.process(path)
            print(result.summary())

            # A passthrough .md has no converted output -- send the original.
            md = result.output or (path if result.verdict == "passthrough" else None)
            if md is None:
                continue
            stems.add(md.name)
            try:
                location = client.upload(md)
            except AnythingLLMError as exc:
                print(f"      upload failed: {exc}", file=sys.stderr)
                continue
            locations.append(location)
            print(f"      uploaded -> {Path(location).name}")

        if not locations:
            print("\nNothing to embed.")
            return 1

        # Drop earlier copies of these same files, so re-running replaces
        # rather than stacking duplicate chunks into the corpus.
        try:
            removed = client.purge_previous(slug, stems)
            if removed:
                print(f"\nreplaced {removed} previous copy/copies")
        except AnythingLLMError as exc:
            print(f"\nwarning: could not purge old copies: {exc}", file=sys.stderr)

        print(f"\nembedding {len(locations)} document(s)...")
        try:
            client.embed(slug, locations)
        except AnythingLLMError as exc:
            print(f"FAILED\n{exc}", file=sys.stderr)
            return 1

    print(f"done -- open the '{args.workspace}' workspace in AnythingLLM and ask it "
          f"about your diagrams.")
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    from .watch import watch  # imported lazily; only this command needs watchdog

    inbox = Path(args.path or DEFAULT_INBOX)
    inbox.mkdir(parents=True, exist_ok=True)
    watch(inbox, Path(args.out))
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    print(f"Endpoint     : {settings.llm_base_url}")
    print(f"Vision model : {settings.vision_model}")
    if settings.is_local:
        print("Privacy      : LOCAL -- nothing leaves this machine")
    else:
        print(
            "Privacy      : REMOTE -- every figure is uploaded to a third party.\n"
            "               Do not point this at confidential documents."
        )
    try:
        preflight()
    except VisionUnavailable as exc:
        print(f"\nFAILED\n{exc}", file=sys.stderr)
        return 1
    print("\nOK -- the model reached the endpoint and correctly read a test image.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="docprep",
        description="Convert documents to Markdown, describing diagrams with a "
        "local vision model -- but only when diagrams are actually present.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="triage a PDF; no LLM, no output files")
    p_check.add_argument("path")
    p_check.add_argument("-v", "--verbose", action="store_true", help="list figures")
    p_check.set_defaults(func=cmd_check)

    p_conv = sub.add_parser("convert", help="convert a file or folder to .md")
    p_conv.add_argument("path")
    p_conv.add_argument("-o", "--out", default=str(DEFAULT_OUTPUT))
    p_conv.set_defaults(func=cmd_convert)

    p_ing = sub.add_parser(
        "ingest", help="convert, then push into an AnythingLLM workspace"
    )
    p_ing.add_argument("path")
    p_ing.add_argument(
        "-w", "--workspace", default=settings.anythingllm_workspace,
        help="workspace name (created if absent, reused if present)",
    )
    p_ing.add_argument("-o", "--out", default=str(DEFAULT_OUTPUT))
    p_ing.set_defaults(func=cmd_ingest)

    p_watch = sub.add_parser("watch", help="process files dropped into a folder")
    p_watch.add_argument("path", nargs="?", default=None)
    p_watch.add_argument("-o", "--out", default=str(DEFAULT_OUTPUT))
    p_watch.set_defaults(func=cmd_watch)

    p_doc = sub.add_parser("doctor", help="check Ollama and the vision model")
    p_doc.set_defaults(func=cmd_doctor)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
