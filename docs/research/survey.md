---
title: How others solved it
---

Research
{ .eyebrow }

# How others solved it

The 2025 to 2026 document-parsing literature and the vendor architectures, read for what they say about dense pages, decomposition, and slides.
{ .lead }

## Two-stage versus end-to-end

The field split into two camps and then started borrowing from each other.

**Two-stage (cascaded).** A layout detector finds regions, a recogniser reads each one, a post-processor orders and merges. MinerU and PaddleOCR grew up this way; PaddleOCR-VL keeps a layout model in front of its 0.9B recogniser, and the [structured-layout-priors paper](https://arxiv.org/abs/2605.19866) shows the value of the detector even for a VLM: injecting RT-DETR boxes (as DocTags) into a 258M model's prompt took markdown F1 on structurally novel documents from 0.37 to 0.92 and the table TEDS on Chinese OmniDocBench from 0.01 to 0.36, for about 15% more latency. The authors' caveats are the right ones: the detector is a dependency, "arbitrarily poor structural proposals can yield misleading priors," and gains may not transfer to scripts absent from training.

**End-to-end.** One VLM reads the page image and emits markdown or HTML with boxes. dots.ocr, OvisOCR2, DeepSeek-OCR, Qianfan-OCR, HPD-Parsing and olmOCR-2 are in this camp, and so is Qwen3-VL with its `qwenvl html` prompt. The [real-world parsing paper](https://arxiv.org/abs/2603.23885) argues cascaded pipelines "often fail under casually captured or non-standard conditions" because they depend on precise layout analysis, while end-to-end models "still produce repetitive, hallucinated, and structurally inconsistent output"; it builds Wild-OmniDocBench from phone-captured pages to measure both. [Qianfan-OCR](https://arxiv.org/abs/2603.13398) drops explicit layout analysis and calls that loss "a practical limitation."

**What the best current models actually do** is a hybrid: a global pass at low resolution for structure, then native-resolution reading of regions. MinerU2.5 describes a decoupled two-stage strategy inside one 1.2B VLM (layout on a downsampled page, recognition on crops), [HPD-Parsing](https://huggingface.co/PaddlePaddle/HPD-Parsing) runs a layout branch that forks concurrent content branches with multi-token prediction (2.68 pages/s batched), and LandingAI's DPT describes the same shape from the outside ([how DPT-3 works](../ade/how-dpt3-works.md)). The [pipeline](../build/pipeline.md) on this wiki is that hybrid with the stages exposed.

## Agentic repair loops

"Agentic" in vendor copy means re-checking and re-doing parts of a page. The measured versions:

- [**Collapse, Not Complexity**](https://arxiv.org/abs/2609.23592) (2026): problem pages for end-to-end parsers are defined by *collapse*, degenerate repetition that uses about 19x the tokens, not by visual complexity (collapsed pages often have lower layout entropy). Enabling the model's reasoning mode makes things worse (mean quality down 2.21 at 1.54x tokens; 83% of collapses recur), and an input-only predictor cannot tell which pages will benefit (AUROC 0.47). The repair that works: detect collapse from the first pass's trace, decompose the page by projection, re-parse the regions. Gains of 1.40 overall at 1.13x tokens, 2.41 on the remaining pages with a frozen 4B model, replicated across three checkpoints. This is the policy the pipeline's `verify.decide()` should implement.
- [**ParseBench**](https://arxiv.org/html/2604.08538v3): a benchmark built for AI agents consuming parser output, with a VLM pass that reviews markdown against the source and proposes patches; used for annotation, but the same loop is a runtime verifier.
- [**AgenticOCR**](https://arxiv.org/html/2602.24134v1): parse only the regions a query needs by analysing layout and zooming; no verification loop, but the zoom-on-demand idea is the figure path of this pipeline.
- **Reducto** (vendor): layout detection, a VLM contextual review that links headers to columns and assigns semantic types, then "agentic OCR" multi-pass correction that re-checks low-confidence regions and emits block-level confidence; "orchestrates 12+ models"; 90.2% on its own RD-TableBench versus Azure 82.7, Textract 80.9, Google 64.6 (vendor-reported). Source: [Reducto deep dive](https://llms.reducto.ai/hybrid-architecture-agentic-ocr-deep-dive).
- **Upstage** (vendor, Korean): `document-parse-260930` replaced its multi-stage pipeline with an end-to-end VLM parser in "enhanced mode" (API only, no weights). Source: [Upstage model history](https://console.upstage.ai/docs/models/history).

## Slides and multi-page understanding

- [**SlideAgent**](https://arxiv.org/abs/2510.26615) (ACL 2026): hierarchical agents at global, page and element level build a query-agnostic representation of a deck, then activate selectively at inference; +7.9% accuracy over proprietary and +9.8% over open models on multi-page visual document QA. Its three levels are the context stage of this pipeline (deck outline, slide argument, block text) made explicit.
- [**SlideVQA**](https://arxiv.org/abs/2301.04883): 2.6k decks, 52k slide images, 14.5k questions needing single-hop, multi-hop and numerical reasoning across slides; the standard slide QA benchmark, English.
- **MMLongBench-Doc**: long multi-page document QA; the one "understand the whole document" number the Qwen cards report (Qwen3.5-27B 60.2).
- [**VISTA-Bench**](https://arxiv.org/abs/2602.04802): do VLMs understand visualised text as well as plain text? (They do not, which is the argument for harvesting the text layer when it exists.)

## Benchmarks and their blind spots

| Benchmark | Covers | Blind spot for this project |
|---|---|---|
| [OmniDocBench](https://github.com/opendatalab/OmniDocBench) v1.5 / v1.6 | 9 page types, zh/en, text/formula/table/order; v1.6 adds a 296-page Hard subset | no Korean, no slides, top scores saturating |
| olmOCR-bench | unit tests over English PDFs | English |
| CC-OCR | multilingual OCR incl. non-Latin | low page quality; not slide layouts |
| [Wild-OmniDocBench](https://arxiv.org/abs/2603.23885) | phone-captured real pages | zh/en |
| [FinixDoc](https://arxiv.org/abs/2608.22842) | hard finance pages where saturated benchmarks stop separating models | finance only |
| [KoViDoRe](https://arxiv.org/abs/2608.20840), [SDS KoPub VDR](https://arxiv.org/abs/2511.04910) | Korean visual document *retrieval* | retrieval, not parsing |
| [upstage/dp-bench](https://huggingface.co/datasets/upstage/dp-bench) | 200-sample document parsing set from a Korean vendor | small; check language mix |

## Takeaways for dense Korean slides

1. Keep a layout stage; feed its boxes to the reader. Measured gains, modest latency.
2. Read crops at native resolution; read whole pages only when they are sparse.
3. Expect collapse, detect it from the output, repair by decomposition. Do not reach for reasoning mode.
4. Treat slide context as a first-class stage (SlideAgent's three levels).
5. Use the text layer whenever it exists; VLMs read visualised text worse than plain text (VISTA-Bench).
6. Build a Korean eval set; nothing public measures this.
