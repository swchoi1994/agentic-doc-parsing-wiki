"""Parse the same files with LandingAI ADE (DPT-3 Pro) to get the quality bar on your own decks.

pip install landingai-ade ; export VISION_AGENT_API_KEY=...
python -m pipeline.eval.run_ade decks/*.pdf --out out/ade
Each file produces out/ade/<name>/parse-response.json in the same shape the local pipeline emits,
so pipeline/eval/compare.py can score either against the same ground truth.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model", default="dpt-3-pro-latest")
    args = ap.parse_args()
    from landingai_ade import LandingAIADE  # noqa: WPS433

    client = LandingAIADE()
    for f in args.files:
        dest = args.out / f.stem
        dest.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        job = client.v2.parse_jobs.create(document=f, model=args.model, service_tier="standard")
        done = client.v2.parse_jobs.wait(job.job_id, timeout=3600, raise_on_failure=True)
        (dest / "parse-response.json").write_text(done.result.model_dump_json(indent=2), encoding="utf-8")
        (dest / "parse-output.md").write_text(done.result.markdown, encoding="utf-8")
        meta = done.result.metadata
        json.dump({"file": str(f), "wall_s": round(time.time() - t0, 1), "duration_ms": meta.duration_ms,
                   "pages": meta.page_count, "credits": getattr(meta.billing, "total_credits", None),
                   "model_version": meta.model_version}, open(dest / "timing.json", "w"), indent=2)
        print(f"{f.name}: {meta.page_count} pages, ADE duration {meta.duration_ms} ms, wall {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
