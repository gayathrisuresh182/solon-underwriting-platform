from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .extractor import extract_from_pdf

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Mini Hammurabi AI Service", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ai-extraction"}


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    pdf_bytes = await file.read()
    if len(pdf_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20 MB)")

    try:
        result = await extract_from_pdf(pdf_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return result


# ═══════════════════════════════════════════════════════════════════════
# pgvector document query endpoint (#13)
# ═══════════════════════════════════════════════════════════════════════


class DocumentQuery(BaseModel):
    source_id: str
    question: str
    top_k: Optional[int] = 3


@app.post("/query-document")
async def query_document(query: DocumentQuery):
    """Query a processed SOC-2 document using semantic search over embedded chunks."""
    from .soc2_vector import query_soc2_document

    try:
        results = await query_soc2_document(
            source_id=query.source_id,
            question=query.question,
            top_k=query.top_k or 3,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

    return {"source_id": query.source_id, "question": query.question, "results": results}
