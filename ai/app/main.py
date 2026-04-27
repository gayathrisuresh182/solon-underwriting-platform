from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .extractor import extract_from_pdf

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Solon AI Service", version="0.3.0")

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
# pgvector document query endpoint
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


# ═══════════════════════════════════════════════════════════════════════
# Workflow status API (#8)
# ═══════════════════════════════════════════════════════════════════════


async def _get_temporal_client():
    from temporalio.client import Client
    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    return await Client.connect(address)


@app.get("/submission/{submission_id}/status")
async def get_submission_status(submission_id: str):
    """Query the Temporal workflow for current submission status."""
    try:
        client = await _get_temporal_client()
        handle = client.get_workflow_handle(f"submission-{submission_id}")
        status = await handle.query("get_status")
        desc = await handle.describe()

        elapsed_seconds = None
        started_at = None
        if desc.start_time:
            started_at = desc.start_time.isoformat()
            import datetime
            elapsed_seconds = int(
                (datetime.datetime.now(datetime.timezone.utc) - desc.start_time).total_seconds()
            )

        return {
            "submission_id": submission_id,
            "status": status,
            "started_at": started_at,
            "elapsed_seconds": elapsed_seconds,
        }
    except Exception as e:
        error_msg = str(e).lower()
        if "not found" in error_msg or "no rows" in error_msg:
            raise HTTPException(status_code=404, detail=f"Workflow not found for submission {submission_id}")
        raise HTTPException(status_code=500, detail=f"Status query failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════
# Human review approval endpoint (#9)
# ═══════════════════════════════════════════════════════════════════════


@app.post("/submission/{submission_id}/approve")
async def approve_submission(submission_id: str):
    """Send the approve_human_review signal to the Temporal workflow."""
    try:
        client = await _get_temporal_client()
        handle = client.get_workflow_handle(f"submission-{submission_id}")

        from workflows.submission_workflow import SubmissionWorkflow
        await handle.signal(SubmissionWorkflow.approve_human_review)

        return {"status": "approved", "submission_id": submission_id}
    except Exception as e:
        error_msg = str(e).lower()
        if "not found" in error_msg or "no rows" in error_msg:
            raise HTTPException(status_code=404, detail=f"Workflow not found for submission {submission_id}")
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════
# Start Temporal workflow endpoint
# ═══════════════════════════════════════════════════════════════════════


class StartWorkflowRequest(BaseModel):
    submission_id: str
    sources: list[dict]


@app.post("/start-workflow")
async def start_workflow(req: StartWorkflowRequest):
    """Start the SubmissionWorkflow in Temporal."""
    try:
        client = await _get_temporal_client()
        from workflows.submission_workflow import SubmissionWorkflow

        handle = await client.start_workflow(
            SubmissionWorkflow.run,
            args=[req.submission_id, req.sources],
            id=f"submission-{req.submission_id}",
            task_queue="submission-pipeline",
        )

        return {
            "workflow_id": handle.id,
            "submission_id": req.submission_id,
            "status": "started",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")
