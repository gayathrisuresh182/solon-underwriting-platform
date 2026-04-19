import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from .activities import (
    analyze_github_repo,
    emit_audit_event,
    evaluate_rules,
    extract_pitch_deck,
    extract_soc2_report,
    reconcile_sources,
)
from .submission_workflow import SubmissionWorkflow


async def main() -> None:
    client = await Client.connect(
        os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
    )

    worker = Worker(
        client,
        task_queue="submission-pipeline",
        workflows=[SubmissionWorkflow],
        activities=[
            extract_pitch_deck,
            extract_soc2_report,
            analyze_github_repo,
            reconcile_sources,
            evaluate_rules,
            emit_audit_event,
        ],
    )

    print("Temporal worker started — listening on queue 'submission-pipeline'", flush=True)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
