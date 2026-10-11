# Agentic Document Parsing Wiki

Research notes on how LandingAI's Agentic Document Extraction (ADE, DPT-3) works,
and how to build an equivalent pipeline for dense Korean slide decks with
open-weight vision-language models (Qwen and alternatives from Hugging Face).

Live site: https://swchoi1994.github.io/agentic-doc-parsing-wiki/

## Local preview

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/mkdocs serve
```

## Reference pipeline

`pipeline/` holds the reference implementation described in the wiki
(render, layout, per-block reading, slide context, verification, ADE-shaped output).
See `pipeline/README.md`.

Not affiliated with LandingAI, Alibaba Qwen, or any model vendor.
