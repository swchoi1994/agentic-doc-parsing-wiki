"""Stage 4: understand the slides, not just read them.

A person reading a deck carries context from slide to slide: the section they are in, the
claim the previous slide set up, what the speaker said. A VLM reading one crop has none of
that. This stage builds a deck outline, then writes a one-paragraph "what this slide argues"
for each slide in Korean, using the slide's own parsed markdown, its title, its speaker notes,
and the summaries of the previous and next slides. The result is stored as `context.json`
and prefixed to each slide's chunks at retrieval time (see wiki: Embeddings and retrieval).

The model here is a text LLM (same vLLM server works if the VLM is instruction-tuned).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

OUTLINE_PROMPT = (
    "다음은 슬라이드 덱의 각 슬라이드 제목과 첫 줄입니다. 덱의 전체 주제를 한 문장으로 쓰고, "
    "슬라이드들을 3~7개의 섹션으로 묶어 각 섹션의 제목과 포함 슬라이드 번호를 JSON으로 출력하세요. "
    '형식: {"topic": "...", "sections": [{"title": "...", "slides": [1,2,3]}]}\n\n'
)

SLIDE_PROMPT = (
    "당신은 이 슬라이드 덱을 발표자처럼 이해하는 분석가입니다. 아래 정보를 바탕으로 "
    "이 슬라이드가 주장하는 핵심 메시지와 그 근거를 한국어 3~5문장으로 요약하세요. "
    "숫자와 고유명사는 원문 그대로 인용하고, 슬라이드에 없는 내용은 추측하지 마세요.\n\n"
    "[덱 주제] {topic}\n[섹션] {section}\n[이전 슬라이드 요지] {prev}\n[다음 슬라이드 요지] {next}\n"
    "[발표자 노트] {notes}\n\n[이 슬라이드의 파싱 결과]\n{markdown}\n"
)


@dataclass
class SlideContext:
    page: int
    section: str
    argument: str


class ContextBuilder:
    def __init__(self, chat, dry_run: bool = False):
        self.chat = chat  # callable(prompt: str) -> str
        self.dry_run = dry_run

    def outline(self, slides: list[dict]) -> dict:
        if self.dry_run:
            return {"topic": "[dry-run] 덱 주제", "sections": [{"title": "전체", "slides": [s["page"] for s in slides]}]}
        listing = "\n".join(f'{s["page"]}. {s.get("title") or ""} | {s["markdown"][:80].replace(chr(10), " ")}' for s in slides)
        raw = self.chat(OUTLINE_PROMPT + listing)
        try:
            return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        except Exception:
            return {"topic": raw[:200], "sections": [{"title": "전체", "slides": [s["page"] for s in slides]}]}

    def build(self, slides: list[dict], out_path: Path) -> list[SlideContext]:
        outline = self.outline(slides)
        section_of = {p: sec["title"] for sec in outline.get("sections", []) for p in sec.get("slides", [])}
        firstlines = {s["page"]: (s.get("title") or s["markdown"][:120]) for s in slides}
        result: list[SlideContext] = []
        for s in slides:
            p = s["page"]
            if self.dry_run:
                arg = "[dry-run] 슬라이드 요지"
            else:
                arg = self.chat(SLIDE_PROMPT.format(
                    topic=outline.get("topic", ""), section=section_of.get(p, ""),
                    prev=firstlines.get(p - 1, "(없음)"), next=firstlines.get(p + 1, "(없음)"),
                    notes=s.get("notes") or "(없음)", markdown=s["markdown"][:6000])).strip()
            result.append(SlideContext(p, section_of.get(p, ""), arg))
        out_path.write_text(json.dumps({"outline": outline, "slides": [asdict(r) for r in result]},
                                       ensure_ascii=False, indent=2), encoding="utf-8")
        return result
