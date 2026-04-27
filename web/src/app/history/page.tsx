"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, ArrowUpRight, Inbox } from "lucide-react";

type Filter = "all" | "in_progress" | "completed" | "declined";

const STATUS_BADGES: Record<string, { label: string; cls: string }> = {
  created: { label: "Created", cls: "bg-slate-100 text-slate-600" },
  extracting: { label: "Extracting", cls: "bg-blue-50 text-blue-700 ring-1 ring-blue-200" },
  reconciling: { label: "Reconciling", cls: "bg-blue-50 text-blue-700 ring-1 ring-blue-200" },
  scoring: { label: "Scoring", cls: "bg-blue-50 text-blue-700 ring-1 ring-blue-200" },
  awaiting_human_review: { label: "Reviewing", cls: "bg-amber-50 text-amber-700 ring-1 ring-amber-200" },
  completed: { label: "Completed", cls: "bg-brand-50 text-brand-700 ring-1 ring-brand-200" },
  human_approved: { label: "Approved", cls: "bg-brand-50 text-brand-700 ring-1 ring-brand-200" },
  declined: { label: "Declined", cls: "bg-red-50 text-red-700 ring-1 ring-red-200" },
  bound: { label: "Bound", cls: "bg-brand-50 text-brand-700 ring-1 ring-brand-200" },
};

const DECISION_BADGES: Record<string, { label: string; cls: string }> = {
  auto_bind: { label: "Auto-bind", cls: "bg-brand-50 text-brand-700" },
  human_review: { label: "Human Review", cls: "bg-amber-50 text-amber-700" },
  decline: { label: "Decline", cls: "bg-red-50 text-red-700" },
};

function matchesFilter(s: any, filter: Filter): boolean {
  if (filter === "all") return true;
  const st = s.status || "created";
  if (filter === "in_progress") return ["created", "extracting", "reconciling", "scoring", "awaiting_human_review"].includes(st);
  if (filter === "completed") return ["completed", "human_approved", "bound"].includes(st);
  if (filter === "declined") return st === "declined";
  return true;
}

const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "in_progress", label: "In Progress" },
  { key: "completed", label: "Completed" },
  { key: "declined", label: "Declined" },
];

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
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-navy-900">Submission History</h1>
          <p className="mt-1 text-sm text-slate-400">{submissions.length} total submissions</p>
        </div>
        <Link href="/submit" className="btn-primary">New Submission</Link>
      </div>

      <div className="mb-6 flex items-center gap-0.5 rounded-xl bg-slate-100/80 p-1 w-fit">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            onClick={() => setFilter(f.key)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-all duration-200 ${
              filter === f.key
                ? "bg-white text-navy-900 shadow-sm"
                : "text-slate-500 hover:text-navy-800"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="flex justify-center py-20">
          <Loader2 className="h-8 w-8 animate-spin text-brand-500" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border-2 border-dashed border-slate-200 p-16 text-center">
          <Inbox className="mx-auto mb-4 h-12 w-12 text-slate-300" />
          <p className="text-base font-medium text-slate-500">No submissions found</p>
          <p className="mt-1 text-sm text-slate-400">Create a new submission to get started</p>
          <Link href="/submit" className="btn-primary mt-6 inline-flex">New Submission</Link>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-slate-200/80 shadow-card">
          <table className="min-w-full divide-y divide-slate-100 text-sm">
            <thead>
              <tr className="bg-slate-50/80">
                <th className="px-5 py-3.5 text-left text-xs font-semibold text-slate-500">Company</th>
                <th className="px-5 py-3.5 text-left text-xs font-semibold text-slate-500">Status</th>
                <th className="px-5 py-3.5 text-center text-xs font-semibold text-slate-500">Sources</th>
                <th className="px-5 py-3.5 text-center text-xs font-semibold text-slate-500">Risk Score</th>
                <th className="px-5 py-3.5 text-center text-xs font-semibold text-slate-500">Decision</th>
                <th className="px-5 py-3.5 text-right text-xs font-semibold text-slate-500">Date</th>
                <th className="px-5 py-3.5 w-10"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map((s: any) => {
                const badge = STATUS_BADGES[s.status] || STATUS_BADGES.created;
                const decBadge = s.decision ? DECISION_BADGES[s.decision] : null;
                return (
                  <tr key={s.id} className="group transition-colors hover:bg-slate-50/60">
                    <td className="px-5 py-4">
                      <Link href={`/submission/${s.id}`} className="font-semibold text-navy-900 transition-colors group-hover:text-brand-600">
                        {s.company_name || "\u2014"}
                      </Link>
                    </td>
                    <td className="px-5 py-4">
                      <span className={`inline-flex rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${badge.cls}`}>
                        {badge.label}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-center text-slate-500">{s.source_count || 0}</td>
                    <td className="px-5 py-4 text-center">
                      {s.risk_score != null ? (
                        <span className={`font-bold ${
                          parseFloat(s.risk_score) < 40 ? "text-brand-600" :
                          parseFloat(s.risk_score) < 70 ? "text-amber-500" :
                          "text-red-500"
                        }`}>
                          {Math.round(parseFloat(s.risk_score))}
                        </span>
                      ) : <span className="text-slate-300">\u2014</span>}
                    </td>
                    <td className="px-5 py-4 text-center">
                      {decBadge ? (
                        <span className={`inline-flex rounded-full px-2.5 py-0.5 text-[11px] font-medium ${decBadge.cls}`}>
                          {decBadge.label}
                        </span>
                      ) : <span className="text-slate-300">\u2014</span>}
                    </td>
                    <td className="px-5 py-4 text-right text-xs text-slate-400">
                      {new Date(s.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                    </td>
                    <td className="px-5 py-4">
                      <Link href={`/submission/${s.id}`} className="text-slate-300 transition-colors group-hover:text-brand-500">
                        <ArrowUpRight className="h-4 w-4" />
                      </Link>
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
