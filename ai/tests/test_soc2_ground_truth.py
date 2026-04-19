"""
SOC-2 Ground Truth Evaluation (#16).

Tests extraction accuracy against synthetic PDFs with known findings:
- coinbase_soc2.pdf: unqualified opinion, 1 exception (CC7.2 monitoring)
- healthpulse_soc2.pdf: qualified opinion, 3 exceptions (CC6.1 access, CC6.3 role-based access, CC7.4 incident response)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

_AI_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _AI_DIR not in sys.path:
    sys.path.insert(0, _AI_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(_AI_DIR, "..", ".env"))


GROUND_TRUTH = {
    "coinbase_soc2.pdf": {
        "opinion": "unqualified",
        "exception_criteria": {"CC7.2"},
        "exception_count": 1,
    },
    "healthpulse_soc2.pdf": {
        "opinion": "qualified",
        "exception_criteria": {"CC6.1", "CC6.3", "CC7.4"},
        "exception_count": 3,
    },
}


def _extract_found_criteria(metadata: dict) -> set[str]:
    """Pull exception criteria IDs from extraction metadata."""
    details = metadata.get("exception_details", [])
    return {d.get("criteria_id", "") for d in details if d.get("criteria_id")}


async def evaluate_single(pdf_name: str) -> dict:
    """Run extraction on one PDF and compare to ground truth."""
    from app.soc2_extractor import extract_from_soc2

    pdf_path = os.path.join(_AI_DIR, "test_data", pdf_name)
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    result = await extract_from_soc2(pdf_bytes)
    meta = result.get("metadata", {})
    fields = result.get("fields", {})

    truth = GROUND_TRUTH[pdf_name]
    extracted_opinion = meta.get("audit_opinion", fields.get("audit_opinion", "unknown"))
    extracted_criteria = _extract_found_criteria(meta)
    extracted_count = meta.get("exceptions_found", 0)

    # Scoring
    opinion_correct = extracted_opinion == truth["opinion"]
    true_positives = extracted_criteria & truth["exception_criteria"]
    false_negatives = truth["exception_criteria"] - extracted_criteria
    false_positives = extracted_criteria - truth["exception_criteria"]

    precision = len(true_positives) / len(extracted_criteria) if extracted_criteria else 0
    recall = len(true_positives) / len(truth["exception_criteria"]) if truth["exception_criteria"] else 1
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        "pdf": pdf_name,
        "opinion_correct": opinion_correct,
        "expected_opinion": truth["opinion"],
        "extracted_opinion": extracted_opinion,
        "expected_criteria": sorted(truth["exception_criteria"]),
        "extracted_criteria": sorted(extracted_criteria),
        "true_positives": sorted(true_positives),
        "false_negatives": sorted(false_negatives),
        "false_positives": sorted(false_positives),
        "expected_count": truth["exception_count"],
        "extracted_count": extracted_count,
        "precision": round(precision, 2),
        "recall": round(recall, 2),
        "f1_score": round(f1, 2),
        "signal_evidence": meta.get("signal_evidence", {}),
        "extraction_time_ms": meta.get("extraction_time_ms", 0),
    }


async def run_evaluation() -> list[dict]:
    results = []
    for pdf_name in GROUND_TRUTH:
        print(f"\n{'=' * 60}")
        print(f"Evaluating: {pdf_name}")
        print('=' * 60)

        eval_result = await evaluate_single(pdf_name)
        results.append(eval_result)

        status = "PASS" if eval_result["opinion_correct"] and eval_result["recall"] == 1.0 else "FAIL"
        print(f"\n  [{status}] {pdf_name}")
        print(f"  Opinion:  expected={eval_result['expected_opinion']}  "
              f"extracted={eval_result['extracted_opinion']}  "
              f"{'OK' if eval_result['opinion_correct'] else 'WRONG'}")
        print(f"  Exceptions: expected={eval_result['expected_count']}  "
              f"extracted={eval_result['extracted_count']}")
        print(f"  Expected criteria:  {eval_result['expected_criteria']}")
        print(f"  Extracted criteria: {eval_result['extracted_criteria']}")
        print(f"  True positives:  {eval_result['true_positives']}")
        print(f"  False negatives: {eval_result['false_negatives']}")
        print(f"  False positives: {eval_result['false_positives']}")
        print(f"  Precision={eval_result['precision']}  "
              f"Recall={eval_result['recall']}  "
              f"F1={eval_result['f1_score']}")
        print(f"  Signal evidence: {json.dumps(eval_result['signal_evidence'], indent=2)}")
        print(f"  Extraction time: {eval_result['extraction_time_ms']}ms")

    # Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print('=' * 60)
    all_pass = True
    for r in results:
        passed = r["opinion_correct"] and r["recall"] == 1.0
        if not passed:
            all_pass = False
        marker = "PASS" if passed else "FAIL"
        print(f"  [{marker}] {r['pdf']} — F1={r['f1_score']} "
              f"opinion={'OK' if r['opinion_correct'] else 'WRONG'}")

    print(f"\n  Overall: {'ALL PASS' if all_pass else 'SOME FAILURES'}")
    return results


if __name__ == "__main__":
    asyncio.run(run_evaluation())
