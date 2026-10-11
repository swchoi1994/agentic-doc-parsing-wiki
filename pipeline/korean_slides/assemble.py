"""Stage 6: assemble one markdown string and the structure tree with code-point ranges.

Mirrors ADE Gen2: pages separated by `<!-- PAGE BREAK -->`, ids `<type>-<index>` per type in
reading order, `range` = [start, end) code points into `markdown`, boxes rounded to 5 decimals,
and a trailing `<!-- doc_id=... -->` comment.
"""
from __future__ import annotations

import re
import time
import uuid
from collections import Counter

from .ade_schema import Box, Document, Element, Grounding, Page, ParseMetadata, ParseResponse, Range
from .read import wrap_markdown
from .route import PagePlan

_CELL = re.compile(r"<(td|th)([^>]*)>(.*?)</\1>", re.S | re.I)
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)


def _table_cells(table_md: str, start: int, page: int, box: Box, counters: Counter) -> list[Element]:
    """Cells get ids and ranges into the table's HTML. Boxes are the table box (no per-cell detector here)."""
    cells: list[Element] = []
    for r, row in enumerate(_ROW.finditer(table_md)):
        for c, m in enumerate(_CELL.finditer(row.group(0))):
            attrs = m.group(2)
            rs = int(re.search(r'rowspan="?(\d+)', attrs).group(1)) if re.search(r'rowspan="?(\d+)', attrs) else 1
            cs = int(re.search(r'colspan="?(\d+)', attrs).group(1)) if re.search(r'colspan="?(\d+)', attrs) else 1
            s = start + row.start() + m.start(3)
            e = s + len(m.group(3))
            cells.append(Element(type="table_cell", id=f"table_cell-{counters['table_cell']}",
                                 grounding=Grounding(page=page, range=Range(start=s, end=e), box=box),
                                 atomic_grounding=[], row=r, col=c, rowspan=rs, colspan=cs))
            counters["table_cell"] += 1
    return cells


def assemble(plans: list[PagePlan], model_version: str, started: float, failed: dict[int, str] | None = None) -> ParseResponse:
    failed = failed or {}
    counters: Counter = Counter()
    parts: list[str] = []
    pages: list[Page] = []
    cursor = 0  # code points so far
    job_id = f"parse-{uuid.uuid4().hex[:26]}"

    for i, plan in enumerate(plans):
        page_start = cursor
        elements: list[Element] = []
        if plan.page in failed:
            pages.append(Page(grounding=Grounding(page=plan.page, range=Range(start=cursor, end=cursor),
                                                  box=Box(xmin=0, ymin=0, xmax=1, ymax=1)),
                              status="failed", reason=failed[plan.page]))
        else:
            for b in plan.blocks:
                md = wrap_markdown(b).strip()
                if not md:
                    continue
                box = Box(xmin=b.box[0], ymin=b.box[1], xmax=b.box[2], ymax=b.box[3]).rounded()
                s = cursor
                e = s + len(md)
                el = Element(type=b.type, id=f"{b.type}-{counters[b.type]}",
                             grounding=Grounding(page=plan.page, range=Range(start=s, end=e), box=box))
                counters[b.type] += 1
                if b.type == "table":
                    el.children = _table_cells(md, s, plan.page, box, counters)
                else:
                    el.atomic_grounding = [Grounding(page=plan.page, range=Range(start=s, end=e), box=box)]
                elements.append(el)
                parts.append(md)
                cursor = e + 2  # the "\n\n" joiner
            pages.append(Page(grounding=Grounding(page=plan.page, range=Range(start=page_start, end=max(page_start, cursor - 2)),
                                                  box=Box(xmin=0, ymin=0, xmax=1, ymax=1)),
                              children=elements))
        if i < len(plans) - 1:
            parts.append("<!-- PAGE BREAK -->")
            cursor += len("<!-- PAGE BREAK -->") + 2

    parts.append(f"<!-- doc_id={job_id} -->")
    markdown = "\n\n".join(parts)
    meta = ParseMetadata(job_id=job_id, model_version=model_version, page_count=len(plans),
                         output_markdown_chars=len(markdown), failed_pages=sorted(failed),
                         duration_ms=int((time.time() - started) * 1000))
    return ParseResponse(markdown=markdown, metadata=meta, structure=Document(children=pages))
