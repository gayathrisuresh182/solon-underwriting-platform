import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";
import type { AIExtractionResult } from "@/lib/types";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://localhost:8081";

export async function POST(req: NextRequest) {
  try {
    const formData = await req.formData();
    const file = formData.get("file") as File | null;

    if (!file || !file.name.toLowerCase().endsWith(".pdf")) {
      return NextResponse.json(
        { error: "A PDF file is required" },
        { status: 400 },
      );
    }

    const aiForm = new FormData();
    const blob = new Blob([await file.arrayBuffer()], {
      type: "application/pdf",
    });
    aiForm.append("file", blob, file.name);

    const aiResp = await fetch(`${AI_SERVICE_URL}/extract`, {
      method: "POST",
      body: aiForm,
    });

    if (!aiResp.ok) {
      const errText = await aiResp.text();
      throw new Error(`AI service error ${aiResp.status}: ${errText}`);
    }

    const result: AIExtractionResult = await aiResp.json();

    const { rows } = await query(
      `INSERT INTO risk_profiles (
        company_name, industry, stage, headcount, revenue_range,
        handles_pii, handles_payments, uses_ai_in_product,
        b2b_or_b2c, geographic_scope, has_soc2,
        risk_score, overall_confidence,
        extracted_fields, confidence_scores, source_citations,
        source_filename, extraction_time_ms
      ) VALUES (
        $1, $2, $3, $4, $5,
        $6, $7, $8,
        $9, $10, $11,
        $12, $13,
        $14, $15, $16,
        $17, $18
      ) RETURNING id`,
      [
        result.company_name,
        result.industry,
        result.stage,
        result.headcount,
        result.revenue_range,
        result.handles_pii,
        result.handles_payments,
        result.uses_ai_in_product,
        result.b2b_or_b2c,
        result.geographic_scope,
        result.has_soc2,
        result.risk_score,
        result.overall_confidence,
        JSON.stringify(result.extracted_fields),
        JSON.stringify(result.confidence_scores),
        JSON.stringify(result.source_citations),
        file.name,
        result.extraction_time_ms ?? null,
      ],
    );

    return NextResponse.json({ id: rows[0].id, ...result });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    console.error("Extraction failed:", message);
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
