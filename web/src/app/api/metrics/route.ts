import { NextResponse } from "next/server";
import { query } from "@/lib/db";

export async function GET() {
  try {
    const { rows: [summary] } = await query(`
      SELECT
        COUNT(DISTINCT s.id) as total_submissions,
        AVG(re.risk_score) as avg_risk_score,
        COUNT(CASE WHEN re.decision = 'auto_bind' THEN 1 END) as auto_bind_count,
        COUNT(CASE WHEN re.decision = 'human_review' THEN 1 END) as review_count,
        COUNT(CASE WHEN re.decision = 'decline' THEN 1 END) as decline_count
      FROM submissions s
      LEFT JOIN rule_evaluations re ON s.id = re.submission_id
    `);

    // Risk score distribution
    const { rows: distribution } = await query(`
      SELECT
        CASE
          WHEN risk_score < 20 THEN '0-20'
          WHEN risk_score < 40 THEN '20-40'
          WHEN risk_score < 60 THEN '40-60'
          WHEN risk_score < 80 THEN '60-80'
          ELSE '80-100'
        END as bucket,
        COUNT(*) as count
      FROM rule_evaluations
      GROUP BY bucket
      ORDER BY bucket
    `);

    // Submissions over time (last 30 days)
    const { rows: timeline } = await query(`
      SELECT DATE(created_at) as date, COUNT(*) as count
      FROM submissions
      WHERE created_at > NOW() - INTERVAL '30 days'
      GROUP BY DATE(created_at)
      ORDER BY date
    `);

    // Top rules fired
    const { rows: topRules } = await query(`
      SELECT
        rule_id,
        COUNT(*) as fire_count
      FROM rule_evaluations,
           jsonb_array_elements_text(rules_applied) as rule_id
      GROUP BY rule_id
      ORDER BY fire_count DESC
      LIMIT 10
    `);

    return NextResponse.json({
      total_submissions: parseInt(summary.total_submissions) || 0,
      avg_risk_score: summary.avg_risk_score ? parseFloat(parseFloat(summary.avg_risk_score).toFixed(1)) : null,
      auto_bind_count: parseInt(summary.auto_bind_count) || 0,
      review_count: parseInt(summary.review_count) || 0,
      decline_count: parseInt(summary.decline_count) || 0,
      risk_distribution: distribution,
      timeline,
      top_rules: topRules,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
