"use client";

import type { RiskProfile } from "@/lib/types";
import { confidenceToNumeric } from "@/lib/types";

function gaugeColor(score: number): string {
  if (score < 40) return "#22c55e";  // green — low risk
  if (score < 70) return "#f59e0b";  // amber — moderate
  return "#ef4444";                  // red — high risk
}

function riskLabel(score: number): string {
  if (score < 40) return "Low Risk";
  if (score < 70) return "Moderate";
  return "High Risk";
}

function RiskGauge({ score }: { score: number }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.min(score, 100) / 100;
  const offset = circumference * (1 - pct);
  const color = gaugeColor(score);

  return (
    <div className="relative h-28 w-28 flex-shrink-0">
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth="8"
        />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-all duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-extrabold text-slate-900">{score}</span>
        <span className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
          {riskLabel(score)}
        </span>
      </div>
    </div>
  );
}

interface RiskProfileCardProps {
  profile: RiskProfile;
}

export default function RiskProfileCard({ profile }: RiskProfileCardProps) {
  const fieldCount = Object.keys(profile.extracted_fields ?? {}).length;
  const confidenceScores = profile.confidence_scores ?? {};
  const avgConf =
    Object.values(confidenceScores).length > 0
      ? Object.values(confidenceScores).reduce(
          (sum, level) => sum + confidenceToNumeric(level),
          0,
        ) / Object.values(confidenceScores).length
      : 0;
  const reviewCount = Object.values(confidenceScores).filter(
    (l) => confidenceToNumeric(l) < 0.5,
  ).length;

  return (
    <div className="card space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="truncate text-xl font-bold text-slate-900">
            {profile.company_name}
          </h2>
          <div className="mt-1.5 flex flex-wrap items-center gap-2">
            {profile.industry && (
              <span className="badge bg-brand-100 text-brand-800">
                {profile.industry}
              </span>
            )}
            {profile.stage && (
              <span className="badge bg-slate-100 text-slate-700">
                {profile.stage}
              </span>
            )}
            {profile.extraction_time_ms != null && (
              <span className="text-xs text-slate-400">
                {(profile.extraction_time_ms / 1000).toFixed(1)}s extraction
              </span>
            )}
          </div>
        </div>

        {profile.risk_score !== null && (
          <RiskGauge score={profile.risk_score} />
        )}
      </div>

      {/* Stats bar */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-slate-100 pt-4 text-xs text-slate-500">
        <Stat label="Fields Extracted" value={String(fieldCount)} />
        <Stat label="Avg. Confidence" value={`${Math.round(avgConf * 100)}%`} />
        {profile.extraction_time_ms != null && (
          <Stat
            label="Extraction Time"
            value={`${(profile.extraction_time_ms / 1000).toFixed(1)}s`}
          />
        )}
        {reviewCount > 0 && (
          <Stat
            label="Needs Review"
            value={String(reviewCount)}
            warn
          />
        )}
      </div>
    </div>
  );
}

function Stat({
  label,
  value,
  warn,
}: {
  label: string;
  value: string;
  warn?: boolean;
}) {
  return (
    <div>
      <span className={`font-semibold ${warn ? "text-amber-600" : "text-slate-900"}`}>
        {value}
      </span>{" "}
      {label}
    </div>
  );
}
