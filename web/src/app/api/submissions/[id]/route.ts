import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  try {
    const { id } = params;

    const { rows: submissions } = await query(
      `SELECT * FROM submissions WHERE id = $1::uuid`, [id],
    );
    if (submissions.length === 0) {
      return NextResponse.json({ error: "Submission not found" }, { status: 404 });
    }

    const { rows: sources } = await query(
      `SELECT * FROM submission_sources WHERE submission_id = $1::uuid ORDER BY created_at`, [id],
    );

    const { rows: reconciled } = await query(
      `SELECT * FROM reconciled_profiles WHERE submission_id = $1::uuid ORDER BY created_at DESC LIMIT 1`, [id],
    );

    const { rows: evaluation } = await query(
      `SELECT * FROM rule_evaluations WHERE submission_id = $1::uuid ORDER BY created_at DESC LIMIT 1`, [id],
    );

    const { rows: quotes } = await query(
      `SELECT * FROM quotes WHERE submission_id = $1::uuid ORDER BY created_at DESC LIMIT 1`, [id],
    );

    const { rows: policies } = await query(
      `SELECT p.*, c.certificate_number, c.holder_name, c.issued_at as cert_issued_at
       FROM policies p
       LEFT JOIN certificates c ON c.policy_id = p.id
       WHERE p.submission_id = $1::uuid
       ORDER BY p.created_at DESC LIMIT 1`, [id],
    );

    const { rows: auditEvents } = await query(
      `SELECT * FROM audit_events WHERE submission_id = $1::uuid ORDER BY created_at DESC`, [id],
    );

    return NextResponse.json({
      ...submissions[0],
      sources,
      reconciled: reconciled[0] || null,
      evaluation: evaluation[0] || null,
      quote: quotes[0] || null,
      policy: policies[0] || null,
      audit_events: auditEvents,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
