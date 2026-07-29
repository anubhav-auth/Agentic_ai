"""Push converted Markdown into an AnythingLLM workspace.

Uses AnythingLLM's Developer API (verified against the cloned server source):

    GET  /v1/auth                              -- validate the API key
    POST /v1/workspace/new                     -- {name} -> {workspace:{slug}}
    GET  /v1/workspaces                        -- list existing
    POST /v1/document/upload                   -- multipart, field "file"
                                                  -> {documents:[{location}]}
    POST /v1/workspace/:slug/update-embeddings -- {adds:[location]}

All authenticated with `Authorization: Bearer <key>`.

Why upload .md rather than the original PDF: AnythingLLM's collector routes .md
straight through its text path, so it copies our content verbatim. Hand it the
PDF instead and its own converter runs -- which drops every image and throws
away exactly the figure descriptions this project exists to produce.

Embedding is done by AnythingLLM using whatever it is configured for (here:
native/local embeddings into cloud Qdrant), so this module never touches the
vector store directly.
"""

from __future__ import annotations

import re
from pathlib import Path

import httpx

from .config import settings


class AnythingLLMError(RuntimeError):
    pass


class AnythingLLM:
    def __init__(self, url: str | None = None, api_key: str | None = None) -> None:
        self.url = (url or settings.anythingllm_url).rstrip("/")
        self.api_key = api_key or settings.anythingllm_api_key
        if not self.api_key:
            raise AnythingLLMError(
                "No API key. In AnythingLLM: Settings -> Tools -> Developer API "
                "-> Generate New API Key, then put it in .env as "
                "ANYTHINGLLM_API_KEY=..."
            )
        self._client = httpx.Client(
            base_url=f"{self.url}/api",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=settings.anythingllm_timeout,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AnythingLLM":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def _json(self, resp: httpx.Response, what: str) -> dict:
        if resp.status_code == 403:
            raise AnythingLLMError(f"{what}: API key rejected (403)")
        if resp.status_code >= 400:
            raise AnythingLLMError(f"{what}: HTTP {resp.status_code} {resp.text[:200]}")
        try:
            return resp.json()
        except Exception as exc:
            raise AnythingLLMError(f"{what}: bad JSON ({exc})") from exc

    # ---------- connection ----------

    def ping(self) -> None:
        try:
            resp = self._client.get("/v1/auth")
        except httpx.ConnectError as exc:
            raise AnythingLLMError(
                f"Cannot reach AnythingLLM at {self.url}.\n"
                f"Is the app running? The desktop app must be OPEN -- it only "
                f"serves the API while the window is up."
            ) from exc
        self._json(resp, "auth")

    # ---------- workspaces ----------

    def workspaces(self) -> list[dict]:
        return self._json(self._client.get("/v1/workspaces"), "list workspaces").get(
            "workspaces", []
        )

    def find_or_create_workspace(self, name: str) -> str:
        """Return the slug, reusing an existing workspace of the same name.

        Idempotent on purpose: re-running ingest should top up one workspace,
        not litter the sidebar with duplicates.
        """
        for ws in self.workspaces():
            if ws.get("name", "").lower() == name.lower():
                return ws["slug"]

        body = self._json(
            self._client.post("/v1/workspace/new", json={"name": name}),
            "create workspace",
        )
        slug = (body.get("workspace") or {}).get("slug")
        if not slug:
            raise AnythingLLMError(f"create workspace: no slug returned ({body})")
        return slug

    # ---------- documents ----------

    def upload(self, path: Path) -> str:
        """Upload a file; returns its storage location (the embed handle)."""
        with path.open("rb") as fh:
            resp = self._client.post(
                "/v1/document/upload",
                files={"file": (path.name, fh, "text/markdown")},
            )
        body = self._json(resp, f"upload {path.name}")
        if not body.get("success", False):
            raise AnythingLLMError(f"upload {path.name}: {body.get('error')}")
        docs = body.get("documents") or []
        if not docs or not docs[0].get("location"):
            raise AnythingLLMError(f"upload {path.name}: no location returned")
        return docs[0]["location"]

    def embed(self, slug: str, locations: list[str]) -> None:
        """Attach documents to a workspace, which triggers embedding."""
        if not locations:
            return
        self._json(
            self._client.post(
                f"/v1/workspace/{slug}/update-embeddings", json={"adds": locations}
            ),
            "update embeddings",
        )

    # ---------- replacing, not duplicating ----------

    def workspace_documents(self, slug: str) -> list[dict]:
        body = self._json(self._client.get(f"/v1/workspace/{slug}"), "get workspace")
        ws = body.get("workspace")
        # This endpoint has returned both a list and an object across versions.
        if isinstance(ws, list):
            ws = ws[0] if ws else {}
        return (ws or {}).get("documents", []) or []

    def purge_previous(self, slug: str, stems: set[str]) -> int:
        """Remove earlier copies of the same source documents.

        Every upload gets a fresh UUID, so re-running ingest silently stacks a
        second, third, fourth copy of the same file into the workspace. In a RAG
        corpus that is actively harmful: retrieval fills its slots with near
        identical chunks and crowds out other documents. So each run replaces
        what it wrote before rather than piling on.
        """
        existing = self.workspace_documents(slug)
        doomed_locations: list[str] = []
        doomed_names: list[str] = []

        for doc in existing:
            docpath = doc.get("docpath") or ""
            # docpath comes back as an absolute Windows path with backslashes
            # ("C:\...\custom-documents\notes.md-<uuid>.json"), so splitting on
            # "/" alone finds nothing and every stale copy survives.
            parts = re.split(r"[\\/]", docpath)
            name = parts[-1]
            # "vector_diagram.md-<uuid>.json" -> "vector_diagram.md"
            stem = name.split(".md-")[0] + ".md" if ".md-" in name else name
            if stem not in stems:
                continue

            doomed_locations.append(docpath)
            # remove-documents resolves names against the documents dir, so it
            # needs "custom-documents/<file>.json". Handing it the absolute path
            # returns 200 and deletes nothing -- the workspace link drops but the
            # file lingers, and the UI's document picker fills with duplicates.
            folder = parts[-2] if len(parts) > 1 else "custom-documents"
            doomed_names.append(f"{folder}/{name}")

        if not doomed_locations:
            return 0

        # Detach from the workspace first (drops the vectors), then delete the
        # files. Reverse order would strand vectors pointing at missing docs.
        self._json(
            self._client.post(
                f"/v1/workspace/{slug}/update-embeddings",
                json={"deletes": doomed_locations},
            ),
            "delete embeddings",
        )
        # httpx's .delete() convenience method takes no body, and this endpoint
        # is a DELETE that requires one -- .request() is the only way to send it.
        self._json(
            self._client.request(
                "DELETE", "/v1/system/remove-documents", json={"names": doomed_names}
            ),
            "remove documents",
        )
        return len(doomed_names)
