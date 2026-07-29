# /docs — source data

Drop the PDFs (or DOCX/PPTX/XLSX/images) you want to ingest here. This is the
lab's **source data** pathway; the ingestion scripts live in [/src](../src).

```bash
# triage only — free, instant, no model, writes nothing
python -m docprep check docs/samples -v

# convert to Markdown in ./output
python -m docprep convert docs/samples

# convert AND push into an AnythingLLM workspace
python -m docprep ingest docs/samples -w "SOA Notes"
```

`samples/` holds three small demonstration PDFs that exercise the interesting
paths (a vector flowchart, a scanned page with no text layer, and a dense
chart). Your own documents — e.g. the Microsoft market-data PDFs from the lab —
go directly in `docs/` and are gitignored so the repo stays small.
