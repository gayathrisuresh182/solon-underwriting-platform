"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2 } from "lucide-react";

type Filter = "all" | "in_progress" | "completed" | "declined";

const STATUS_BADGES: Record<string, { label: string; class: string }> = {
  created: { label: "Created", class: "bg-slate-100 text-slate-600" },
  extracting: { label: "Extracting", class: "bg-blue-100 text-blue-700" },
  reconciling: { label: "Reconciling", class: "bg-blue-100 text-blue-700" },
  scoring: { label: "Scoring", class: "bg-blue-100 text-blue-700" },
  awaiting_human_review: { label: "Reviewing", class: "bg-amber-100 text-amber-700" },
  completed: { label: "Completed", class: "bg-emerald-100 text-emerald-700" },
  human_approved: { label: "Approved", class: "bg-emerald-100 text-emerald-700" },
  declined: { label: "Declined", class: "bg-red-100 text-red-700" },
  bound: { label: "Bound", class: "bg-emerald-100 text-emerald-700" },
};

const DECISION_BADGES: Record<string, { label: string; class: string }> = {
  auto_bind: { label: "Auto-bind", class: "bg-emerald-50 text-emerald-700" },
  human_review: { label: "Human Review", class: "bg-amber-50 text-amber-700" },
  decline: { label: "Decline", class: "bg-red-50 text-red-700" },
};

function matchesFilter(s: any, filter: Filter): boolean {
  if (filter === "all") return true;
  const st = s.status || "created";
  if (filter === "in_progress") return ["created", "extracting", "reconciling", "scoring", "awaiting_human_review"].includes(st);
  if (filter === "completed") return ["completed", "human_approved", "bound"].includes(st);
  if (filter === "declined") return st === "declined";
  return true;
}

export default function HistoryPage() {
  const [submissions, setSubmissions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");

  useEffect(() => {
    fetch("/api/submissions")
      .then((r) => r.json())
      .then(setSubmissions)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const filtered = submissions.filter((s) => matchesFilter(s, filter));

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <h1 className="mb-6 text-2xl font-bold text-slate-900">Submission History</h1>

      {/* Filter tabs */}
      <div className="mb-6 flex gap-1 rounded-lg bg-slate-100 p-1">
        {(["all", "in_progress", "completed", "declined"] as Filter[]).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-md px-4 py-2 text-sm font-medium transition-colors ${
              filter === f ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"
            }`}
          >
            {f === "all" ? "All" : f === "in_progress" ? "In Progress" : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-brand-500" /></div>
      ) : filtered.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 p-12 text-center">
          <p className="text-slate-500">No submissions found</p>
          <Link href="/submit" className="btn-primary mt-4 inline-flex">New Submission</Link>
        </div>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Company</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Status</th>
                <th className="px-4 py-3 text-center font-medium text-slate-600">Sources</th>
                <th className="px-4 py-3 text-center font-medium text-slate-600">Risk Score</th>
                <th className="px-4 py-3 text-center font-medium text-slate-600">Decision</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((s: any) => {
                const badge = STATUS_BADGES[s.status] || STATUS_BADGES.created;
                const decBadge = s.decision ? DECISION_BADGES[s.decision] : null;
                return (
                  <tr key={s.id} className="group cursor-pointer transition-colors hover:bg-slate-50">
                    <td className="px-4 py-3">
                      <Link href={`/submission/${s.id}`} className="font-medium text-slate-900 group-hover:text-brand-700">
                        {s.company_name || "—"}
                      </Link>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${badge.class}`}>
                        {badge.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center text-slate-600">{s.source_count || 0}</td>
                    <td className="px-4 py-3 text-center">
                      {s.risk_score != null ? (
                        <span className={`font-semibold ${parseFloat(s.risk_score) < 40 ? "text-emerald-600" : parseFloat(s.risk_score) < 70 ? "text-amber-500" : "text-red-500"}`}>
                          {Math.round(parseFloat(s.risk_score))}
                        </span>
                      ) : <span className="text-slate-400">—</span>}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {decBadge ? (
                        <span className={`inline-flex rounded px-2 py-0.5 text-[11px] font-medium ${decBadge.class}`}>
                          {decBadge.label}
                        </span>
                      ) : <span className="text-slate-400">—</span>}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-500">
                      {new Date(s.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
