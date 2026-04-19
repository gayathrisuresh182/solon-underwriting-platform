from __future__ import annotations

import json
import os
from dataclasses import dataclass

import psycopg2
from temporalio import activity


@dataclass
class ExtractionInput:
    submission_id: str
    source_id: str
    source_type: str  # 'pitch_deck', 'soc2_report', 'github_repo'
    file_path: str | None = None
    url: str | None = None


@dataclass
class ExtractionOutput:
    source_id: str
    source_type: str
    fields: dict
    confidence_scores: dict
    citations: dict
    metadata: dict  # cost, timing, model, etc.
    success: bool
    error: str | None = None


# ── Extraction activities (stubs — implemented in Prompt 2b) ───────────


@activity.defn
async def extract_pitch_deck(input: ExtractionInput) -> ExtractionOutput:
    """Extract risk fields from a pitch deck PDF using GPT-4o vision."""
    activity.logger.info(f"Extracting pitch deck for submission {input.submission_id}")
    raise NotImplementedError("Pitch deck extraction — implemented in Prompt 2b")


@activity.defn
async def extract_soc2_report(input: ExtractionInput) -> ExtractionOutput:
    """Extract security posture from SOC-2 report using hybrid vision + knowledge base."""
    activity.logger.info(f"Extracting SOC-2 for submission {input.submission_id}")
    raise NotImplementedError("SOC-2 extraction — implemented in Prompt 2b")


@activity.defn
async def analyze_github_repo(input: ExtractionInput) -> ExtractionOutput:
    """Analyze GitHub repository for tech stack and security posture."""
    activity.logger.info(f"Analyzing GitHub for submission {input.submission_id}")
    raise NotImplementedError("GitHub analysis — implemented in Prompt 2b")


# ── Reconciliation & scoring (stubs — implemented in Prompt 2c) ───────


@activity.defn
async def reconcile_sources(submission_id: str, extractions: list[dict]) -> dict:
    """Merge and reconcile extraction results from multiple sources."""
    raise NotImplementedError("Reconciliation — implemented in Prompt 2c")


@activity.defn
async def evaluate_rules(submission_id: str, reconciled_profile: dict) -> dict:
    """Apply declarative rules engine to produce risk score and decision."""
    raise NotImplementedError("Rules evaluation — implemented in Prompt 2c")


# ── Audit logging (implemented now — used by everything) ──────────────


@activity.defn
async def emit_audit_event(submission_id: str, event_type: str, payload: dict) -> None:
    """Log an audit event for the submission.

    Uses psycopg2 (synchronous) — the blocking call is acceptable for a
    single-row INSERT and keeps the dependency set small.  A production
    system would swap in asyncpg or run via ``asyncio.to_thread``.
    """
    dsn = os.environ.get("DATABASE_URL", "")
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO audit_events (submission_id, event_type, payload)
                   VALUES (%s::uuid, %s, %s::jsonb)""",
                (submission_id, event_type, json.dumps(payload)),
            )
        conn.commit()
    finally:
        conn.close()
