"""Stage 1: render pages and harvest everything the file already knows.

ADE rasterises Office files to PDF and reads pixels. We do the same for the picture,
but we also keep the text layer, the slide titles and the speaker notes, because for
digitally authored decks they are exact and free. Scanned decks have none of this and
fall through to the VLM for everything.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf as fitz

DPI = 200  # ~2200 px wide for a 16:9 slide: enough for 8-10 pt Hangul


@dataclass
class TextSpan:
    text: str
    box: tuple[float, float, float, float]  # normalised xmin, ymin, xmax, ymax
    size: float


@dataclass
class PageAsset:
    number: int  # 1-indexed, as in ADE
    image_path: Path
    width_px: int
    height_px: int
    text_spans: list[TextSpan] = field(default_factory=list)
    title: str | None = None
    notes: str | None = None

    @property
    def has_text_layer(self) -> bool:
        return sum(len(s.text) for s in self.text_spans) > 20


def pptx_to_pdf(pptx: Path, workdir: Path) -> Path:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("LibreOffice (soffice) is required to convert PPTX to PDF")
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(workdir), str(pptx)],
                   check=True, capture_output=True)
    return workdir / (pptx.stem + ".pdf")


def harvest_pptx(pptx: Path) -> dict[int, dict]:
    """Slide titles and speaker notes from the PPTX XML (1-indexed)."""
    from pptx import Presentation

    out: dict[int, dict] = {}
    prs = Presentation(str(pptx))
    for i, slide in enumerate(prs.slides, start=1):
        title = slide.shapes.title.text.strip() if slide.shapes.title is not None and slide.shapes.title.has_text_frame else None
        notes = slide.notes_slide.notes_text_frame.text.strip() if slide.has_notes_slide else None
        out[i] = {"title": title or None, "notes": notes or None}
    return out


def render(source: Path, out_dir: Path, dpi: int = DPI) -> list[PageAsset]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(exist_ok=True)

    extras: dict[int, dict] = {}
    pdf = source
    if source.suffix.lower() == ".pptx":
        extras = harvest_pptx(source)
        pdf = pptx_to_pdf(source, out_dir)

    assets: list[PageAsset] = []
    with fitz.open(pdf) as doc:
        for idx, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            img = pages_dir / f"page-{idx:03d}.png"
            pix.save(img)
            w, h = page.rect.width, page.rect.height
            spans: list[TextSpan] = []
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        t = span["text"].strip()
                        if not t:
                            continue
                        x0, y0, x1, y1 = span["bbox"]
                        spans.append(TextSpan(t, (x0 / w, y0 / h, x1 / w, y1 / h), span["size"]))
            assets.append(PageAsset(idx, img, pix.width, pix.height, spans,
                                    extras.get(idx, {}).get("title"), extras.get(idx, {}).get("notes")))
    return assets
