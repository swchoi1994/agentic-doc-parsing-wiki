"""Pydantic models of the ADE Gen2 Parse response.

Field names and semantics follow https://docs.landing.ai/dpt3/parse-response and the
published OpenAPI spec (https://docs.landing.ai/dpt3/openapi-adev2.json):
- one `markdown` string in reading order;
- a `structure` tree: document -> pages -> elements (tables nest table_cell children);
- every node below the root carries `grounding = {page, range, box}`;
- `range` is `[start, end)` in Unicode code points into `markdown`;
- `box` is normalised page coordinates (0..1), at most 5 decimals;
- element ids are `<type>-<index>` counted per type in reading order.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

ElementType = Literal[
    "text", "table", "table_cell", "figure", "marginalia",
    "attestation", "logo", "card", "scan_code",
]


class Range(BaseModel):
    start: int
    end: int


class Box(BaseModel):
    xmin: float
    ymin: float
    xmax: float
    ymax: float

    def rounded(self) -> "Box":
        return Box(**{k: round(v, 5) for k, v in self.model_dump().items()})


class Grounding(BaseModel):
    page: int
    range: Range
    box: Box
    confidence: Optional[float] = None  # word-level only, Verity-style readers


class Element(BaseModel):
    type: ElementType
    id: str
    grounding: Grounding
    atomic_grounding: Optional[list[Grounding]] = None
    children: Optional[list["Element"]] = None  # table -> table_cell
    row: Optional[int] = None
    col: Optional[int] = None
    rowspan: Optional[int] = None
    colspan: Optional[int] = None
    markdown: Optional[str] = None  # only when inline_markdown is requested


class Page(BaseModel):
    type: Literal["page"] = "page"
    grounding: Grounding
    status: Literal["ok", "failed"] = "ok"
    reason: Optional[str] = None
    children: list[Element] = Field(default_factory=list)
    markdown: Optional[str] = None


class Document(BaseModel):
    type: Literal["document"] = "document"
    children: list[Page] = Field(default_factory=list)
    markdown: Optional[str] = None


class Billing(BaseModel):
    service_tier: str = "local"
    total_credits: float = 0.0


class ParseMetadata(BaseModel):
    job_id: str
    model_version: str
    page_count: int
    output_markdown_chars: int
    range_units: Literal["unicode_codepoints"] = "unicode_codepoints"
    failed_pages: list[int] = Field(default_factory=list)
    duration_ms: int = 0
    billing: Billing = Field(default_factory=Billing)
    openapi_spec: str = "https://docs.landing.ai/dpt3/openapi-adev2.json"


class ParseResponse(BaseModel):
    markdown: str
    metadata: ParseMetadata
    structure: Document
