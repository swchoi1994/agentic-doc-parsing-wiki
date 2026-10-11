---
title: Korean benchmarks and models
---

Research
{ .eyebrow }

# Korean benchmarks and models

Everything Korean-specific found while building this wiki: benchmarks, models, datasets, and the quirks of Korean text that a parser has to get right.
{ .lead }

## Benchmarks

| Name | What | Size | Source |
|---|---|---|---|
| **KoViDoRe** | Korean visual document retrieval across public documents with tables, figures, multi-column layouts; queries built by structured parsing, summary- and context-based synthetic generation, human-verified relevance; four domains (Cybersecurity, Economic, Energy, HR); also releases Ko-VDR Train Public | not stated in the abstract | [arXiv 2608.20840](https://arxiv.org/abs/2608.20840), MAGMaR 2026 |
| **SDS KoPub VDR** | first large public benchmark for retrieving and understanding Korean public documents; 361 documents (256 KOGL Type-1, 105 legal portals), 600 query-page-answer items, six public-sector domains, queries typed as text, visual or cross-modal | 600 | [arXiv 2511.04910](https://arxiv.org/abs/2511.04910) |
| **upstage/dp-bench** | document parsing benchmark from Upstage, 200 samples (20 internal) | 200 | [Hugging Face](https://huggingface.co/datasets/upstage/dp-bench) |
| Korean MTEB subsets | text retrieval and STS for embedding selection | varies | MTEB leaderboard |

Nothing public measures Korean *slide parsing*; see the [evaluation recipe](../build/evaluation.md).

## Models

| Model | Type | Notes |
|---|---|---|
| [whybe-choi/kovre](https://huggingface.co/whybe-choi/kovre) | visual document embedding, 2B, Apache-2.0 | Qwen3-VL-Embedding-2B fine-tuned on 708,729 Korean/English query-page pairs plus reranker distillation; best overall on KoViDoRe + SDS KoPub (0.592 nDCG@10) among the models in its table; MRL 128 to 2048 |
| [nlpai-lab/KURE-v1](https://huggingface.co/nlpai-lab/KURE-v1) | text embedding, 568M, MIT | BGE-M3 fine-tuned for Korean retrieval; Korean-only |
| Qwen3-VL (2B to 235B) | general VLM | Korean named in the OCR language list since Qwen2-VL; 32 OCR languages in Qwen3-VL |
| Qwen3-VL-Embedding / Reranker (2B, 8B) | multimodal retrieval | 33 languages including Korean |
| Upstage Document Parse (`document-parse-260930`) | commercial API from a Korean vendor | end-to-end VLM parser in enhanced mode; no open weights; a useful second quality bar next to ADE if you can get a key |
| PaddleOCR (classic) and PaddleOCR-VL | OCR / parser | Korean recognition models exist in the classic PaddleOCR line; the VL line claims 109 languages |

## What the KoVRE paper teaches about Korean training data

From the controlled experiments ([arXiv 2608.01389](https://arxiv.org/abs/2608.01389)):

- A **bilingual Korean + English** visual-document mixture beat Korean-only data overall.
- Adding a Korean **text** triplet dataset (ko-triplet-v1.0) *reduced* visual retrieval performance; the final stage-1 mix is visual-document data only.
- Distilling from Qwen3-VL-Reranker-8B on Korean data helped on every benchmark, but only with per-query min-max normalisation of the teacher scores; without it, distillation fell below the stage-1 checkpoint.
- A 2B model at 256 dimensions edged out an 8B model at 4,096 dimensions.

If you fine-tune anything for Korean decks (the parser, the embedder, or the reranker), these are the four knobs that mattered.

## Korean text details a parser must handle

- **Normalise to NFC** before any comparison. Hangul syllables can appear as precomposed (NFC) or as jamo sequences (NFD, common in files that passed through macOS); CER on unnormalised text punishes the model for a representation difference.
- **Spacing (띄어쓰기) is content**, not formatting. Korean word spacing changes meaning and is frequently inconsistent in slides; the prompts in this pipeline tell the model to keep the original spacing, and the verifier compares against the text layer rather than "correcting" it.
- **Mixed scripts on one line.** Hangul, Hanja, Latin acronyms and digits with units (억 원, %, bp) sit together; tokenisation and resolution both matter, and the figure prompt asks for units explicitly.
- **Vertical and rotated text** appears in table headers and chart axes; check whether your layout detector handles rotated boxes before trusting its table headers.
- **Fonts.** Thin sans-serif Korean fonts at 8 pt lose strokes at 150 DPI; render at 200 DPI or higher, and crop-read dense blocks at native resolution.
