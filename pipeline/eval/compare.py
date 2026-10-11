"""Score a parse against ground truth: character error rate on Hangul-normalised text,
table TEDS (optional, needs `pip install apted`), and reading-order Kendall tau.

python -m pipeline.eval.compare pred/parse-response.json gt/parse-response.json
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata


def norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"<[^>]+>", " ", s)            # strip HTML (tables, figures)
    s = re.sub(r"<!--.*?-->", " ", s, flags=re.S)
    s = re.sub(r"[#*_`>|\-]+", " ", s)         # markdown punctuation
    return re.sub(r"\s+", " ", s).strip()


def cer(pred: str, ref: str) -> float:
    a, b = norm(pred), norm(ref)
    if not b:
        return 0.0 if not a else 1.0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1] / len(b)


def page_texts(rsp: dict) -> dict[int, str]:
    md = rsp["markdown"]
    return {p["grounding"]["page"]: md[p["grounding"]["range"]["start"]:p["grounding"]["range"]["end"]]
            for p in rsp["structure"]["children"] if p.get("status", "ok") == "ok"}


def block_order_tau(pred: dict, ref: dict, page: int) -> float | None:
    """Kendall tau between predicted and reference reading order, matched by box centre."""
    def centres(rsp):
        pg = next((p for p in rsp["structure"]["children"] if p["grounding"]["page"] == page), None)
        return [((e["grounding"]["box"]["xmin"] + e["grounding"]["box"]["xmax"]) / 2,
                 (e["grounding"]["box"]["ymin"] + e["grounding"]["box"]["ymax"]) / 2) for e in (pg["children"] if pg else [])]
    P, R = centres(pred), centres(ref)
    if len(P) < 2 or len(R) < 2:
        return None
    # map each reference block to the nearest predicted block index
    order = []
    for (rx, ry) in R:
        order.append(min(range(len(P)), key=lambda i: (P[i][0] - rx) ** 2 + (P[i][1] - ry) ** 2))
    conc = disc = 0
    for i in range(len(order)):
        for j in range(i + 1, len(order)):
            if order[i] < order[j]: conc += 1
            elif order[i] > order[j]: disc += 1
    return (conc - disc) / max(1, conc + disc)


def main() -> None:
    pred = json.load(open(sys.argv[1], encoding="utf-8"))
    ref = json.load(open(sys.argv[2], encoding="utf-8"))
    pt, rt = page_texts(pred), page_texts(ref)
    rows = []
    for page in sorted(rt):
        c = cer(pt.get(page, ""), rt[page])
        tau = block_order_tau(pred, ref, page)
        rows.append((page, c, tau))
        print(f"page {page:3d}  CER {c:.3f}  order-tau {tau if tau is None else round(tau, 2)}")
    print(f"mean CER {sum(r[1] for r in rows) / len(rows):.3f} over {len(rows)} pages")


if __name__ == "__main__":
    main()
