"""Stage 3: read each block with a VLM through an OpenAI-compatible endpoint (vLLM, SGLang,
TGI, or a hosted Qwen). One prompt per block type, Korean output, crops at native resolution.

Why per block and not per page: the generative reader is the component that collapses on
dense pages (repetition, skipped lines, hallucinated rows). Reading a crop keeps the token
budget per call small, lets you run blocks in parallel, and lets stage 5 retry one block.
"""
from __future__ import annotations

import base64
import io
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .route import Block, PagePlan

LAYOUT_PROMPT = "qwenvl html"  # Qwen3-VL's built-in document-parsing prompt: boxes in 0..1000

PROMPTS = {
    "text": (
        "이 이미지의 모든 텍스트를 보이는 순서대로 Markdown으로 정확히 옮겨 적으세요. "
        "제목은 #, 글머리 기호는 -, 강조는 **굵게**로 표시하고, 없는 내용을 추가하지 마세요. "
        "한글 맞춤법과 띄어쓰기는 원문 그대로 유지합니다. Markdown만 출력하세요."
    ),
    "table": (
        "이 표를 HTML <table>로 변환하세요. 병합된 셀은 rowspan/colspan으로 표현하고, "
        "모든 셀 내용을 빠짐없이 원문 그대로 적으세요. 표 바깥 설명은 쓰지 말고 HTML만 출력하세요."
    ),
    "figure": (
        "이 그림(차트/도식/사진)을 한국어로 설명하세요. 차트라면 축, 범례, 단위, 수치와 추세를 "
        "구체적으로 적고, 도식이라면 구성 요소와 화살표 관계를 적으세요. 3~6문장, Markdown 없이 서술합니다."
    ),
    "marginalia": "이 영역의 텍스트(머리글/바닥글/페이지 번호/각주)를 있는 그대로 한 줄씩 적으세요.",
    "logo": "이 로고에 적힌 글자나 브랜드명이 있으면 적고, 없으면 '로고'라고만 쓰세요.",
    "attestation": "서명/도장/직인이 보이면 'SIGNED' 또는 'STAMPED'와 함께 보이는 글자를 적으세요.",
    "card": "이 카드/신분증에 인쇄된 필드와 값을 '필드: 값' 형식으로 한 줄씩 적으세요.",
    "scan_code": "바코드/QR 코드입니다. 해독 가능한 텍스트가 보이면 적고, 아니면 'QR 코드' 또는 '바코드'라고 쓰세요.",
}

PAD = 0.006  # 0.6% of the page around each crop


@dataclass
class ReaderConfig:
    base_url: str = "http://localhost:8000/v1"
    model: str = "Qwen/Qwen3-VL-8B-Instruct"
    api_key: str = "EMPTY"
    max_tokens: int = 2048
    temperature: float = 0.0
    workers: int = 8
    dry_run: bool = False


class VLMReader:
    def __init__(self, cfg: ReaderConfig):
        self.cfg = cfg
        self.client = None
        if not cfg.dry_run:
            from openai import OpenAI
            self.client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key)

    # --- raw calls -------------------------------------------------------------------
    def ask(self, image: Image.Image, prompt: str, max_pixels: int | None = None) -> str:
        if self.cfg.dry_run:
            return "[dry-run] " + prompt[:24]
        buf = io.BytesIO(); image.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        extra = {"mm_processor_kwargs": {"max_pixels": max_pixels}} if max_pixels else {}
        rsp = self.client.chat.completions.create(
            model=self.cfg.model, temperature=self.cfg.temperature, max_tokens=self.cfg.max_tokens,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": prompt}]}],
            extra_body=extra,
        )
        return rsp.choices[0].message.content or ""

    def layout(self, page_image: Path, max_pixels: int) -> str:
        if self.cfg.dry_run:
            # a plausible dense slide: title, two text columns, one table, one chart
            return ('<h1 data-bbox="60 40 940 110" class="title">t</h1>'
                    '<p data-bbox="60 140 480 620" class="text">t</p>'
                    '<p data-bbox="520 140 940 400" class="text">t</p>'
                    '<table data-bbox="520 420 940 720" class="table"></table>'
                    '<img data-bbox="60 650 480 940" class="image"/>'
                    '<p data-bbox="60 950 940 990" class="footer">t</p>')
        return self.ask(Image.open(page_image), LAYOUT_PROMPT, max_pixels)

    # --- per-block reading ---------------------------------------------------------------
    def read_block(self, page_image: Path, block: Block, max_pixels: int) -> str:
        img = Image.open(page_image)
        W, H = img.size
        x0, y0, x1, y1 = block.box
        crop = img.crop((max(0, int((x0 - PAD) * W)), max(0, int((y0 - PAD) * H)),
                         min(W, int((x1 + PAD) * W)), min(H, int((y1 + PAD) * H))))
        prompt = PROMPTS.get(block.type, PROMPTS["text"])
        return self.ask(crop, prompt, max_pixels).strip()

    def read_plan(self, page_image: Path, plan: PagePlan) -> None:
        todo = [b for b in plan.blocks if b.source != "text-layer"]  # text-layer blocks are already exact
        with ThreadPoolExecutor(max_workers=self.cfg.workers) as ex:
            results = list(ex.map(lambda b: self.read_block(page_image, b, plan.max_pixels), todo))
        for b, md in zip(todo, results):
            b.markdown = md


def wrap_markdown(block: Block) -> str:
    """ADE's markdown conventions per block type."""
    if block.type == "figure":
        return f'<figure type="FIGURE"><description>{block.markdown}</description></figure>'
    if block.type == "attestation":
        return f"[SIGNED] {block.markdown}" if "SIGNED" in block.markdown.upper() else f"[STAMPED] {block.markdown}"
    if block.type == "scan_code":
        return f"[SCAN_CODE] {block.markdown}"
    if block.type == "logo":
        return f"[LOGO] {block.markdown}"
    return block.markdown
