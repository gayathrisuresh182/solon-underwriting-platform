from __future__ import annotations

import base64
import io
import json
import logging
import time
from typing import Any

import fitz
from openai import AsyncOpenAI
from PIL import Image

from .prompts import EXTRACTION_PROMPT, SYSTEM_PROMPT

logger = logging.getLogger(__name__)

client: AsyncOpenAI | None = None

BOOL_FIELDS = {"handles_pii", "handles_payments", "uses_ai_in_product", "has_soc2"}
INT_FIELDS = {"headcount"}
LIST_FIELDS = {"tech_stack", "key_risks"}


def get_client() -> AsyncOpenAI:
    global client
    if client is None:
        client = AsyncOpenAI()
    return client


def _pdf_to_images(pdf_bytes: bytes) -> list[Image.Image]:
    """Convert each PDF page to a PIL Image using PyMuPDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images: list[Image.Image] = []
    for page in doc:
        pix = page.get_pixmap(dpi=150)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        images.append(img)
    doc.close()
    return images


def _image_to_base64(img: Image.Image, max_dim: int = 1024) -> str:
    img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _parse_bool(val: Any) -> bool | None:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "yes", "1")
    return None


def _parse_int(val: Any) -> int | None:
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _coerce_list(val: Any) -> list[str] | None:
    """Ensure list fields come back as a list of strings."""
    if isinstance(val, list):
        return [str(v) for v in val]
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
        return [val]
    return None


def _calculate_risk_score(fields: dict[str, Any]) -> int:
    """Deterministic risk scoring based on weighted field values."""
    score = 30  # base score

    if _parse_bool(fields.get("handles_pii")):
        score += 15
    if _parse_bool(fields.get("handles_payments")):
        score += 20
    if _parse_bool(fields.get("uses_ai_in_product")):
        score += 10
    if _parse_bool(fields.get("has_soc2")) is False:
        score += 15

    stage = str(fields.get("stage", "")).lower()
    if stage in ("pre-seed", "seed"):
        score += 10

    return min(score, 100)


def _calculate_overall_confidence(confidence: dict[str, float]) -> float:
    """Average of all per-field confidence scores."""
    if not confidence:
        return 0.0
    return round(sum(confidence.values()) / len(confidence), 2)


async def extract_from_pdf(pdf_bytes: bytes) -> dict[str, Any]:
    start = time.time()

    images = _pdf_to_images(pdf_bytes)
    if not images:
        raise ValueError("PDF has no extractable pages")

    merged_fields: dict[str, Any] = {}
    merged_confidence: dict[str, float] = {}
    merged_citations: dict[str, str] = {}

    for idx, img in enumerate(images, start=1):
        page_result = await _extract_page(img, idx)
        if page_result is None:
            continue

        page_fields = page_result.get("fields", {})
        page_confidence = page_result.get("confidence", {})
        page_citations = page_result.get("citations", {})

        for field, value in page_fields.items():
            if value is None:
                continue
            new_conf = float(page_confidence.get(field, 0.5))
            old_conf = merged_confidence.get(field, -1.0)
            if new_conf > old_conf:
                merged_fields[field] = value
                merged_confidence[field] = new_conf
                merged_citations[field] = page_citations.get(field, f"page {idx}")

    risk_score = _calculate_risk_score(merged_fields)
    overall_confidence = _calculate_overall_confidence(merged_confidence)
    elapsed_ms = int((time.time() - start) * 1000)

    top_level = _build_top_level(merged_fields)

    confidence_levels: dict[str, str] = {}
    for k, v in merged_confidence.items():
        if v >= 0.8:
            confidence_levels[k] = "high"
        elif v >= 0.5:
            confidence_levels[k] = "medium"
        else:
            confidence_levels[k] = "low"

    # Stringify list fields for the JSONB store
    serialized_fields: dict[str, str] = {}
    for k, v in merged_fields.items():
        if isinstance(v, (list, dict)):
            serialized_fields[k] = json.dumps(v)
        else:
            serialized_fields[k] = str(v)

    return {
        **top_level,
        "risk_score": risk_score,
        "overall_confidence": overall_confidence,
        "extracted_fields": serialized_fields,
        "confidence_scores": confidence_levels,
        "source_citations": merged_citations,
        "extraction_time_ms": elapsed_ms,
    }


def _build_top_level(fields: dict[str, Any]) -> dict[str, Any]:
    """Extract the typed top-level columns from the merged fields dict."""
    return {
        "company_name": fields.get("company_name", "Unknown Company"),
        "industry": fields.get("industry"),
        "stage": fields.get("stage"),
        "headcount": _parse_int(fields.get("headcount")),
        "revenue_range": fields.get("revenue_range"),
        "handles_pii": _parse_bool(fields.get("handles_pii")),
        "handles_payments": _parse_bool(fields.get("handles_payments")),
        "uses_ai_in_product": _parse_bool(fields.get("uses_ai_in_product")),
        "b2b_or_b2c": fields.get("b2b_or_b2c"),
        "geographic_scope": fields.get("geographic_scope"),
        "has_soc2": _parse_bool(fields.get("has_soc2")),
    }


async def _extract_page(img: Image.Image, page_number: int) -> dict | None:
    """Send a single page image to GPT-4o and return parsed JSON, or None on failure."""
    b64 = _image_to_base64(img)
    oai = get_client()

    try:
        resp = await oai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": EXTRACTION_PROMPT.format(page_number=page_number),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{b64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=2000,
        )

        raw = resp.choices[0].message.content or "{}"
        data = json.loads(raw)

        if not isinstance(data, dict) or "fields" not in data:
            logger.warning(
                "Page %d: GPT-4o returned JSON without 'fields' key, skipping",
                page_number,
            )
            return None

        return data

    except json.JSONDecodeError:
        logger.warning(
            "Page %d: GPT-4o returned malformed JSON, skipping", page_number
        )
        return None
    except Exception:
        logger.exception("Page %d: extraction failed", page_number)
        return None
