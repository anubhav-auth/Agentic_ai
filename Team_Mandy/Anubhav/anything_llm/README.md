# docprep — diagram-aware document ingestion

Converts documents to Markdown for a RAG corpus (AnythingLLM), describing
diagrams with a **local** vision model — but **only when diagrams are actually
there**. Text-only documents never touch the LLM.

Everything runs on this machine. Nothing is uploaded anywhere.

---

## The problem this solves

Standard PDF → text extraction reads *letters* and silently discards *pictures*.
Both tools on this laptop do exactly that:

**MarkItDown** ([`_pdf_converter.py`][mid]) is `pdfminer.high_level.extract_text()`.
A PDF of circuit diagrams converts to a nearly empty `.md`, reports success, and
warns you about nothing.

**AnythingLLM** ([`asPDF/index.js`][allm]) already has a gate shaped like this one:

```js
let docs = await pdfLoader.load();
if (docs.length === 0) {              // <-- only when there is ZERO text
  docs = await new OCRLoader({...}).ocrPDF(fullFilePath);
}
```

Read the condition closely. It falls back to OCR only when the PDF yields **no
text at all**. A lecture deck or a paper — text *and* diagrams — returns text
fine, so `docs.length > 0`, the OCR branch never runs, and **every diagram is
dropped without a warning**. And even when it does fire, it's Tesseract: it reads
letters, so a flowchart becomes a bag of disconnected words (`"Client" "Gateway"
"DB"`) with the arrows and the meaning gone.

| | AnythingLLM today | docprep |
|---|---|---|
| Detect | `text.length == 0` | PyMuPDF scan for raster **and vector** figures |
| Describe | Tesseract reads letters | vision LLM explains the diagram |
| Fires on | scanned pages only | any page with a real figure |

---

## Setup

```bash
pip install -e .                # editable install (src layout)
cp .env.example .env
ollama pull qwen2.5vl:3b        # or use OpenRouter/NVIDIA — see .env.example
python -m docprep doctor        # verify the model can actually see
```

Optional — install the lab's parser (heavy, pulls ML models):

```bash
pip install -e ".[docling]"
```

`doctor` is not ceremony. A text-only model (`qwen2.5:7b`) cannot process an
image, and depending on the backend it either errors or **ignores the image and
invents a plausible description from the prompt alone** — a failure that looks
completely normal in the output. `doctor` sends a known image and checks the
answer.

Model choice is constrained by VRAM (this box: RTX 3050, 4GB). `qwen2.5vl:3b`
(~3.2GB) fits fully in VRAM and stays fast. `llava:7b` spills to CPU.

## Swapping the vision backend

Any OpenAI-compatible endpoint works — it's three values in `.env`:

```bash
# FREE + accurate (current default). Uploads figures to OpenRouter.
LLM_BASE_URL=https://openrouter.ai/api/v1
VISION_MODEL=google/gemma-4-26b-a4b-it:free
LLM_API_KEY=sk-or-v1-...

# FREE + private. Nothing leaves the machine, but least accurate.
LLM_BASE_URL=http://localhost:11434/v1
VISION_MODEL=qwen2.5vl:3b
LLM_API_KEY=ollama
```

`doctor` prints which mode you're in and warns on remote. Measured on the same
flowchart fixture (which contains a crossing arrow — the hard case):

| | qwen2.5vl:3b (local) | gemma-4-26b:free | grok-4.20 (paid) |
|---|---|---|---|
| Per figure | 5–21s | 5–20s | **1.7–4.3s** |
| Cost | free | **free** | ~$0.002/figure |
| Privacy | **nothing leaves** | uploaded | uploaded |
| Test flowchart | linked wrong node | **correct** | correct topology, arrow reversed |

`gemma-4-26b-a4b-it:free` is the sweet spot: a 26B model at zero cost that got
the topology exactly right, including the crossing arrow both other models
misread. Its catch is shared capacity — `:free` models return **429** under
load (`gemma-4-31b:free` did, consistently). Retry, switch `:free` model, or
fall back to local.

`:free` models also sidestep an OpenRouter trap: a paid model reserves its whole
output window (65536 tokens) against your balance up front, so a $1-capped key
gets a 402 before generating a single token. Free models reserve nothing.

The gate matters more, not less, on a paid API: text-only documents make **zero
billed calls**.

**Never commit `.env`** — it's in `.gitignore` (this repo has a public remote).
If a key is ever pasted into a chat, a log, or a commit, rotate it.

## Use

```bash
python -m docprep check   report.pdf -v    # triage only: no LLM, no writes
python -m docprep convert report.pdf       # -> output/report.md
python -m docprep convert ./papers -o out  # whole folder
python -m docprep watch                    # auto-process anything in docs/
```

`check` is free and instant — use it to see what the gate thinks before spending
inference on a big batch.

## Routing

| Input | Verdict | What happens | LLM calls |
|---|---|---|---|
| PDF, prose only | `text-only` | MarkItDown text | **0** |
| PDF, text + diagrams | `has-figures` | text + each figure described inline | one per figure |
| PDF, scanned | `scanned` | every page rendered and read | one per page |
| `.png` / `.jpg` | `image` | described directly | 1 |
| `.md` / `.txt` | `passthrough` | left untouched | **0** |
| `.docx` / `.pptx` / … | `text-only` | MarkItDown text (see Limits) | **0** |

## Performance (measured, not estimated)

Triage is effectively free — it is pure parsing:

| Workload | Triage time |
|---|---|
| 16-page report | 22 ms (1.4 ms/page) |
| 423-path chart page | 30 ms |
| 2000 scattered paths | 0.5 s |

The vision model is the entire cost: **~6–8s per figure** warm (~20s on the
first call, while the model loads into VRAM). Which is exactly why the gate
matters. On a 16-page report with 4 diagram pages:

| | LLM calls | Time |
|---|---|---|
| No gate (describe every page) | 16 | 134s |
| **docprep** | **4** | **32s** |

**76% saved**, and the gate found all 4 diagram pages with no false positives on
the other 12. Budget roughly `figures × 7s`; page count barely matters.

## How the gate works

`docprep/triage.py`, no LLM involved. Two kinds of picture look nothing alike
inside a PDF:

- **Raster** — a real embedded bitmap. `page.get_images()`.
- **Vector** — drawing commands, *no bitmap anywhere*. Everything out of
  matplotlib, draw.io, Visio, PowerPoint or TikZ. `page.get_drawings()`.

Catching only raster is the classic bug: a page of architecture diagrams can
contain zero embedded images, so a `get_images()`-only check reports "text only".

**Telling a diagram from a table** is the hard part — both are swarms of vector
paths, so "many paths ⇒ diagram" flags every table in the document. The
discriminator is dimensionality: a table is built from **1D rules** (hairlines);
a diagram has **2D shapes and curves** (boxes, nodes, arrowheads). So lines still
extend a figure's bounds — an arrow is part of the picture — but only shapes and
curves vote on whether it *is* one. `tests/fixtures/table.pdf` guards this.

Small pictures are rejected by area (≥1.5% of page), side (≥40pt) and aspect
ratio (≤20:1) — that's what stops logos, icons and horizontal rules.

Figures are sent to the model as a **rendered page region**, not an extracted
bitmap: a vector diagram has no bitmap to extract, and axis labels are very often
separate text objects layered *on top of* an image rather than part of it.

## Tuning

Copy `.env.example` to `.env`. The two that matter:

- `VECTOR_MIN_SHAPES` (4) — raise if tables get flagged; lower if simple 3-box
  diagrams are missed.
- `MIN_AREA_RATIO` (0.015) — raise if logos get described; lower if small
  diagrams are missed.

Use `check -v` after any change; it costs nothing.

**Do not raise `MAX_RENDER_PX` without also raising `NUM_CTX`.** Vision models
bill by pixel area (~28×28px per token), so image size and context are coupled.
Ollama's default 4096 context cannot fit even one full A4 page at 200 DPI
(~4200 image tokens), which is why `NUM_CTX=8192` is the default here.

## Feeding AnythingLLM

```bash
python -m docprep ingest ./papers -w "SOA Notes"
```

Converts, uploads, creates the workspace if absent, and embeds — the vectors go
wherever AnythingLLM is configured to put them (here: local native embeddings
into cloud Qdrant). Re-running **replaces** what it wrote before rather than
stacking duplicate chunks, which otherwise crowd retrieval with near-identical
hits.

It uploads the `.md`, never the original PDF. Hand AnythingLLM the PDF and its
own collector runs, which drops every image — throwing away exactly the figure
descriptions this project exists to produce. Markdown routes through its plain
text path and survives verbatim.

Needs `ANYTHINGLLM_API_KEY` in `.env` (Settings → Tools → Developer API) and
AnythingLLM running.

### Running AnythingLLM from source

The desktop app is not required — it is an Electron wrapper around a plain Node
server. Running `../anything-llm` from source is better here: the Qdrant fix
below lives in real source you can read and keep, rather than a patch to a
minified bundle that any app update silently reverts.

```bash
cd ../anything-llm
(cd server && npm install --legacy-peer-deps)      # --legacy-peer-deps: the repo
(cd collector && npm install --legacy-peer-deps)   # targets yarn; npm 10 rejects
(cd frontend && npm install --legacy-peer-deps)    # an apache-arrow/lancedb clash
(cd server && npx prisma generate)

# server/.env  -- point STORAGE_DIR at the desktop storage to reuse its
# workspaces and encryption keys, or anywhere for a clean start.
#   SERVER_PORT=3001
#   STORAGE_DIR="...anythingllm-desktop\storage"
#   DATABASE_URL="file:...\anythingllm.db"
# frontend/.env
#   VITE_API_BASE='http://localhost:3001/api'

npm run dev    # server :3001, collector :8888, frontend :3000
```

`SIG_KEY`/`SIG_SALT` must match whatever wrote the storage, or previously
encrypted values fail to decrypt.

### Two AnythingLLM bugs you will hit

**Qdrant Cloud never connects.** The Qdrant JS client defaults to port 6333;
Qdrant Cloud serves 443. AnythingLLM passes only `url`, so it always tries 6333
and every embed fails with `fetch failed` — while still reporting success.
Putting `:443` in `QDRANT_ENDPOINT` does **not** help: the client ignores an
inline port. The only fix is code — `new QdrantClient({url, port: null})`.

**Chat 402s on a credit-capped OpenRouter key**, because AnythingLLM sends no
`max_tokens` and OpenRouter reserves the model's full output window. Use a
`:free` model or raise the key's limit.

Neither is caused by docprep; both silently break ingestion.

## Agent web search (AnythingLLM)

Enabling the agent's web-search skill needs no paid key — **DuckDuckGo** scrapes
`html.duckduckgo.com` directly, unlike Google/Brave/Serper which all require a
signup. Two settings in AnythingLLM's `system_settings`:

| Setting | Value |
|---|---|
| `agent_search_provider` | `duckduckgo-engine` |
| `default_agent_skills` | `["web-browsing"]` |

Set them in the UI (**Settings → Agent Skills**), then use `@agent` in any chat:

```
@agent search the web for the current stable version of Python
```

One gotcha worth knowing: DuckDuckGo blocks a bare `curl` (HTTP 202, no results)
but serves Node's `fetch` fine — which is what the server uses, so it works.

### SQL Connector (Postgres)

The agent can query a real database. Two things matter:

**Connect as a read-only role.** The dialog's warning is not boilerplate — the
agent is only *instructed* to avoid writes, so an LLM hallucinating a `DELETE`
is a live risk. A grant makes it structurally impossible:

```sql
CREATE ROLE llm_readonly WITH LOGIN PASSWORD '...';
GRANT CONNECT ON DATABASE mydb TO llm_readonly;
GRANT USAGE  ON SCHEMA public TO llm_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO llm_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO llm_readonly;
```

Verify it: `SELECT` succeeds, `DELETE FROM orders` returns *permission denied*.

**The connection string scheme is `postgres://`, not `postgresql://`.** The
connector rejects the longer form with `URI must start with 'postgres://'` — and
it fails *late*: schema discovery (`sql-list-tables`, `sql-get-table-schema`)
succeeds, so the agent looks like it is working right up until the first real
query. Stored in `system_settings.agent_sql_connections`:

```json
[{ "database_id": "soa_demo", "engine": "postgresql",
   "connectionString": "postgres://llm_readonly:...@localhost:5432/soa_demo" }]
```

### Free tool-calling models for the agent

Agents run a multi-step tool loop, so they burn far more calls than a chat turn
and hit free-tier rate limits fast. Of 17 free OpenRouter models, 14 advertise
tool support; these were measured on a real `tools=` call:

| Model | Tool call | Time | Note |
|---|---|---|---|
| `nvidia/nemotron-3-super-120b-a12b:free` | yes | 1.3s | 120B, 1M ctx — best free agent model |
| `google/gemma-4-26b-a4b-it:free` | yes | 1.7s | fine for chat, **429s under agent load** |
| `openai/gpt-oss-20b:free` | yes | 3.9s | open-weights |
| `nvidia/nemotron-3-nano-30b-a3b:free` | **no** | 2.4s | replies in prose, ignores the tool |
| `nvidia/nemotron-nano-12b-v2-vl:free` | no | 6.0s | but **vision-capable** — usable for figures |

Set the agent model per workspace (`workspaces.agentModel`), not just globally:
a workspace with none set falls back to the system LLM, which is how a working
agent silently starts 429ing in a newly created workspace.

`nemotron-3-super-120b` also satisfies a brief that asks for an **NVIDIA
open-weights model** without needing an NVIDIA account — it is free on
OpenRouter.

## Limits — read before trusting it

- **A 3B model makes mistakes.** On the test flowchart it attributed an arrow to
  the wrong node (said Auth Service → PostgreSQL; it's actually Order Service →
  PostgreSQL). It reliably gets *nodes*; it can misread *crossing arrows*. Use a
  larger vision model if that matters.
- **Office formats aren't triaged yet.** `.docx`/`.pptx` get text only —
  embedded pictures are dropped, same as AnythingLLM does today. The
  [`markitdown-ocr`][ocr] plugin already handles image extraction for these and
  takes any OpenAI-compatible client, so it's the natural next step.
- **Descriptions aren't deterministic** even at `temperature=0.1`. Re-running
  changes the wording.
- The gate is heuristic. It's tuned against `tests/fixtures/`, not against your
  actual documents — check it on those.
- **Corrupt and password-protected PDFs are skipped, not converted.** They
  report `UNREADABLE` rather than emitting a blank `.md`, because a silently
  empty document in the corpus is worse than an absent one.

## Parser backends

The text-extraction step is swappable via `PARSER` in `.env`:

| `PARSER` | Engine | Speed | Notes |
|---|---|---|---|
| `markitdown` (default) | MarkItDown + PyMuPDF | ~0.1s/pg | no ML models, wide format support |
| `docling` | IBM Docling | ~4s/pg | layout-aware, better tables; needs `.[docling]` |

Neither engine describes diagrams — Docling emits a bare `<!-- image -->` marker
where a figure sits and drops its content. That marker is the whole point: it's
the gap docprep's triage + vision layer fills, whichever parser you pick.

## Layout

```
docs/           source data — drop your PDFs here (the lab's /docs)
  samples/      three demo PDFs
src/
  docprep/      ingestion package (the lab's /src)
    config.py   tunables (env-overridable)
    triage.py   THE GATE — figure detection, no LLM
    vision.py   vision client + rendering + doctor preflight
    parsers.py  markitdown | docling text-extraction backends
    pipeline.py routing: triage -> parse -> describe -> .md
    anythingllm.py  AnythingLLM ingest client
    watch.py    docs/ folder watcher
    cli.py      check | convert | ingest | watch | doctor
output/         generated .md
tests/
  make_fixtures.py   regenerates the six PDFs the gate is tested against
```

[mid]: ../markitdown/packages/markitdown/src/markitdown/converters/_pdf_converter.py
[allm]: ../../Users/ritzr/OneDrive/Desktop/Anything%20Llm/anything-llm/collector/processSingleFile/convert/asPDF/index.js
[ocr]: ../markitdown/packages/markitdown-ocr/
