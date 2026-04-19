import { NextRequest, NextResponse } from "next/server";
import { query } from "@/lib/db";

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || "http://localhost:8081";

export async function POST(_req: NextRequest, { params }: { params: { id: string } }) {
  try {
    const res = await fetch(`${AI_SERVICE_URL}/submission/${params.id}/approve`, {
      method: "POST",
    });
    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json(data, { status: res.status });
    }
    // Update DB status so frontend can pick it up
    await query(`UPDATE submissions SET status = 'completed', updated_at = NOW() WHERE id = $1::uuid`, [params.id]);
    return NextResponse.json(data);
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
