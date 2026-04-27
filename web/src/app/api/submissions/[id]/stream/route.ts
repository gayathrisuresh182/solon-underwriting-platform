import { NextRequest } from "next/server";
import { query } from "@/lib/db";

async function getSubmissionData(id: string) {
  const { rows: submissions } = await query(
    `SELECT * FROM submissions WHERE id = $1::uuid`, [id],
  );
  if (submissions.length === 0) return null;

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

  return {
    ...submissions[0],
    sources,
    reconciled: reconciled[0] || null,
    evaluation: evaluation[0] || null,
    quote: quotes[0] || null,
    policy: policies[0] || null,
    audit_events: auditEvents,
  };
}

function deriveStatus(data: any): string {
  const dbStatus = data.status || "created";
  if (data.policy || dbStatus === "bound") return "bound";
  if (data.quote) return "completed";
  if (data.evaluation) {
    const decision = data.evaluation.decision;
    if (decision === "decline") return "declined";
    if (decision === "human_review") {
      if (["completed", "human_approved", "bound"].includes(dbStatus)) return "completed";
      return "awaiting_human_review";
    }
    return "completed";
  }
  if (data.reconciled) return "scoring";
  if (data.sources?.some((s: any) => s.status === "completed")) return "reconciling";
  if (dbStatus === "extracting" || data.sources?.some((s: any) => s.status === "pending")) return "extracting";
  return dbStatus;
}

const TERMINAL_STATUSES = new Set(["completed", "declined", "bound", "human_approved"]);

export async function GET(
  req: NextRequest,
  { params }: { params: { id: string } },
) {
  const { id } = params;
  const encoder = new TextEncoder();
  let cancelled = false;

  req.signal.addEventListener("abort", () => { cancelled = true; });

  const stream = new ReadableStream({
    async start(controller) {
      const send = (event: string, data: unknown) => {
        controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
      };

      try {
        let prevJson = "";

        while (!cancelled) {
          const data = await getSubmissionData(id);

          if (!data) {
            send("error", { message: "Submission not found" });
            break;
          }

          const curJson = JSON.stringify(data);
          if (curJson !== prevJson) {
            send("update", data);
            prevJson = curJson;
          }

          const effectiveStatus = deriveStatus(data);
          if (TERMINAL_STATUSES.has(effectiveStatus)) {
            send("complete", { status: effectiveStatus });
            break;
          }

          await new Promise<void>((resolve) => {
            const timer = setTimeout(resolve, 2000);
            req.signal.addEventListener("abort", () => {
              clearTimeout(timer);
              resolve();
            }, { once: true });
          });
        }
      } catch (err) {
        if (!cancelled) {
          send("error", { message: err instanceof Error ? err.message : "Stream error" });
        }
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
