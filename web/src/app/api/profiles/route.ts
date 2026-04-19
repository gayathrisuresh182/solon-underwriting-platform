import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function GET(req: NextRequest) {
  try {
    const id = req.nextUrl.searchParams.get("id");

    if (id) {
      const { rows: profiles } = await query(
        `SELECT * FROM risk_profiles WHERE id = $1`,
        [id],
      );
      if (profiles.length === 0) {
        return NextResponse.json(
          { error: "Profile not found" },
          { status: 404 },
        );
      }

      const { rows: overrides } = await query(
        `SELECT * FROM field_overrides WHERE risk_profile_id = $1 ORDER BY created_at DESC`,
        [id],
      );

      return NextResponse.json({ ...profiles[0], overrides });
    }

    const { rows } = await query(
      `SELECT id, company_name, industry, stage, risk_score, overall_confidence,
              source_filename, extraction_time_ms, created_at
       FROM risk_profiles ORDER BY created_at DESC LIMIT 50`,
    );
    return NextResponse.json(rows);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function PATCH(req: NextRequest) {
  try {
    const body = await req.json();
    const { profile_id, field_name, original_value, override_value, reason } =
      body;

    if (!profile_id || !field_name || override_value === undefined) {
      return NextResponse.json(
        { error: "profile_id, field_name, and override_value are required" },
        { status: 400 },
      );
    }

    const { rows } = await query(
      `INSERT INTO field_overrides (risk_profile_id, field_name, original_value, override_value, reason)
       VALUES ($1, $2, $3, $4, $5)
       RETURNING *`,
      [profile_id, field_name, original_value ?? null, override_value, reason ?? null],
    );

    return NextResponse.json(rows[0]);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
