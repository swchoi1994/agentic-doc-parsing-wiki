---
title: Hardware and serving
---

Build
{ .eyebrow }

# Hardware and serving

Memory budgets, serving stacks and routing for A100 40/80 GB in two or four cards, TPU, and Apple M1 Max, against a five-second-per-slide target.
{ .lead }

## What fits where

Weights at BF16 are about 2 bytes per parameter; INT4 (AWQ/GPTQ) about 0.55. Leave 30 to 40% of each card for the KV cache and vision activations and set `--gpu-memory-utilization 0.9`. A100 has **no FP8 tensor cores**, so the FP8 checkpoints Qwen publishes do not help here; use BF16 or INT4.

| Model | BF16 weights | INT4 weights | 2x A100 40 | 4x A100 40 | 2x A100 80 | 4x A100 80 |
|---|---|---|---|---|---|---|
| PaddleOCR-VL-1.6 / OvisOCR2 / HPD-Parsing (0.8 to 1.2B) | 2 to 3 GB | n/a | one replica per card | one per card | one per card, with room for a Qwen beside it | same |
| Qwen3-VL-4B | 9 GB | 3 GB | one per card | one per card | two per card | two per card |
| Qwen3-VL-8B | 17 GB | 5 GB | one per card | one per card | one per card, large batch | same |
| Qwen3.5-27B / Qwen3.8-27B | 54 GB | 16 GB | TP2, tight (little KV) or INT4 on one card | TP2 on two cards, parsers on the other two | one card at BF16 | one card each, or TP2 for latency |
| Qwen3-VL-32B | 66 GB | 19 GB | INT4 only | TP4 at BF16 | one card at BF16 | TP2 |
| Qwen3-VL-30B-A3B (MoE) | 61 GB | 18 GB | INT4 | TP4 | one card | TP2 |
| Qwen3-VL-235B-A22B (MoE) | 470 GB | ~130 GB | no | no | INT4 TP2, marginal | INT4 TP4 |

Recommended layouts for the five-second target:

- **2x A100 40 GB:** card 0 serves a 1B parser (layout, text, tables), card 1 serves Qwen3-VL-8B (figures, context). Per-slide critical path is one parser call and one or two Qwen calls in parallel.
- **4x A100 40 GB:** two parser replicas, two Qwen3-VL-8B replicas, or one Qwen3.5-27B over TP2 if chart descriptions matter more than throughput.
- **2x A100 80 GB:** card 0 parser plus Qwen3-VL-8B, card 1 Qwen3-VL-32B or Qwen3.8-27B for the context pass and hard figures.
- **4x A100 80 GB:** the same plus two more parser/8B replicas for throughput, or Qwen3-VL-235B-A22B INT4 over TP4 as an offline "judge" for the evaluation set (not in the five-second path).

## Serving stacks

### vLLM on A100 (the default)

```bash
# general VLM, one card
vllm serve Qwen/Qwen3-VL-8B-Instruct --dtype bfloat16 --max-model-len 16384 \
  --limit-mm-per-prompt '{"image":4}' --max-num-seqs 64 --gpu-memory-utilization 0.9 --port 8000

# 27B/32B over two 40 GB cards
vllm serve Qwen/Qwen3-VL-32B-Instruct --tensor-parallel-size 2 --dtype bfloat16 --max-model-len 16384 --port 8001

# INT4 when it has to fit on one 40 GB card (community AWQ checkpoints exist; verify the quant kernel on Ampere)
vllm serve <org>/Qwen3-VL-32B-Instruct-AWQ --quantization awq_marlin --max-model-len 16384 --port 8001
```

Two settings matter for per-slide latency: `--max-num-seqs` high enough that one slide's 6 to 12 block requests batch together, and `mm_processor_kwargs.max_pixels` per request (set from the decision layer) so that dense pages get more visual tokens and sparse pages fewer.

!!! warning "Qwen3.5 and Qwen3.8 on A100"
    Both use a hybrid Gated DeltaNet / Gated Attention architecture. At release the cards asked for transformers from the main branch and a nightly vLLM; the linear-attention kernels come from the flash-linear-attention (Triton) project. Ampere is supported by those kernels, but confirm the exact vLLM version and kernel path on your cards before committing the 27B class to the production path. Qwen3-VL (standard attention) is the safe choice on A100 today.

### Parsers

PaddleOCR-VL-1.6 serves through PaddleOCR's `genai_server` (a vLLM recipe is in the model card) or transformers 5.x; dots.ocr has official vLLM integration since 0.11; HPD-Parsing ships a customised vLLM build and a Docker image that serves on port 8118 and reports 2.68 pages per second batched on one A800. OvisOCR2 has transformers support and community MLX conversions. All of them speak an OpenAI-compatible chat API when served by vLLM, which is the only interface the pipeline's reader needs.

### Routing with vLLM Semantic Router

[vllm-project/semantic-router](https://github.com/vllm-project/semantic-router) is "an open, programmable decision layer for models and compute": one endpoint (`vllm-sr/auto`) in front of several backends, with policy-driven selection per request, a semantic cache, and guardrails. It fits this pipeline as the serving-side half of the decision layer:

- The pipeline's stage 2 already knows the page class (digital / scan / dense). Encode it in the request (a category tag in the system prompt or a header) and let the router's decision policy map `digital` to the 8B replica, `dense-scan` to the 27B/32B backend, and `figure` prompts to whichever model you trust on charts. One client URL, no routing code in the pipeline.
- The semantic cache deduplicates repeated slides: template slides, agendas and section dividers recur across decks and return instantly.
- Its classifiers are text-based (the "signal" side reads the prompt). For image-heavy requests the signal has to come from your tag, not from the router inspecting pixels; verify multimodal passthrough in its current docs before relying on it.

A sketch of the decision policy, in the router's spirit (check the current config schema in its docs):

```yaml
decisions:
  - name: dense-scan-parse
    signals: [{type: keyword, match: "page_class=dense"}]
    model: qwen3-vl-32b
  - name: digital-parse
    signals: [{type: keyword, match: "page_class=digital"}]
    model: qwen3-vl-8b
  - name: figure-description
    signals: [{type: keyword, match: "task=figure"}]
    model: qwen3-vl-32b
default_model: qwen3-vl-8b
```

### TPU

The vLLM TPU backend (`tpu-inference`) recommends v5e, v6e and v7x. Its tested-model table lists Qwen2.5-VL-7B-Instruct as passing unit and correctness tests (not performance), and Gemma 4 multimodal models as fully tested. **Qwen3-VL is not confirmed on TPU** in the material reviewed for this wiki. Treat a TPU deployment as a hypothesis to verify with the backend's support matrix first; if Qwen3-VL is not there, Qwen2.5-VL-7B (same `qwenvl html` prompt family, Korean OCR confirmed) is the fallback, and Gemma 4 is the tested alternative for figure descriptions.

### Apple M1 Max (64 GB)

For development and evaluation, not for the five-second production path:

```bash
pip install -U mlx-vlm
python -m mlx_vlm.generate --model mlx-community/Qwen3-VL-8B-Instruct-4bit \
  --image slide-012.png --prompt "qwenvl html" --max-tokens 2048
```

Qwen3-VL-8B at 4-bit is about 5 GB and 32B about 18 GB, both comfortable in 64 GB of unified memory; generation speed is bound by memory bandwidth and has not been measured on M1 Max for these models in any source reviewed here (an OvisOCR2 MLX 4-bit card reports roughly 140 to 155 tokens per second on an unnamed Apple Silicon machine). Use the Mac to iterate on prompts, the verifier policy and the eval set; run the budget measurements on the A100s.

## Measuring instead of estimating

The timing harness in the [evaluation recipe](evaluation.md) writes per-stage, per-slide seconds to `timings.json`. Run it on 50 slides per deck type before choosing a layout; the table at the top of this page is a planning estimate, not a measurement.
