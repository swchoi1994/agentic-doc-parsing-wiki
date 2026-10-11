---
title: What LandingAI built
---

Guide
{ .eyebrow }

# What LandingAI built

Agentic Document Extraction as a product: three APIs, two generations, two DPT-3 models, and the operating envelope around them.
{ .lead }

## Three APIs

| API | Input | Output | Billing |
|---|---|---|---|
| **Parse** | PDF, image, DOCX, PPTX, ODT, RTF (Gen2); spreadsheets and legacy Office in Gen1 | reading-order markdown, a structure tree of pages and blocks, per-block grounding | by output characters (Gen2); Verity about 40% of Pro's credits |
| **Extract** | markdown from any source plus a JSON Schema | values matching the schema, each with character ranges into the markdown | by input and output characters |
| **Ground** | Parse `structure` plus Extract `extraction_metadata` | the blocks, pages and boxes each extracted value was quoted from | free, synchronous |

Gen1 keeps four more: **Classify** (document type per page), **Split** (cut a batch into sub-documents, detecting repeated identifiers such as invoice numbers), **Section**, and **Build Extract Schema**. Gen1 Parse takes `custom_prompts` for figure descriptions and `split=page`.

Sources: [Overview](https://docs.landing.ai/dpt3/overview), [ADE agent skill](https://github.com/landing-ai/ade-document-processing-skills), [Gen1 overview](https://docs.landing.ai/ade/ade-overview).

## Two generations

| | Gen1 (DPT-2) | Gen2 (DPT-3) |
|---|---|---|
| Endpoint | `api.va.landing.ai/v1/ade/parse` | `api.ade.landing.ai/v2/parse` |
| Response | `chunks` list, 0-indexed pages, boxes as `left/top/right/bottom` | `structure` tree, 1-indexed pages, boxes as `xmin/ymin/xmax/ymax`, `range` into `markdown` |
| Tables | pipe markdown | HTML by default (merged cells), markdown optional |
| Confidence | block and cell level (preview, Feb 2026), gone after the September 2026 provider change | per word, Verity only |
| Figure prompts | `custom_prompts.figure` | none; `blocks.figure.markdown` on/off |
| Models | `dpt-2`, dated snapshots | `dpt-3-pro-20260710`, `dpt-3-verity-20260804-preview` |
| Pricing | 3 credits per page | by characters; "25% to 80% lower for mixed workloads" |

Gen1 code does not run on Gen2 without changes; Extract schemas carry over. Source: [migration guide](https://docs.landing.ai/dpt3/migration-guide).

## Two DPT-3 models

**DPT-3 Pro** (default): scans, handwriting, non-Latin scripts, math, detailed figure descriptions, markdown styling, line-level grounding, no confidence. **DPT-3 Verity** (preview, formerly DPT-3 Fast): digitally created Latin-script documents, word-level grounding with per-word confidence, no styling, basic figure markers, lower latency and cost. Automated routing between them is "planned for fall 2026." Details and evidence on [how DPT-3 works](how-dpt3-works.md).

## Languages

Strong support: English, Chinese (Simplified and Traditional), Dutch, French, German, Italian, Japanese, **Korean**, Portuguese, Russian, Spanish. Moderate: Arabic, Czech, Danish, Finnish, Greek, Hebrew, Hindi, Indonesian, Norwegian, Polish, Swedish, Thai, Turkish, Vietnamese. Basic: Amharic, Bengali, Gujarati, Malayalam, Tamil, Telugu, Urdu and other complex scripts. The tiers apply to DPT-2 and DPT-3 Pro; Verity reads Latin scripts only. Source: [supported languages](https://docs.landing.ai/ade/ade-languages).

## Operating envelope

- **Files:** up to 1 GiB for PDFs, 50 MiB for images; page limits per plan; Office files converted to PDF before parsing.
- **Modes:** synchronous (`priority` tier, inline result) or jobs (`standard` tier at half the credits, poll or webhook); results can be written to S3, Azure Blob or GCS presigned URLs for zero-data-retention organisations.
- **Deployment:** US and EU cloud, customer VPC on AWS, Azure or Google Cloud, Snowflake native app, on-premises including air-gapped (enterprise).
- **Compliance claims:** SOC 2 Type II, GDPR, HIPAA.
- **Throughput claims:** "thousands of pages per minute" and "under 2 second processing time" on the marketing site; measured `duration_ms` is returned per request.

Sources: [file types](https://docs.landing.ai/dpt3/file-types), [sync vs async](https://docs.landing.ai/dpt3/sync-async), [Gen2 blog](https://landing.ai/blog/introducing-agentic-document-extraction-gen2), [landing.ai](https://landing.ai/).

## Open-source surface

LandingAI's GitHub organisation holds the client side, never the model: [ade-python](https://github.com/landing-ai/ade-python), [ade-typescript](https://github.com/landing-ai/ade-typescript), [ade-cli](https://github.com/landing-ai/ade-cli), the [ade-document-processing-skills](https://github.com/landing-ai/ade-document-processing-skills) agent skill, [ade-sample-projects](https://github.com/landing-ai/ade-sample-projects), and the [ade-docvqa-benchmark](https://github.com/landing-ai/ade-docvqa-benchmark) that reports 99.156% on DocVQA validation by parsing with DPT-2 and answering with Claude Sonnet 4.5. The legacy `agentic-doc` library and `vision-agent` tools are deprecated.

## Accessing ADE from code

```python
from pathlib import Path
from landingai_ade import LandingAIADE   # pip install landingai-ade

client = LandingAIADE()                   # reads VISION_AGENT_API_KEY
job = client.v2.parse_jobs.create(document=Path("deck.pdf"), model="dpt-3-pro-latest", service_tier="standard")
done = client.v2.parse_jobs.wait(job.job_id, timeout=3600, raise_on_failure=True)
Path("parse-response.json").write_text(done.result.model_dump_json(indent=2))
```

The [evaluation recipe](../build/evaluation.md) wraps this so ADE's output lands in the same folder layout as the local pipeline's.
