import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";

function randomChars(n: number): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  let result = "";
  for (let i = 0; i < n; i++) result += chars[Math.floor(Math.random() * chars.length)];
  return result;
}

interface CoverageLine {
  type: string;
  name: string;
  base_premium: number;
  adjustments: Array<{ label: string; amount: number }>;
  annual_premium: number;
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { submission_id } = body;
    if (!submission_id) {
      return NextResponse.json({ error: "submission_id required" }, { status: 400 });
    }

    // Check existing quote
    const { rows: existing } = await query(
      `SELECT * FROM quotes WHERE submission_id = $1::uuid AND status = 'active' LIMIT 1`,
      [submission_id],
    );
    if (existing.length > 0) {
      return NextResponse.json(existing[0]);
    }

    // Get reconciled profile and evaluation
    const { rows: reconciled } = await query(
      `SELECT * FROM reconciled_profiles WHERE submission_id = $1::uuid ORDER BY created_at DESC LIMIT 1`,
      [submission_id],
    );
    const { rows: evaluation } = await query(
      `SELECT * FROM rule_evaluations WHERE submission_id = $1::uuid ORDER BY created_at DESC LIMIT 1`,
      [submission_id],
    );

    if (!reconciled.length || !evaluation.length) {
      return NextResponse.json({ error: "Submission not yet evaluated" }, { status: 400 });
    }

    const fields = reconciled[0].merged_fields || {};
    const riskScore = parseFloat(evaluation[0].risk_score) || 50;
    const recCoverages = evaluation[0].rules_applied || [];

    const toBool = (v: unknown) => String(v).toLowerCase() === "true";
    const handlesPii = toBool(fields.handles_pii);
    const handlesPayments = toBool(fields.handles_payments);
    const usesAi = toBool(fields.uses_ai_in_product);
    const hasSoc2 = toBool(fields.has_soc2);
    const b2b = String(fields.b2b_or_b2c || "").toUpperCase() === "B2B";
    const headcount = parseInt(String(fields.headcount || "0")) || 0;
    const stage = String(fields.stage || "").toLowerCase();
    const engScore = parseFloat(String(fields.engineering_maturity_score || "0.5"));
    const geo = String(fields.geographic_scope || "").toLowerCase();

    const coverages: CoverageLine[] = [];

    // GL
    const glAdj: CoverageLine["adjustments"] = [];
    let glBase = 450;
    if (handlesPayments) glAdj.push({ label: "Handles payments", amount: 200 });
    if (!b2b) glAdj.push({ label: "B2C model", amount: 150 });
    if (headcount > 50) glAdj.push({ label: "50+ headcount", amount: 100 });
    const glTotal = glBase + glAdj.reduce((s, a) => s + a.amount, 0);
    coverages.push({ type: "gl", name: "General Liability", base_premium: glBase, adjustments: glAdj, annual_premium: glTotal });

    // Cyber
    const cyberAdj: CoverageLine["adjustments"] = [];
    let cyberBase = 600;
    if (handlesPii) cyberAdj.push({ label: "Handles PII", amount: 400 });
    if (handlesPayments) cyberAdj.push({ label: "Handles payments", amount: 300 });
    if (!hasSoc2) cyberAdj.push({ label: "No SOC-2", amount: 500 });
    if (engScore < 0.3) cyberAdj.push({ label: "Low eng maturity", amount: 200 });
    const cyberTotal = cyberBase + cyberAdj.reduce((s, a) => s + a.amount, 0);
    coverages.push({ type: "cyber", name: "Cyber Liability", base_premium: cyberBase, adjustments: cyberAdj, annual_premium: cyberTotal });

    // Tech E&O
    const teoAdj: CoverageLine["adjustments"] = [];
    let teoBase = 500;
    if (usesAi) teoAdj.push({ label: "AI in product", amount: 300 });
    if (b2b) teoAdj.push({ label: "Enterprise B2B", amount: 200 });
    const teoTotal = teoBase + teoAdj.reduce((s, a) => s + a.amount, 0);
    coverages.push({ type: "tech_eo", name: "Technology E&O", base_premium: teoBase, adjustments: teoAdj, annual_premium: teoTotal });

    // D&O
    const doAdj: CoverageLine["adjustments"] = [];
    let doBase = 800;
    if (stage.includes("seed") || stage.includes("pre")) doAdj.push({ label: "Early stage", amount: 200 });
    if (stage.includes("series")) doAdj.push({ label: "Funded", amount: 100 });
    if (headcount > 50) doAdj.push({ label: "50+ headcount", amount: 150 });
    const doTotal = doBase + doAdj.reduce((s, a) => s + a.amount, 0);
    coverages.push({ type: "d_and_o", name: "Directors & Officers", base_premium: doBase, adjustments: doAdj, annual_premium: doTotal });

    // EPLI
    const epliAdj: CoverageLine["adjustments"] = [];
    let epliBase = 350;
    if (headcount > 20) epliAdj.push({ label: "20+ headcount", amount: 150 });
    if (headcount > 100) epliAdj.push({ label: "100+ headcount", amount: 200 });
    if (geo.includes("international")) epliAdj.push({ label: "International", amount: 100 });
    const epliTotal = epliBase + epliAdj.reduce((s, a) => s + a.amount, 0);
    coverages.push({ type: "epli", name: "Employment Practices", base_premium: epliBase, adjustments: epliAdj, annual_premium: epliTotal });

    const totalPremium = coverages.reduce((s, c) => s + c.annual_premium, 0);

    const now = new Date();
    const quoteNumber = `QT-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}-${randomChars(4)}`;
    const validUntil = new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000);

    const { rows: [quote] } = await query(
      `INSERT INTO quotes (submission_id, quote_number, coverages, total_annual_premium, valid_until)
       VALUES ($1::uuid, $2, $3::jsonb, $4, $5) RETURNING *`,
      [submission_id, quoteNumber, JSON.stringify(coverages), totalPremium, validUntil.toISOString()],
    );

    return NextResponse.json(quote);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
