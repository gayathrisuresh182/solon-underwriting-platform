import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";
import { writeFile, mkdir } from "fs/promises";
import path from "path";
import { randomUUID } from "crypto";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://localhost:8081";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const companyName = formData.get("company_name") as string;
    const pitchDeck = formData.get("pitch_deck") as File | null;
    const soc2Report = formData.get("soc2_report") as File | null;
    const githubUrl = formData.get("github_url") as string | null;

    if (!companyName?.trim()) {
      return NextResponse.json({ error: "Company name is required" }, { status: 400 });
    }

    const hasAnySource = pitchDeck || soc2Report || githubUrl?.trim();
    if (!hasAnySource) {
      return NextResponse.json({ error: "At least one source is required" }, { status: 400 });
    }

    // Create submission
    const { rows: [submission] } = await query(
      `INSERT INTO submissions (company_name, status) VALUES ($1, 'created') RETURNING id`,
      [companyName.trim()],
    );
    const submissionId = submission.id;

    // Save files and create sources
    const uploadDir = path.join(process.cwd(), "uploads", submissionId);
    await mkdir(uploadDir, { recursive: true });

    const sources: Array<{ source_id: string; source_type: string; file_path?: string; url?: string }> = [];

    if (pitchDeck) {
      const filePath = path.join(uploadDir, pitchDeck.name);
      const bytes = Buffer.from(await pitchDeck.arrayBuffer());
      await writeFile(filePath, bytes);

      const { rows: [src] } = await query(
        `INSERT INTO submission_sources (submission_id, source_type, source_ref, status)
         VALUES ($1::uuid, 'pitch_deck', $2, 'pending') RETURNING id`,
        [submissionId, pitchDeck.name],
      );
      sources.push({ source_id: src.id, source_type: "pitch_deck", file_path: filePath });
    }

    if (soc2Report) {
      const filePath = path.join(uploadDir, soc2Report.name);
      const bytes = Buffer.from(await soc2Report.arrayBuffer());
      await writeFile(filePath, bytes);

      const { rows: [src] } = await query(
        `INSERT INTO submission_sources (submission_id, source_type, source_ref, status)
         VALUES ($1::uuid, 'soc2_report', $2, 'pending') RETURNING id`,
        [submissionId, soc2Report.name],
      );
      sources.push({ source_id: src.id, source_type: "soc2_report", file_path: filePath });
    }

    if (githubUrl?.trim()) {
      const { rows: [src] } = await query(
        `INSERT INTO submission_sources (submission_id, source_type, source_ref, status)
         VALUES ($1::uuid, 'github_repo', $2, 'pending') RETURNING id`,
        [submissionId, githubUrl.trim()],
      );
      sources.push({ source_id: src.id, source_type: "github_repo", url: githubUrl.trim() });
    }

    // Start Temporal workflow via Python service
    try {
      await fetch(`${AI_SERVICE_URL}/start-workflow`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ submission_id: submissionId, sources }),
      });
      await query(`UPDATE submissions SET status = 'extracting' WHERE id = $1::uuid`, [submissionId]);
    } catch (e) {
      console.error("Failed to start workflow:", e);
      // Don't fail — the submission is created, workflow can be retried
    }

    return NextResponse.json({ submission_id: submissionId, status: "created", sources: sources.length });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("Create submission failed:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function GET() {
  try {
    const { rows } = await query(`
      SELECT
        s.id, s.company_name, s.status, s.created_at,
        (SELECT COUNT(*) FROM submission_sources WHERE submission_id = s.id) as source_count,
        re.risk_score, re.decision
      FROM submissions s
      LEFT JOIN rule_evaluations re ON s.id = re.submission_id
      ORDER BY s.created_at DESC
      LIMIT 100
    `);
    return NextResponse.json(rows);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
