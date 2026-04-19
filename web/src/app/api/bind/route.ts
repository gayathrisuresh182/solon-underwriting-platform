import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";

function randomChars(n: number): string {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
  let result = "";
  for (let i = 0; i < n; i++) result += chars[Math.floor(Math.random() * chars.length)];
  return result;
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { quote_id } = body;
    if (!quote_id) {
      return NextResponse.json({ error: "quote_id required" }, { status: 400 });
    }

    const { rows: quotes } = await query(`SELECT * FROM quotes WHERE id = $1::uuid`, [quote_id]);
    if (quotes.length === 0) {
      return NextResponse.json({ error: "Quote not found" }, { status: 404 });
    }
    const quote = quotes[0];

    if (quote.status !== "active") {
      return NextResponse.json({ error: "Quote is no longer active" }, { status: 400 });
    }

    if (new Date(quote.valid_until) < new Date()) {
      return NextResponse.json({ error: "Quote has expired" }, { status: 400 });
    }

    // Check for existing policy
    const { rows: existingPolicies } = await query(
      `SELECT * FROM policies WHERE quote_id = $1::uuid LIMIT 1`, [quote_id],
    );
    if (existingPolicies.length > 0) {
      const policy = existingPolicies[0];
      const { rows: certs } = await query(
        `SELECT * FROM certificates WHERE policy_id = $1::uuid LIMIT 1`, [policy.id],
      );
      return NextResponse.json({ policy, certificate: certs[0] || null });
    }

    const now = new Date();
    const policyNumber = `POL-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}-${randomChars(6)}`;
    const effectiveDate = now.toISOString().split("T")[0];
    const expirationDate = new Date(now.getFullYear() + 1, now.getMonth(), now.getDate()).toISOString().split("T")[0];

    const { rows: [policy] } = await query(
      `INSERT INTO policies (quote_id, submission_id, policy_number, effective_date, expiration_date, total_premium, coverages)
       VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7::jsonb) RETURNING *`,
      [quote_id, quote.submission_id, policyNumber, effectiveDate, expirationDate, quote.total_annual_premium, JSON.stringify(quote.coverages)],
    );

    // Get company name for certificate
    const { rows: submissions } = await query(
      `SELECT company_name FROM submissions WHERE id = $1::uuid`, [quote.submission_id],
    );
    const holderName = submissions[0]?.company_name || "Unknown";

    const certNumber = `COI-${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, "0")}${String(now.getDate()).padStart(2, "0")}-${randomChars(6)}`;
    const { rows: [certificate] } = await query(
      `INSERT INTO certificates (policy_id, certificate_number, holder_name) VALUES ($1::uuid, $2, $3) RETURNING *`,
      [policy.id, certNumber, holderName],
    );

    // Mark quote as bound
    await query(`UPDATE quotes SET status = 'bound' WHERE id = $1::uuid`, [quote_id]);
    // Update submission status
    await query(`UPDATE submissions SET status = 'bound' WHERE id = $1::uuid`, [quote.submission_id]);

    return NextResponse.json({ policy, certificate });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
