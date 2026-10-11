# Reference pipeline: ADE-shaped parsing for dense Korean slides

Six stages, one output shape (the ADE Gen2 Parse response: `markdown` + `structure` + `metadata`).
The wiki page [Korean slides pipeline](https://swchoi1994.github.io/agentic-doc-parsing-wiki/build/pipeline/)
explains each stage; this folder is the code it points at.

```
korean_slides/
  ade_schema.py   Pydantic models of the ADE Gen2 response (Document, Page, Element, Grounding)
  render.py       Stage 1: PPTX/PDF -> page images + text layer + speaker notes
  route.py        Stage 2: decision layer (page class, reader choice, resolution, layout)
  read.py         Stage 3: per-block reading with a VLM (OpenAI-compatible, e.g. vLLM)
  context.py      Stage 4: deck outline and per-slide argument (the "understand the slide" pass)
  verify.py       Stage 5: checks + the retry policy (one function left for you to write)
  assemble.py     Stage 6: markdown + structure tree with code-point ranges and boxes
  run.py          CLI
```

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r pipeline/requirements.txt
# a VLM server (see wiki: Hardware and serving), e.g.
#   vllm serve Qwen/Qwen3-VL-8B-Instruct --max-model-len 16384 --limit-mm-per-prompt '{"image":4}'
.venv/bin/python -m pipeline.korean_slides.run deck.pptx --out out/deck \
    --vlm-base-url http://localhost:8000/v1 --vlm-model Qwen/Qwen3-VL-8B-Instruct

# no GPU at hand? exercise the whole path with the stub reader:
.venv/bin/python -m pipeline.korean_slides.run deck.pdf --out out/deck --dry-run
```

Outputs: `out/deck/parse-response.json` (ADE shape), `out/deck/parse-output.md`,
`out/deck/pages/*.png`, `out/deck/context.json` (deck outline and per-slide arguments),
`out/deck/verify.jsonl` (what was retried and why).

`soffice` (LibreOffice) is needed for PPTX; PDFs need only PyMuPDF.
