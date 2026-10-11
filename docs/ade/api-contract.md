---
title: The API contract
---

Guide
{ .eyebrow }

# The API contract

The ADE Gen2 request and response shapes, read from the published OpenAPI spec, and why a replacement pipeline should emit exactly this.
{ .lead }

Source for everything on this page: [openapi-adev2.json](https://docs.landing.ai/dpt3/openapi-adev2.json) (title: "LandingAI Agentic Document Extraction (ADE) Gen2 API: Parse, Extract, and Ground Documents with DPT-3", server `https://api.ade.landing.ai`) and [Parse API response](https://docs.landing.ai/dpt3/parse-response).

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/v2/parse` | parse synchronously (priority tier) |
| POST | `/v2/parse/jobs`, GET `/v2/parse/jobs`, GET `/v2/parse/jobs/{job_id}` | parse as a job |
| POST | `/v2/extract` | extract synchronously |
| POST | `/v2/extract/jobs`, GET `/v2/extract/jobs`, GET `/v2/extract/jobs/{job_id}` | extract as a job |
| POST | `/v2/ground` | map extracted ranges to blocks |

## Parse request

Multipart form: `document` (file) or `document_url`; `model` (`dpt-3-pro`, `dpt-3-pro-latest`, `dpt-3-pro-20260710`, `dpt-3-verity`, `dpt-3-verity-20260804-preview`); `options` as a JSON string:

```json
{
  "pages": [1, 3],
  "blocks": {"table": {"format": "html", "markdown": true}, "figure": {"markdown": true}, "text": {"markdown": true}},
  "atomic_grounding": true,
  "inline_markdown": false
}
```

`blocks.<type>.markdown=false` suppresses that type's markdown and empties its `atomic_grounding`; `inline_markdown=true` copies each node's slice of the markdown onto the node. Jobs add `service_tier` (`standard` or `priority`), `output_save_url`, and webhooks.

## Parse response

```json
{
  "markdown": "# 제목\n\n본문…\n\n<!-- PAGE BREAK -->\n\n…\n<!-- doc_id=parse-01J… -->",
  "metadata": {
    "job_id": "parse-01J…", "model_version": "dpt-3-pro-20260710", "page_count": 12,
    "output_markdown_chars": 18342, "range_units": "unicode_codepoints", "failed_pages": [],
    "duration_ms": 9400, "billing": {"service_tier": "standard", "total_credits": 3.2},
    "openapi_spec": "https://docs.landing.ai/dpt3/openapi-adev2.json"
  },
  "structure": {
    "type": "document",
    "children": [
      {"type": "page", "status": "ok",
       "grounding": {"page": 1, "range": {"start": 0, "end": 1620}, "box": {"xmin": 0, "ymin": 0, "xmax": 1, "ymax": 1}},
       "children": [
         {"type": "text", "id": "text-0",
          "grounding": {"page": 1, "range": {"start": 0, "end": 24}, "box": {"xmin": 0.06, "ymin": 0.05, "xmax": 0.7, "ymax": 0.11}},
          "atomic_grounding": [{"page": 1, "range": {"start": 0, "end": 24}, "box": {"xmin": 0.06, "ymin": 0.05, "xmax": 0.7, "ymax": 0.11}}]},
         {"type": "table", "id": "table-0",
          "grounding": {"page": 1, "range": {"start": 600, "end": 1410}, "box": {"xmin": 0.52, "ymin": 0.3, "xmax": 0.95, "ymax": 0.8}},
          "children": [
            {"type": "table_cell", "id": "table_cell-0", "row": 0, "col": 0, "rowspan": 1, "colspan": 2,
             "grounding": {"page": 1, "range": {"start": 640, "end": 652}, "box": {"xmin": 0.52, "ymin": 0.3, "xmax": 0.7, "ymax": 0.34}},
             "atomic_grounding": []}
          ]}
       ]}
    ]
  }
}
```

The values are illustrative; the field names, nesting and conventions are the spec's.

### The rules that matter

- **`range` is `[start, end)` in Unicode code points** into the one `markdown` string. JavaScript strings are UTF-16, so a naive `slice` drifts on astral characters; the spec says so explicitly. Korean syllables are in the BMP, but emoji in slides are not.
- **Ids are `<type>-<index>`**, a per-type counter in reading order, "stable within a response but not across re-parses."
- **Boxes are normalised 0..1** with at most five decimals; multiply by the rendered page size to get pixels. Page boxes are always `{0,0,1,1}`.
- **`atomic_grounding`** is present on every leaf type except `table`: one entry per visual line for Pro, one per word with `confidence` for Verity. `table_cell` has `[]` on a line-granularity model.
- **Failed pages stay in the tree** with `status: "failed"`, a `reason`, a zero-length range and no children, and appear in `metadata.failed_pages`; the response is HTTP 206 and credits are charged.
- **Markdown conventions:** `<!-- PAGE BREAK -->` between pages, `<figure type="CHART">…<description>…</description></figure>`, `[SIGNED]` / `[STAMPED]` / `[SEALED]` on attestations, `[X]` / `[]` checkboxes, HTML tables by default, `<!-- doc_id=… -->` as the last line.
- **Errors** are `{"code", "message"}`; branch on `code`.

## Extract and Ground

Extract takes `markdown` (string, any source) and `schema` (JSON Schema; descriptions act as prompts), optional `model` (`extract-latest`, dated snapshots) and `options.strict`. It returns `extraction` (values; `null` when not found, `[]` for arrays), `extraction_metadata` (the same tree with each leaf as `{value, ranges}`; `ranges: null` means the value was synthesised), and `metadata` with `doc_id` when the markdown carried the comment.

Ground takes `structure` and `extraction_metadata` and returns `grounding`, the metadata tree with each leaf replaced by the list of overlapping blocks (`block_id`, `type`, `parent_id`, `grounding`, the overlapping `atomic_grounding` subset). `null` means nothing was quoted; `[]` means the inputs came from different parses, which Ground cannot detect, so compare `metadata.doc_id` with `metadata.job_id` in code first.

## Why emit this shape

Every downstream consumer LandingAI has published (the agent skill, the sample projects, the CLI's crop and highlight commands) reads `markdown` plus `structure`. A local pipeline that writes the same JSON gets all of that tooling, can be A/B tested against ADE with one comparison script ([evaluation](../build/evaluation.md)), and can be swapped for ADE per document class without touching the consumers. `pipeline/korean_slides/ade_schema.py` is a Pydantic transcription of these schemas.
