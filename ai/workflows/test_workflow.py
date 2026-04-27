"""
Test script: create a submission and kick off the Temporal workflow.

Usage:
    python -m workflows.test_workflow github https://github.com/coinbase
    python -m workflows.test_workflow pitch_deck /path/to/deck.pdf
    python -m workflows.test_workflow soc2 /path/to/soc2.pdf
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

_AI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AI_DIR not in sys.path:
    sys.path.insert(0, _AI_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(_AI_DIR, "..", ".env"))

import psycopg2
from temporalio.client import Client


def _get_dsn() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://solon:solon_dev@localhost:5432/solon")


def create_submission(company_name: str, sources: list[dict]) -> tuple[str, list[dict]]:
    """Insert a submission and its sources into the DB, return (submission_id, enriched_sources)."""
    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    submission_id = str(uuid.uuid4())
    enriched: list[dict] = []

    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO submissions (id, company_name, status, sources_attached)
                   VALUES (%s::uuid, %s, 'created', %s::jsonb)""",
                (submission_id, company_name, json.dumps([s["source_type"] for s in sources])),
            )
            for src in sources:
                source_id = str(uuid.uuid4())
                source_ref = src.get("url") or src.get("file_path") or ""
                cur.execute(
                    """INSERT INTO submission_sources (id, submission_id, source_type, source_ref, status)
                       VALUES (%s::uuid, %s::uuid, %s, %s, 'pending')""",
                    (source_id, submission_id, src["source_type"], source_ref),
                )
                enriched.append({
                    **src,
                    "source_id": source_id,
                })
        conn.commit()
    finally:
        conn.close()

    return submission_id, enriched


async def run_workflow(submission_id: str, sources: list[dict], wait: bool = True) -> dict | None:
    """Connect to Temporal and start the SubmissionWorkflow."""
    client = await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
    )

    workflow_id = f"submission-{submission_id}"
    print(f"Starting workflow {workflow_id}...", flush=True)

    from workflows.submission_workflow import SubmissionWorkflow

    if wait:
        try:
            result = await client.execute_workflow(
                SubmissionWorkflow.run,
                args=[submission_id, sources],
                id=workflow_id,
                task_queue="submission-pipeline",
            )
            return result
        except Exception as e:
            print(f"Workflow completed with error: {e}", flush=True)
            # Still try to query status
            handle = client.get_workflow_handle(workflow_id)
            try:
                status = await handle.query(SubmissionWorkflow.get_status)
                print(f"Workflow status at error: {status}", flush=True)
            except Exception:
                pass
            return None
    else:
        handle = await client.start_workflow(
            SubmissionWorkflow.run,
            args=[submission_id, sources],
            id=workflow_id,
            task_queue="submission-pipeline",
        )
        print(f"Workflow started (fire-and-forget): {handle.id}", flush=True)
        return None


def print_db_results(submission_id: str) -> None:
    """Query the DB and print what was saved."""
    dsn = _get_dsn()
    conn = psycopg2.connect(dsn)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status, sources_attached FROM submissions WHERE id = %s::uuid", (submission_id,))
            row = cur.fetchone()
            if row:
                print(f"\n  Submission status: {row[0]}")
                print(f"  Sources attached: {row[1]}")

            cur.execute(
                """SELECT id, source_type, source_ref, status, extraction_result, metadata
                   FROM submission_sources WHERE submission_id = %s::uuid""",
                (submission_id,),
            )
            for row in cur.fetchall():
                sid, stype, sref, status, result, meta = row
                print(f"\n  Source: {stype} ({status})")
                print(f"    Ref: {sref}")
                if result:
                    result_dict = json.loads(result) if isinstance(result, str) else result
                    for k in sorted(result_dict.keys())[:10]:
                        v = str(result_dict[k])[:100]
                        print(f"    {k}: {v}")
                if meta:
                    meta_dict = json.loads(meta) if isinstance(meta, str) else meta
                    for k in ("extraction_time_ms", "engineering_maturity_score", "repos_analyzed", "error"):
                        if k in meta_dict:
                            print(f"    meta.{k}: {meta_dict[k]}")

            cur.execute(
                "SELECT event_type, payload FROM audit_events WHERE submission_id = %s::uuid ORDER BY created_at",
                (submission_id,),
            )
            events = cur.fetchall()
            if events:
                print(f"\n  Audit events ({len(events)}):")
                for etype, payload in events:
                    payload_str = json.dumps(payload)[:120] if payload else ""
                    print(f"    [{etype}] {payload_str}")
    finally:
        conn.close()


async def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "github"
    target = sys.argv[2] if len(sys.argv) > 2 else "https://github.com/coinbase"

    if mode == "github":
        company = target.rstrip("/").split("/")[-1].title()
        sources = [{"source_type": "github_repo", "url": target}]
    elif mode == "pitch_deck":
        sources = [{"source_type": "pitch_deck", "file_path": os.path.abspath(target)}]
        company = "Test Company"
    elif mode == "soc2":
        sources = [{"source_type": "soc2_report", "file_path": os.path.abspath(target)}]
        company = "Test Company"
    else:
        print(f"Unknown mode: {mode}")
        return

    print(f"Creating submission for '{company}'...")
    submission_id, enriched_sources = create_submission(company, sources)
    print(f"  Submission ID: {submission_id}")
    for s in enriched_sources:
        print(f"  Source ID: {s['source_id']} ({s['source_type']})")

    print(f"\nStarting Temporal workflow...")
    result = await run_workflow(submission_id, enriched_sources)

    if result:
        print(f"\nWorkflow result:")
        print(f"  Status: {result.get('status')}")
        if "evaluation" in result:
            print(f"  Decision: {result['evaluation'].get('decision')}")

    print(f"\n{'='*60}")
    print(f"  Database state after workflow:")
    print(f"{'='*60}")
    print_db_results(submission_id)


if __name__ == "__main__":
    asyncio.run(main())
