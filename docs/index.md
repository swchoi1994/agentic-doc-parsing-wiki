---
title: Home
hide:
  - toc
---

<div class="hero" markdown>

Guide
{ .eyebrow }

# Parse dense Korean slides the way ADE does, on open weights

What LandingAI's Agentic Document Extraction (DPT-3) is known to do, what the public evidence implies about how it does it, and a reproducible pipeline that reaches for the same output shape with Qwen-family and other open vision-language models from Hugging Face.
{ .lead }

<div class="hero-actions" markdown>
[How DPT-3 works](ade/how-dpt3-works.md){ .md-button .md-button--primary }
[Korean slides pipeline](build/pipeline.md){ .md-button }
[Model candidates](build/models.md){ .md-button }
</div>

</div>

## What this wiki is for

People read a slide deck and understand it: the title frames the page, the bullets argue a point, the chart proves it, and the footnote qualifies it. A language model given the same slide as pixels sees a wall of small Korean text, a table without gridlines, and a chart whose legend is three words long. This wiki is the working notebook for closing that gap without a vendor API.

<div class="grid cards" markdown>

-   **Understand the target**

    ---

    LandingAI's Parse, Extract and Ground APIs, the DPT-3 Pro and Verity models, and the exact JSON shape they return. [What LandingAI built](ade/overview.md)

-   **Reconstruct the pipeline**

    ---

    An evidence-graded reconstruction of DPT-3: documented, strongly implied, unknown. Every claim cites its source. [How DPT-3 works](ade/how-dpt3-works.md)

-   **Build the equivalent**

    ---

    Render, layout, per-block reading, slide context, verification, and ADE-shaped output, with reference Python code. [Korean slides pipeline](build/pipeline.md)

-   **Pick the models**

    ---

    Qwen3-VL, Qwen3.5, Qwen3.8 and the specialised 1B parsers that beat them on OmniDocBench, with code and published results. [Model candidates](build/models.md)

-   **Retrieve over the result**

    ---

    Text and page-image embeddings that actually work on Korean, with the KoVRE benchmark numbers. [Embeddings and retrieval](build/embeddings.md)

-   **Size the hardware**

    ---

    A100 40/80 GB in 2 or 4 cards, TPU, and M1 Max, with memory budgets and serving stacks. [Hardware and serving](build/hardware.md)

</div>

## How to read the evidence

This wiki does not have access to LandingAI's models or code. Three chips mark the strength of every claim about their system:

<span class="ev ev-doc">Documented</span> stated in LandingAI's docs, OpenAPI spec, changelog or blog, with a link.
<span class="ev ev-imp">Implied</span> a reasonable inference from documented behaviour; the reasoning is shown.
<span class="ev ev-unk">Unknown</span> not publicly knowable; stated so you do not mistake a guess for a fact.

Model quality numbers for Korean are a second caveat: no public benchmark measures Korean slide parsing, so every model page ends with how to measure it yourself. See the [evaluation recipe](build/evaluation.md).
