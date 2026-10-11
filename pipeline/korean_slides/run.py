"""CLI: deck.pptx|deck.pdf -> ADE-shaped parse-response.json (+ markdown, context, verify log)."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from .assemble import assemble
from .context import ContextBuilder
from .read import ReaderConfig, VLMReader
from .render import render
from .route import PagePlan, plan_page, projection_split, MAX_PIXELS_DENSE, Block
from .verify import check_block, decide


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--vlm-base-url", default="http://localhost:8000/v1")
    ap.add_argument("--vlm-model", default="Qwen/Qwen3-VL-8B-Instruct")
    ap.add_argument("--dpi", type=int, default=200)
    ap.add_argument("--max-retries", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true", help="stub reader; exercises the whole path without a GPU")
    args = ap.parse_args()

    started = time.time()
    args.out.mkdir(parents=True, exist_ok=True)
    assets = render(args.source, args.out, args.dpi)
    reader = VLMReader(ReaderConfig(base_url=args.vlm_base_url, model=args.vlm_model, dry_run=args.dry_run))

    plans: list[PagePlan] = []
    failed: dict[int, str] = {}
    timings: list[dict] = []
    verify_log = (args.out / "verify.jsonl").open("w", encoding="utf-8")
    for a in assets:
        t0 = time.time()
        try:
            html = reader.layout(a.image_path, MAX_PIXELS_DENSE)
            t_layout = time.time()
            plan = plan_page(a, html)
            reader.read_plan(a.image_path, plan)
            t_read = time.time()
            text_layer = " ".join(s.text for s in a.text_spans) if a.has_text_layer else None
            # stage 5: verify, then act on the policy you wrote in verify.decide()
            for idx, b in enumerate(list(plan.blocks)):
                for attempt in range(args.max_retries + 1):
                    res = check_block(b, f"p{a.number}-b{idx}", plan, text_layer if b.source != "text-layer" else None)
                    action = decide(res, b) if res.flags else "accept"
                    verify_log.write(json.dumps({"page": a.number, "block": idx, "attempt": attempt,
                                                 "flags": res.flags, "action": action}, ensure_ascii=False) + "\n")
                    if action == "accept" or attempt == args.max_retries:
                        break
                    if action == "reread-hires":
                        b.retries += 1
                        b.markdown = reader.read_block(a.image_path, b, MAX_PIXELS_DENSE * 2)
                    elif action == "split-reread":
                        parts = projection_split(a.image_path, b.box)
                        if len(parts) > 1:
                            subs = [Block(type=b.type, box=p, source="split") for p in parts]
                            for sb in subs:
                                sb.markdown = reader.read_block(a.image_path, sb, MAX_PIXELS_DENSE)
                            b.markdown = "\n\n".join(sb.markdown for sb in subs)
                            b.source = "split"
                        else:
                            b.markdown = reader.read_block(a.image_path, b, MAX_PIXELS_DENSE * 2)
                    else:  # "flag": keep the text, leave the flag in the log for review
                        break
            plans.append(plan)
            timings.append({"page": a.number, "class": plan.page_class, "blocks": len(plan.blocks),
                            "layout_s": round(t_layout - t0, 3), "read_s": round(t_read - t_layout, 3),
                            "verify_s": round(time.time() - t_read, 3), "total_s": round(time.time() - t0, 3)})
        except Exception as exc:  # a page that fails stays in the tree with status=failed, like ADE
            failed[a.number] = f"{type(exc).__name__}: {exc}"
            plans.append(PagePlan(a.number, "failed", "none", 0, 0.0))
    verify_log.close()
    json.dump(timings, (args.out / "timings.json").open("w"), indent=2)

    rsp = assemble(plans, f"{args.vlm_model}@korean-slides-0.1", started, failed)
    (args.out / "parse-response.json").write_text(rsp.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
    (args.out / "parse-output.md").write_text(rsp.markdown, encoding="utf-8")

    # stage 4: slide context from the assembled markdown
    slides = []
    for page in rsp.structure.children:
        if page.status != "ok":
            continue
        md = rsp.markdown[page.grounding.range.start: page.grounding.range.end]
        a = assets[page.grounding.page - 1]
        slides.append({"page": page.grounding.page, "markdown": md, "title": a.title, "notes": a.notes})
    chat = (lambda p: "[dry-run]") if args.dry_run else (lambda p: reader.client.chat.completions.create(
        model=args.vlm_model, temperature=0.2, max_tokens=800,
        messages=[{"role": "user", "content": p}]).choices[0].message.content or "")
    ContextBuilder(chat, dry_run=args.dry_run).build(slides, args.out / "context.json")

    print(f"pages={rsp.metadata.page_count} failed={rsp.metadata.failed_pages} "
          f"chars={rsp.metadata.output_markdown_chars} ms={rsp.metadata.duration_ms} -> {args.out}")


if __name__ == "__main__":
    main()
