"""Stage 2: the decision layer. Classify the page, choose the reader, set the resolution,
and detect layout blocks.

This is the "CNN sees with kernels" part of the pipeline, in two forms:
- cheap classical CV on the rendered page (ink density, projection profiles) to decide how
  hard the page is and whether to decompose it before reading;
- a layout detector. The default below asks the VLM itself for layout in Qwen's
  `qwenvl html` format (element boxes in 0..1000 coordinates). Swap in DocLayout-YOLO /
  PP-DocLayout for a 30 ms detector when you have thousands of pages.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

from .ade_schema import ElementType
from .render import PageAsset

# Qwen3-VL: 16 px patches merged 2x2 -> one visual token per 32x32 px block.
TOKEN_PX = 32
MIN_PIXELS = 512 * TOKEN_PX * TOKEN_PX
MAX_PIXELS_DEFAULT = 2048 * TOKEN_PX * TOKEN_PX   # ~2.1 MP, ~2048 visual tokens
MAX_PIXELS_DENSE = 4608 * TOKEN_PX * TOKEN_PX     # ~4.7 MP, the cookbook's markdown setting


@dataclass
class Block:
    type: ElementType
    box: tuple[float, float, float, float]  # normalised
    source: str = "layout"                   # layout | text-layer | split
    markdown: str = ""
    children: list["Block"] = field(default_factory=list)
    retries: int = 0


@dataclass
class PagePlan:
    page: int
    page_class: str          # digital | scan | dense | sparse
    reader: str              # text-layer | vlm | ocr
    max_pixels: int
    ink_density: float
    blocks: list[Block] = field(default_factory=list)


def ink_density(image_path: Path) -> float:
    """Fraction of dark pixels; dense Korean slides land around 0.08-0.2."""
    g = np.asarray(Image.open(image_path).convert("L"), dtype=np.uint8)
    return float((g < 128).mean())


def projection_split(image_path: Path, box: tuple[float, float, float, float], max_parts: int = 4) -> list[tuple[float, float, float, float]]:
    """Cut a region at horizontal whitespace valleys (the decomposition used for collapse repair)."""
    img = Image.open(image_path).convert("L")
    W, H = img.size
    x0, y0, x1, y1 = (int(box[0] * W), int(box[1] * H), int(box[2] * W), int(box[3] * H))
    crop = np.asarray(img.crop((x0, y0, x1, y1)), dtype=np.uint8)
    if crop.size == 0:
        return [box]
    rows = (crop < 128).mean(axis=1)
    valleys = [i for i in range(1, len(rows) - 1) if rows[i] < 0.002 and rows[i - 1] >= 0.002]
    if not valleys:
        return [box]
    step = max(1, len(valleys) // max_parts)
    cuts = [0] + valleys[::step][: max_parts - 1] + [len(rows)]
    parts = []
    for a, b in zip(cuts, cuts[1:]):
        if b - a < 8:
            continue
        parts.append((box[0], (y0 + a) / H, box[2], (y0 + b) / H))
    return parts or [box]


def classify(asset: PageAsset) -> tuple[str, str, int]:
    density = ink_density(asset.image_path)
    if asset.has_text_layer:
        page_class = "digital"
        reader = "text-layer"          # exact text for free; VLM only for tables/figures
    else:
        page_class = "scan"
        reader = "vlm"
    if density > 0.12:
        page_class = "dense"
    max_pixels = MAX_PIXELS_DENSE if page_class == "dense" else MAX_PIXELS_DEFAULT
    return page_class, reader, max_pixels


QWEN_TO_ADE: dict[str, ElementType] = {
    "table": "table", "image": "figure", "figure": "figure", "chart": "figure",
    "logo": "logo", "header": "marginalia", "footer": "marginalia", "page-number": "marginalia",
    "footnote": "marginalia", "caption": "text", "title": "text", "section-header": "text",
    "list-item": "text", "text": "text", "formula": "text", "code": "text", "signature": "attestation",
}

_BBOX_RE = re.compile(r'<(\w+)[^>]*data-bbox="(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"[^>]*class="([^"]*)"', re.S)
_BBOX_RE2 = re.compile(r'<(\w+)[^>]*class="([^"]*)"[^>]*data-bbox="(\d+)\s+(\d+)\s+(\d+)\s+(\d+)"', re.S)


def parse_qwenvl_html(html: str) -> list[Block]:
    """Turn Qwen's `qwenvl html` output (data-bbox in 0..1000) into ADE-typed blocks."""
    blocks: list[Block] = []
    for m in _BBOX_RE.finditer(html):
        tag, x0, y0, x1, y1, cls = m.groups()
        blocks.append(_mk(tag, cls, x0, y0, x1, y1))
    if not blocks:
        for m in _BBOX_RE2.finditer(html):
            tag, cls, x0, y0, x1, y1 = m.groups()
            blocks.append(_mk(tag, cls, x0, y0, x1, y1))
    return blocks


def _mk(tag: str, cls: str, x0: str, y0: str, x1: str, y1: str) -> Block:
    label = (cls.split() or [tag])[0].lower()
    if tag.lower() == "table":
        label = "table"
    elif tag.lower() == "img":
        label = "image"
    t: ElementType = QWEN_TO_ADE.get(label, "text")
    box = (int(x0) / 1000, int(y0) / 1000, int(x1) / 1000, int(y1) / 1000)
    return Block(type=t, box=box)


def blocks_from_text_layer(asset: PageAsset) -> list[Block]:
    """Group text-layer spans into line blocks by vertical proximity. Cheap and exact for digital decks."""
    spans = sorted(asset.text_spans, key=lambda s: (round(s.box[1], 2), s.box[0]))
    blocks: list[Block] = []
    cur: list = []
    for s in spans:
        if cur and (s.box[1] - cur[-1].box[3]) > 0.012:  # new paragraph when the gap exceeds ~1 line
            blocks.append(_merge(cur)); cur = []
        cur.append(s)
    if cur:
        blocks.append(_merge(cur))
    return blocks


def _merge(spans: list) -> Block:
    x0 = min(s.box[0] for s in spans); y0 = min(s.box[1] for s in spans)
    x1 = max(s.box[2] for s in spans); y1 = max(s.box[3] for s in spans)
    text = " ".join(s.text for s in spans)
    return Block(type="text", box=(x0, y0, x1, y1), source="text-layer", markdown=text)


def plan_page(asset: PageAsset, layout_html: str | None) -> PagePlan:
    page_class, reader, max_pixels = classify(asset)
    plan = PagePlan(asset.number, page_class, reader, max_pixels, ink_density(asset.image_path))
    layout_blocks = parse_qwenvl_html(layout_html) if layout_html else []
    if reader == "text-layer":
        # exact text from the file; keep only non-text regions (tables, figures) from the detector
        plan.blocks = blocks_from_text_layer(asset) + [b for b in layout_blocks if b.type != "text"]
        plan.blocks.sort(key=lambda b: (round(b.box[1], 2), b.box[0]))
    else:
        plan.blocks = layout_blocks
    return plan
