"""Stage 5: verify each block and decide what to do about the ones that look wrong.

Checks are cheap and deterministic. The *policy* that turns check results into an action
(accept / re-read at higher resolution / split the block and re-read the parts / flag for
a human) is where the engineering judgement lives, so it is left to you: see `decide()`.
A trivial default keeps the pipeline runnable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .route import Block, PagePlan

HANGUL = re.compile(r"[가-힣]")


@dataclass
class CheckResult:
    block_id: str
    type: str
    length: int
    hangul_ratio: float      # share of Hangul syllables among letters; near 0 on a Korean slide is suspicious
    repetition: float        # share of 3-gram repeats; collapse shows up as > 0.3
    expected_chars: float    # rough expectation from the crop area and text density
    agreement: float | None  # similarity to the text layer when one exists (1.0 = identical)
    table_ok: bool | None    # rows have consistent column counts (tables only)
    flags: list[str] = field(default_factory=list)


def _repetition(text: str) -> float:
    toks = text.split()
    if len(toks) < 6:
        return 0.0
    grams = [" ".join(toks[i:i + 3]) for i in range(len(toks) - 2)]
    return 1 - len(set(grams)) / len(grams)


def _hangul_ratio(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return len(HANGUL.findall(text)) / len(letters)


def _table_ok(html: str) -> bool:
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I)
    if not rows:
        return False
    counts = [len(re.findall(r"<t[dh]\b", r, re.I)) for r in rows]
    return max(counts) - min(counts) <= 1


def _agreement(a: str, b: str) -> float:
    import difflib
    return difflib.SequenceMatcher(None, a, b).ratio()


def check_block(block: Block, block_id: str, plan: PagePlan, text_layer_text: str | None) -> CheckResult:
    md = block.markdown or ""
    area = max(1e-6, (block.box[2] - block.box[0]) * (block.box[3] - block.box[1]))
    expected = 1800 * area * (plan.ink_density / 0.1)  # ~1800 chars for a full dense page at density 0.1
    r = CheckResult(block_id, block.type, len(md), _hangul_ratio(md), _repetition(md), expected,
                    _agreement(md, text_layer_text) if text_layer_text else None,
                    _table_ok(md) if block.type == "table" else None)
    if block.type in ("text", "marginalia"):
        if r.repetition > 0.3:
            r.flags.append("collapse")
        if r.length < 0.3 * r.expected_chars and plan.page_class != "sparse":
            r.flags.append("too-short")
        if r.hangul_ratio < 0.2 and plan.page_class != "digital":
            r.flags.append("no-hangul")
        if r.agreement is not None and r.agreement < 0.85:
            r.flags.append("disagrees-with-text-layer")
    if block.type == "table" and r.table_ok is False:
        r.flags.append("ragged-table")
    if block.type == "figure" and r.length < 40:
        r.flags.append("thin-description")
    return r


Action = str  # "accept" | "reread-hires" | "split-reread" | "flag"


def decide(result: CheckResult, block: Block) -> Action:
    """Turn a CheckResult into an action.

    TODO(you): write the retry policy. This is the heart of the "verify until a quality
    threshold is met" behaviour, and it depends on your documents and your budget:

      - which flags are worth a retry at all? ("thin-description" on a decorative figure is not)
      - when do you re-read the same crop at higher resolution (small glyphs, no collapse) versus
        split the crop and read the parts (collapse / too-short on a big block)?
      - how many retries per block before you stop and flag it for review?
      - should a block that disagrees with the text layer be *replaced* by the text layer?

    Return one of: "accept", "reread-hires", "split-reread", "flag".
    The default below retries nothing, so the pipeline runs end to end but never repairs.
    """
    if result.flags:
        return "flag"
    return "accept"
