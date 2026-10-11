---
title: Evaluation recipe
---

Build
{ .eyebrow }

# Evaluation recipe

How to measure parsing quality and latency on your own Korean decks, and how to put ADE's output on the same scale so "almost as good as LandingAI" becomes a number.
{ .lead }

## Why you have to build the set yourself

No public benchmark covers Korean slide parsing. OmniDocBench is Chinese and English pages, olmOCR-bench is English PDFs, and the Korean visual-document benchmarks (KoViDoRe, SDS KoPub VDR) measure retrieval, not transcription. Thirty to fifty slides of your own, annotated once, are worth more than any leaderboard for this decision.

## The set

| Bucket | Slides | Why |
|---|---|---|
| Digital, text-heavy (two columns, 8 to 10 pt) | 10 | the common case; tests the text layer path and reading order |
| Digital with borderless tables and merged headers | 10 | the table path, TEDS |
| Digital with charts and diagrams | 10 | figure descriptions; judged, not string-matched |
| Scanned or flattened exports of the same kinds | 10 to 20 | the VLM-only path and the collapse repair |

Keep the PPTX where you have it: the text layer makes ground truth cheap.

## Ground truth

1. Run the pipeline once with `--dry-run` disabled and the best model you have; this gives you the ADE-shaped JSON to correct rather than write.
2. Fix the markdown by hand per page: reading order, every character, tables as HTML with `rowspan`/`colspan`. For digital decks, paste from the PPTX text layer and only fix order and structure.
3. For figures, write a two-line reference description that names what a good description must contain (axis, unit, the key number). This is a rubric, not a target string.
4. Save as `gt/<deck>/parse-response.json` in the same shape; only `markdown`, the page ranges and the block boxes need to be right.

## Metrics

| Metric | Computed by | Applies to |
|---|---|---|
| CER on NFC-normalised text with HTML and markdown punctuation stripped | `pipeline/eval/compare.py` | text and marginalia blocks per page |
| Reading-order Kendall tau, blocks matched by box centre | `compare.py` | pages with 2+ blocks |
| TEDS for tables | OmniDocBench's `teds` implementation on the table HTML | table blocks |
| Figure description rubric: axis named, unit named, key number present, no invented number | an LLM judge with the rubric, or a human | figure blocks |
| Context quality: does the per-slide argument match the deck author's intent | human, 1 to 5 | `context.json` |
| Latency per stage per slide | `out/<deck>/timings.json` written by `run.py` | the five-second budget |

```bash
.venv/bin/python -m pipeline.eval.compare out/deck/parse-response.json gt/deck/parse-response.json
# page   1  CER 0.012  order-tau 1.0
# ...
# mean CER 0.031 over 40 pages
```

Report CER separately for the text-layer path and the VLM path: the first should be near zero, the second is the number you are tuning.

## The ADE comparison

With an ADE API key, parse the same files with DPT-3 Pro:

```bash
pip install landingai-ade
export VISION_AGENT_API_KEY=...
.venv/bin/python -m pipeline.eval.run_ade decks/*.pdf --out out/ade
.venv/bin/python -m pipeline.eval.compare out/ade/deck/parse-response.json gt/deck/parse-response.json
```

`run_ade.py` writes the same `parse-response.json` shape plus a `timing.json` with ADE's own `duration_ms` and the credits charged, so one table compares your pipeline and ADE on CER, TEDS, order, figure rubric, seconds per slide and cost per slide. That table is the deliverable; everything else on this wiki is how to make its numbers move.

## Timing harness

`run.py` records `layout_s`, `read_s`, `verify_s` and `total_s` per page. For the budget, report the 95th percentile of `total_s` per bucket, not the mean; a dense scanned page with a large table is the one that misses five seconds, and the median hides it. Run with the same vLLM settings you will deploy (`--max-num-seqs`, `max_pixels` from the decision layer), on an otherwise idle card, and with at least 50 pages so the batching behaviour is representative.

## Retrieval split

If the corpus will be searched, add 30 Korean questions whose answer is on one known slide (the KoViDoRe construction: summary-based and context-based queries, human-verified) and report nDCG@10 for the text track, the image track and the fused and reranked result. The models to compare are on the [embeddings page](embeddings.md).
