"""Folder watcher -- the "right after uploading" trigger.

Drop a file into docs/ and it gets converted into output/.
"""

from __future__ import annotations

import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .pipeline import Pipeline


def _settled(path: Path, checks: int = 3, interval: float = 0.4) -> bool:
    """Wait until a file stops growing.

    A watcher fires the moment a file is *created*, which for anything bigger
    than a few KB is long before the copy has finished. Parsing then hits a
    truncated PDF. So we poll the size until it holds steady.
    """
    last = -1
    stable = 0
    for _ in range(60):
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return False
        if size == last and size > 0:
            stable += 1
            if stable >= checks:
                return True
        else:
            stable = 0
            last = size
        time.sleep(interval)
    return False


class _Handler(FileSystemEventHandler):
    def __init__(self, pipeline: Pipeline) -> None:
        self.pipeline = pipeline
        self._seen: set[str] = set()

    def _handle(self, path: Path) -> None:
        key = str(path.resolve())
        if key in self._seen:
            return
        if not _settled(path):
            print(f"SKIP  {path.name} -- file never finished copying")
            return
        self._seen.add(key)

        print(f"\n--> {path.name}")
        try:
            print("    " + self.pipeline.process(path).summary())
        except Exception as exc:
            print(f"    FAIL {path.name} -- {exc}")

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._handle(Path(str(event.src_path)))

    def on_moved(self, event: FileSystemEvent) -> None:
        # Browsers and Explorer often write a .part/.tmp then rename into place,
        # so the finished file arrives as a move, never as a create.
        if not event.is_directory:
            self._handle(Path(str(event.dest_path)))


def watch(inbox: Path, out_dir: Path) -> None:
    pipeline = Pipeline(out_dir)
    handler = _Handler(pipeline)

    # Anything already sitting in the inbox at startup.
    for existing in sorted(p for p in inbox.iterdir() if p.is_file()):
        handler._handle(existing)

    observer = Observer()
    observer.schedule(handler, str(inbox), recursive=False)
    observer.start()
    print(f"\nWatching {inbox}\nWriting  {out_dir}\nCtrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")
        observer.stop()
    observer.join()
