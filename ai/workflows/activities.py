from __future__ import annotations

import json
import os
import sys
import time
import traceback
from dataclasses import dataclass

import psycopg2
from temporalio import activity

# Ensure the ai/ directory is on sys.path so `app.*` and `knowledge_base.*`
# imports work regardless of how the worker is launched.
_AI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AI_DIR not in sys.path:
    sys.path.insert(0, _AI_DIR)


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
    metadata: dict
    success: bool
    error: str | None = None


def _get_dsn() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://solon:solon_dev@localhost:5432/solon")


def _save_source_result(source_id: str, status: str, result: dict | None, error: str | None = None) -> None:
    """Persist extraction results back to the submission_sources table."""
    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            if result:
                cur.execute(
                    """UPDATE submission_sources
                       SET status = %s,
                           extraction_result = %s::jsonb,
                           confidence_scores = %s::jsonb,
                           citations = %s::jsonb,
                           metadata = %s::jsonb
                       WHERE id = %s::uuid""",
                    (
                        status,
                        json.dumps(result.get("fields", {})),
                        json.dumps(result.get("confidence_scores", {})),
                        json.dumps(result.get("citations", {})),
                        json.dumps(result.get("metadata", {})),
                        source_id,
                    ),
                )
            else:
                cur.execute(
                    """UPDATE submission_sources
                       SET status = %s,
                           metadata = %s::jsonb
                       WHERE id = %s::uuid""",
                    (status, json.dumps({"error": error or "unknown"}), source_id),
                )
        conn.commit()
    finally:
        conn.close()


def _update_submission_status(submission_id: str, status: str) -> None:
    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE submissions SET status = %s, updated_at = NOW() WHERE id = %s::uuid",
                (status, submission_id),
            )
        conn.commit()
    finally:
        conn.close()


def _make_error_output(inp: ExtractionInput, error: str) -> ExtractionOutput:
    return ExtractionOutput(
        source_id=inp.source_id,
        source_type=inp.source_type,
        fields={},
        confidence_scores={},
        citations={},
        metadata={"error": error},
        success=False,
        error=error,
    )


# ═══════════════════════════════════════════════════════════════════════
# Extraction activities
# ═══════════════════════════════════════════════════════════════════════


@activity.defn
async def extract_pitch_deck(input: ExtractionInput) -> ExtractionOutput:
    """Extract risk fields from a pitch deck PDF using GPT-4o vision."""
    activity.logger.info(
        "Extracting pitch deck for submission %s, source %s, file %s",
        input.submission_id, input.source_id, input.file_path,
    )
    start = time.time()
    try:
        if not input.file_path or not os.path.isfile(input.file_path):
            raise FileNotFoundError(f"PDF not found: {input.file_path}")

        with open(input.file_path, "rb") as f:
            pdf_bytes = f.read()

        from app.extractor import extract_from_pdf
        result = await extract_from_pdf(pdf_bytes)

        output_result = {
            "fields": result.get("extracted_fields", {}),
            "confidence_scores": result.get("confidence_scores", {}),
            "citations": result.get("source_citations", {}),
            "metadata": {
                "source_type": "pitch_deck",
                "extraction_time_ms": result.get("extraction_time_ms", int((time.time() - start) * 1000)),
                "risk_score": result.get("risk_score"),
                "overall_confidence": result.get("overall_confidence"),
                "company_name": result.get("company_name"),
                "industry": result.get("industry"),
            },
        }

        _save_source_result(input.source_id, "completed", output_result)

        return ExtractionOutput(
            source_id=input.source_id,
            source_type=input.source_type,
            fields=output_result["fields"],
            confidence_scores=output_result["confidence_scores"],
            citations=output_result["citations"],
            metadata=output_result["metadata"],
            success=True,
        )

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        err_msg = f"{type(e).__name__}: {e}"
        activity.logger.error("Pitch deck extraction failed (%dms): %s", elapsed, err_msg)
        _save_source_result(input.source_id, "failed", None, err_msg)
        return _make_error_output(input, err_msg)


@activity.defn
async def extract_soc2_report(input: ExtractionInput) -> ExtractionOutput:
    """Extract security posture from SOC-2 report using hybrid vision + knowledge base."""
    activity.logger.info(
        "Extracting SOC-2 for submission %s, source %s, file %s",
        input.submission_id, input.source_id, input.file_path,
    )
    start = time.time()
    try:
        if not input.file_path or not os.path.isfile(input.file_path):
            raise FileNotFoundError(f"PDF not found: {input.file_path}")

        with open(input.file_path, "rb") as f:
            pdf_bytes = f.read()

        from app.soc2_extractor import extract_from_soc2
        result = await extract_from_soc2(pdf_bytes)

        _save_source_result(input.source_id, "completed", result)

        return ExtractionOutput(
            source_id=input.source_id,
            source_type=input.source_type,
            fields=result["fields"],
            confidence_scores=result["confidence_scores"],
            citations=result["citations"],
            metadata=result["metadata"],
            success=True,
        )

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        err_msg = f"{type(e).__name__}: {e}"
        activity.logger.error("SOC-2 extraction failed (%dms): %s", elapsed, err_msg)
        _save_source_result(input.source_id, "failed", None, err_msg)
        return _make_error_output(input, err_msg)


@activity.defn
async def analyze_github_repo(input: ExtractionInput) -> ExtractionOutput:
    """Analyze GitHub organization/repo for tech stack and security posture."""
    activity.logger.info(
        "Analyzing GitHub for submission %s, source %s, url %s",
        input.submission_id, input.source_id, input.url,
    )
    start = time.time()
    try:
        if not input.url:
            raise ValueError("GitHub URL is required")

        from app.github_analyzer import analyze_github_org
        result = await analyze_github_org(input.url)

        _save_source_result(input.source_id, "completed", result)

        return ExtractionOutput(
            source_id=input.source_id,
            source_type=input.source_type,
            fields=result["fields"],
            confidence_scores=result["confidence_scores"],
            citations=result["citations"],
            metadata=result["metadata"],
            success=True,
        )

    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        err_msg = f"{type(e).__name__}: {e}"
        activity.logger.error("GitHub analysis failed (%dms): %s", elapsed, err_msg)
        _save_source_result(input.source_id, "failed", None, err_msg)
        return _make_error_output(input, err_msg)


# ═══════════════════════════════════════════════════════════════════════
# Reconciliation & scoring (stubs — implemented in Prompt 2c)
# ═══════════════════════════════════════════════════════════════════════


@activity.defn
async def reconcile_sources(submission_id: str, extractions: list[dict]) -> dict:
    """Merge and reconcile extraction results from multiple sources."""
    activity.logger.info(
        "Reconciling %d sources for submission %s",
        len(extractions), submission_id,
    )
    from app.reconciler import reconcile
    result = reconcile(extractions)

    # Persist to reconciled_profiles table
    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO reconciled_profiles
                       (submission_id, merged_fields, field_sources, conflicts, coverage_score)
                   VALUES (%s::uuid, %s::jsonb, %s::jsonb, %s::jsonb, %s)""",
                (
                    submission_id,
                    json.dumps(result["merged_fields"]),
                    json.dumps(result["field_sources"]),
                    json.dumps(result["conflicts"]),
                    result["coverage_score"],
                ),
            )
        conn.commit()
    finally:
        conn.close()

    return result


@activity.defn
async def evaluate_rules(submission_id: str, reconciled_profile: dict) -> dict:
    """Apply declarative rules engine to produce risk score and decision."""
    activity.logger.info("Evaluating rules for submission %s", submission_id)

    rules_path = os.path.join(_AI_DIR, "rules", "underwriting_rules_v1.yaml")

    from app.rules_engine import evaluate
    result = evaluate(reconciled_profile, rules_path)

    # Persist to rule_evaluations table
    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO rule_evaluations
                       (submission_id, rules_version, rules_applied, risk_score,
                        risk_breakdown, decision, decision_reasons)
                   VALUES (%s::uuid, %s, %s::jsonb, %s, %s::jsonb, %s, %s::jsonb)""",
                (
                    submission_id,
                    result["rules_version"],
                    json.dumps(result["rules_applied"]),
                    result["risk_score"],
                    json.dumps(result["risk_breakdown"]),
                    result["decision"],
                    json.dumps(result["decision_reasons"]),
                ),
            )
        conn.commit()
    finally:
        conn.close()

    return result


# ═══════════════════════════════════════════════════════════════════════
# Audit logging
# ═══════════════════════════════════════════════════════════════════════


@activity.defn
async def emit_audit_event(submission_id: str, event_type: str, payload: dict) -> None:
    """Log an audit event for the submission."""
    dsn = _get_dsn()
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
