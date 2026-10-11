---
title: Embeddings and retrieval
---

Build
{ .eyebrow }

# Embeddings and retrieval

Which embedding models to use over the parsed Korean decks, and a two-track retrieval design that uses the slide context the pipeline produces.
{ .lead }

!!! note "ADE has no embedding product"
    "As good as LandingAI" does not apply to this page: ADE parses, extracts and grounds, and LandingAI's own guidance is to embed the chunks with whatever you like. The bar here is **Korean retrieval quality**, and there are now public Korean benchmarks to measure it: KoViDoRe and SDS KoPub VDR for page images, and the Korean subsets of MTEB for text.

## Two kinds of retrieval, two kinds of model

Slides carry meaning in text *and* in pictures. Two retrievers cover that:

| Track | Index unit | Model class | Why it is needed |
|---|---|---|---|
| Text | one chunk per block (or per slide) from the ADE-shaped markdown, prefixed with the slide's context paragraph | multilingual text embedding | exact numbers, names, and the context stage's "what this slide argues" paragraph |
| Visual document | one rendered slide image | visual-document embedding (ColPali family, single- or multi-vector) | charts, diagrams, layout cues that the parser described imperfectly or not at all |

Fuse them (reciprocal rank fusion is enough), then rerank the top 20 to 50 with a multimodal reranker.

## Text embeddings

| Model | Size | Dims | Context | Languages | License | Notes |
|---|---|---|---|---|---|---|
| [Qwen3-Embedding-8B](https://huggingface.co/Qwen/Qwen3-Embedding-8B) | 8B | up to 4096 (MRL) | 32k | 119 | Apache-2.0 | #1 on MTEB multilingual at release (70.58); instruction-aware; the 0.6B and 4B siblings for cheaper indexing |
| [BGE-M3](https://huggingface.co/BAAI/bge-m3) | 568M | 1024 | 8192 | 100+ | MIT | dense + sparse + multi-vector in one model; the safe default for Korean when GPU budget is small |
| [KURE-v1](https://huggingface.co/nlpai-lab/KURE-v1) | 568M | 1024 | 8192 | Korean | MIT | BGE-M3 fine-tuned on Korean retrieval by Korea University's NLP&AI lab; Korean-only, so not for mixed-language corpora |
| [multilingual-e5-large-instruct](https://huggingface.co/intfloat/multilingual-e5-large-instruct) | 560M | 1024 | 512 | 100 | MIT | solid baseline; the 512-token window is short for slide chunks with context prefixes |

Korean numbers are thin in public: a Korean embedding guide reports KURE-v1 at 0.76 and KURE-v2 at 0.82 average nDCG@10 on Korean retrieval sets, and the KoVRE paper's authors describe Qwen3-Embedding as "particularly robust on non-English languages such as Korean" without a number. Run the three on your own queries; the evaluation harness on the [evaluation page](evaluation.md) includes a retrieval split for exactly this.

## Visual document embeddings

The only Korean-specific numbers available anywhere on this wiki are here, from the KoVRE paper and model card (nDCG@10):

| Model | Params | KoViDoRe avg (4 domains) | SDS KoPub VDR | Overall |
|---|---|---|---|---|
| jina-clip-v2 | 0.9B | 0.085 | 0.073 | 0.083 |
| jina-v5-omni-small | 2B | 0.213 | 0.190 | 0.208 |
| Qwen3-VL-Embedding-2B | 2B | 0.342 | 0.429 | 0.359 |
| jina-embeddings-v4 (single-vector) | 4B | 0.493 | 0.722 | 0.539 |
| Qwen3-VL-Embedding-8B | 8B | 0.504 | 0.729 | 0.549 |
| jina-embeddings-v4 (multi-vector) | 4B | 0.541 | **0.780** | 0.589 |
| **KoVRE** (Stage 1 + 2) | 2B | **0.557** | 0.732 | **0.592** |

Source: [whybe-choi/kovre model card](https://huggingface.co/whybe-choi/kovre) and [arXiv 2608.01389](https://arxiv.org/abs/2608.01389). KoVRE is Qwen3-VL-Embedding-2B fine-tuned on 708,729 Korean and English query-page pairs with hard-negative mining, then distilled from Qwen3-VL-Reranker-8B on Korean data. At 256 dimensions it still scores 0.550 overall, above the 8B Qwen embedding at 4,096 dimensions. Apache-2.0.

Two readings of that table matter for a Korean deck corpus:

- **A 2B model fine-tuned on Korean beats an 8B general model by a wide margin.** Language-specific training data is worth more than parameters here.
- **The absolute numbers are low.** 0.59 nDCG@10 means a lot of Korean visual queries still miss. This is why the text track with the context paragraph is not optional, and why a reranker is worth its latency.

Other visual retrievers to know: [Qwen3-VL-Embedding-2B/8B](https://github.com/QwenLM/Qwen3-VL-Embedding) (33 languages including Korean, 2048/4096 dims, MRL, Apache-2.0, vLLM 0.14+), [ColQwen2.5](https://huggingface.co/vidore/colqwen2.5-v0.2) (multi-vector, ViDoRe-leading in its class), and jina-embeddings-v4 (strong multi-vector, but check its license terms before commercial use).

## Rerankers

| Model | Inputs | Use |
|---|---|---|
| [Qwen3-VL-Reranker-8B](https://huggingface.co/Qwen/Qwen3-VL-Reranker-8B) (or 2B) | query + page image or text | rerank the fused top-k; the 8B is what KoVRE was distilled from, and the card reports 66.7 on ViDoRe v3 vs 52.9 for the 2B embedder alone |
| [Qwen3-Reranker-4B](https://huggingface.co/Qwen/Qwen3-Reranker-4B) | query + text | text-only rerank when images are not needed |
| [bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) | query + text | cheap multilingual text rerank |

## Chunking the ADE-shaped output

The structure tree makes chunking mechanical:

```python
import json

rsp = json.load(open("out/deck/parse-response.json"))
ctx = {s["page"]: s for s in json.load(open("out/deck/context.json"))["slides"]}
md = rsp["markdown"]

chunks = []
for page in rsp["structure"]["children"]:
    if page["status"] != "ok":
        continue
    p = page["grounding"]["page"]
    prefix = f"[섹션] {ctx[p]['section']}\n[슬라이드 요지] {ctx[p]['argument']}\n\n"
    for el in page["children"]:
        r = el["grounding"]["range"]
        body = md[r["start"]:r["end"]]
        if el["type"] in ("marginalia", "logo", "scan_code") or len(body) < 15:
            continue
        chunks.append({"id": el["id"], "page": p, "type": el["type"], "box": el["grounding"]["box"],
                       "text": prefix + body})
```

Each chunk keeps its page and box, so a retrieved chunk can be highlighted on the slide image exactly as ADE's Ground API would.

## Encoding

```python
from sentence_transformers import SentenceTransformer

# text track
txt = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B")       # or BAAI/bge-m3, nlpai-lab/KURE-v1
doc_vecs = txt.encode([c["text"] for c in chunks], normalize_embeddings=True, batch_size=32)
q_vec = txt.encode(["2024년 정보보호 예산은 얼마인가요?"], prompt_name="query", normalize_embeddings=True)

# visual track (pages as images)
vdr = SentenceTransformer("whybe-choi/kovre", truncate_dim=512)
page_vecs = vdr.encode([f"out/deck/pages/page-{p:03d}.png" for p in range(1, 41)], normalize_embeddings=True)
q_img = vdr.encode(["2024년 정보보호 예산은 얼마인가요?"],
                   prompt="Find a document image that matches the given query.", normalize_embeddings=True)
```

KoVRE's card specifies the query instruction above and the default "Represent the user's input." for pages; training used at most 1,280 visual tokens per page, so render pages for indexing at about 1.3 MP.

## Fusion and rerank

```python
def rrf(rankings, k=60):
    scores = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
    return sorted(scores, key=scores.get, reverse=True)

text_hits  = [chunks[i]["page"] for i in (doc_vecs @ q_vec.T)[:, 0].argsort()[::-1][:30]]
image_hits = [p + 1 for p in (page_vecs @ q_img.T)[:, 0].argsort()[::-1][:30]]
candidates = rrf([text_hits, image_hits])[:20]
# then score (query, page image) pairs with Qwen3-VL-Reranker and take the top 5
```

## Sizing

Indexing a 10,000-slide corpus: KoVRE at 2B and the 0.6B text embedder both fit on one A100 40 GB with room to spare; the 8B reranker needs a 40 GB card of its own at BF16 or shares an 80 GB card with the parser. Latency per query with rerank of 20 candidates is typically well under a second on one A100; measure it with the harness.
