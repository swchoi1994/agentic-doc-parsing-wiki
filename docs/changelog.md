---
title: Changelog
---

Changelog
{ .eyebrow }

# Changelog

What landed in this wiki, newest first.
{ .lead }

## 2026-10-12

- **How DPT-3 works:** evidence-graded reconstruction with documented / implied / unknown chips, version timeline, and black-box probes to run with an API key.
- **Korean slides pipeline:** six stages, five-second budget table, Korean prompts, resolution math; reference code in `pipeline/korean_slides/` with a dry-run mode and a `verify.decide()` policy left for the reader.
- **Model candidates:** Qwen3-VL, Qwen3.5, Qwen3.8 and the 1B parsers (PaddleOCR-VL-1.6, OvisOCR2, HPD-Parsing, dots.ocr, DeepSeek-OCR) with code and published results, and the recommended combination.
- **Embeddings and retrieval:** two-track design, the KoVRE Korean benchmark table, chunking from the ADE-shaped output, encoding and fusion code.
- **Hardware and serving:** what fits on 2x/4x A100 40/80 GB, vLLM commands, Qwen3.5/3.8 caveats on A100, vLLM Semantic Router as the serving-side decision layer, TPU as a hypothesis, M1 Max for development.
- **Evaluation recipe:** eval-set buckets, ground-truth protocol, CER/order/TEDS/rubric metrics, `pipeline/eval/compare.py`, `pipeline/eval/run_ade.py`, timing harness.
- **Research:** two-stage vs end-to-end, agentic repair loops, slide understanding, benchmark blind spots; Korean benchmarks, models and text details.
- **What LandingAI built**, **The API contract**, **What REA revealed**.
- Site scaffold: MkDocs Material themed after docs.landing.ai, deployed by GitHub Actions.
