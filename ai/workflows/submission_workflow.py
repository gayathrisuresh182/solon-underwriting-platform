from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from .activities import (
        ExtractionInput,
        ExtractionOutput,
        analyze_github_repo,
        emit_audit_event,
        evaluate_rules,
        extract_pitch_deck,
        extract_soc2_report,
        reconcile_sources,
    )

_EXTRACTOR_FOR_TYPE = {
    "pitch_deck": extract_pitch_deck,
    "soc2_report": extract_soc2_report,
    "github_repo": analyze_github_repo,
}


@workflow.defn
class SubmissionWorkflow:
    """Orchestrates the full underwriting pipeline for a submission."""

    def __init__(self) -> None:
        self.status = "created"
        self.human_approved = False
        self.extraction_results: list = []

    @workflow.run
    async def run(self, submission_id: str, sources: list[dict]) -> dict:
        retry = RetryPolicy(
            maximum_attempts=3,
            initial_interval=timedelta(seconds=2),
        )

        # Step 1: Emit submission started event
        await workflow.execute_activity(
            emit_audit_event,
            args=[submission_id, "submission_started", {"sources": [s["source_type"] for s in sources]}],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Step 2: Run all extractors in parallel
        self.status = "extracting"
        extraction_coros = []
        for source in sources:
            extractor = _EXTRACTOR_FOR_TYPE.get(source["source_type"])
            if extractor is None:
                continue

            inp = ExtractionInput(
                submission_id=submission_id,
                source_id=source["source_id"],
                source_type=source["source_type"],
                file_path=source.get("file_path"),
                url=source.get("url"),
            )
            extraction_coros.append(
                workflow.execute_activity(
                    extractor,
                    inp,
                    start_to_close_timeout=timedelta(minutes=5)
                    if source["source_type"] != "github_repo"
                    else timedelta(minutes=3),
                    retry_policy=retry,
                )
            )

        self.extraction_results = list(
            await asyncio.gather(*extraction_coros, return_exceptions=True)
        )

        successful = [
            r for r in self.extraction_results
            if isinstance(r, ExtractionOutput) and r.success
        ]

        await workflow.execute_activity(
            emit_audit_event,
            args=[
                submission_id,
                "extraction_completed",
                {
                    "total_sources": len(sources),
                    "successful": len(successful),
                    "failed": len(sources) - len(successful),
                },
            ],
            start_to_close_timeout=timedelta(seconds=10),
        )

        # Step 3: Reconcile
        self.status = "reconciling"
        reconciled = await workflow.execute_activity(
            reconcile_sources,
            args=[submission_id, [r.__dict__ for r in successful]],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        # Step 4: Apply rules engine
        self.status = "scoring"
        evaluation = await workflow.execute_activity(
            evaluate_rules,
            args=[submission_id, reconciled],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=retry,
        )

        decision = evaluation["decision"]
        self.status = f"scored_{decision}"

        # Step 5: If human review needed, wait for signal
        if decision == "human_review":
            self.status = "awaiting_human_review"
            await workflow.execute_activity(
                emit_audit_event,
                args=[submission_id, "human_review_requested", evaluation],
                start_to_close_timeout=timedelta(seconds=10),
            )
            await workflow.wait_condition(lambda: self.human_approved)
            self.status = "human_approved"

        elif decision == "decline":
            self.status = "declined"
            await workflow.execute_activity(
                emit_audit_event,
                args=[submission_id, "submission_declined", evaluation],
                start_to_close_timeout=timedelta(seconds=10),
            )
            return {"status": "declined", "evaluation": evaluation}

        self.status = "completed"
        return {
            "status": "completed",
            "reconciled_profile": reconciled,
            "evaluation": evaluation,
            "decision": decision,
        }

    @workflow.signal
    async def approve_human_review(self) -> None:
        """Signal sent when a human approves the submission."""
        self.human_approved = True

    @workflow.query
    def get_status(self) -> str:
        """Query the current workflow status."""
        return self.status
