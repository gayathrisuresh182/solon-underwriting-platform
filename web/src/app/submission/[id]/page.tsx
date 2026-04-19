"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, CheckCircle2, XCircle, Loader2, Clock,
  AlertTriangle, ChevronDown, ShieldCheck, FileText, Github, Download
} from "lucide-react";
import ConfidenceBadge from "@/components/ConfidenceBadge";

const PIPELINE_STEPS = [
  { key: "sources", label: "Sources" },
  { key: "extracting", label: "Extracting" },
  { key: "reconciling", label: "Reconciling" },
  { key: "scoring", label: "Scoring" },
  { key: "decision", label: "Decision" },
];

function stepIndex(status: string): number {
  if (!status || status === "created") return 0;
  if (status === "extracting") return 1;
  if (status === "reconciling") return 2;
  if (status === "scoring" || status.startsWith("scored")) return 3;
  if (["awaiting_human_review", "human_approved", "completed", "declined", "bound"].includes(status)) return 4;
  return 0;
}

function isTerminal(status: string): boolean {
  return ["completed", "declined", "bound", "human_approved"].includes(status);
}

export default function SubmissionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`/api/submissions/${id}`);
      if (!res.ok) throw new Error("Failed to load");
      setData(await res.json());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  // Poll for updates
  useEffect(() => {
    fetchData();
    const interval = setInterval(() => {
      fetchData();
    }, 3000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Stop polling when terminal
  useEffect(() => {
    if (data && isTerminal(data.status)) {
      // No more polling needed, but we keep it simple
    }
  }, [data]);

  if (loading && !data) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-brand-500" />
      </div>
    );
  }
  if (error && !data) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <div className="rounded-lg bg-red-50 p-6 text-center text-red-700">{error}</div>
      </div>
    );
  }
  if (!data) return null;

  // Derive effective status from actual data presence (workflow may not update submissions.status)
  const effectiveStatus = (() => {
    const dbStatus = data.status || "created";
    if (data.policy || dbStatus === "bound") return "bound";
    if (data.quote) return "completed";
    if (data.evaluation) {
      const decision = data.evaluation.decision;
      if (decision === "decline") return "declined";
      if (decision === "human_review") {
        if (["completed", "human_approved", "bound"].includes(dbStatus)) return "completed";
        return "awaiting_human_review";
      }
      return "completed";
    }
    if (data.reconciled) return "scoring";
    if (data.sources?.some((s: any) => s.status === "completed")) return "reconciling";
    if (dbStatus === "extracting" || data.sources?.some((s: any) => s.status === "pending")) return "extracting";
    return dbStatus;
  })();
  const currentStep = stepIndex(effectiveStatus);
  const status = effectiveStatus;

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center gap-4">
        <Link href="/history" className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-xl font-bold text-slate-900">{data.company_name || "Submission"}</h1>
          <p className="text-xs text-slate-500">ID: {id}</p>
        </div>
        <StatusBadge status={status} />
      </div>

      {/* Pipeline Stepper */}
      <PipelineStepper currentStep={currentStep} status={status} />

      <div className="mt-8 space-y-8">
        {/* Sources */}
        {data.sources && <SourcesSection sources={data.sources} />}

        {/* Reconciliation */}
        {data.reconciled && <ReconciliationSection reconciled={data.reconciled} />}

        {/* Rules Evaluation */}
        {data.evaluation && (
          <EvaluationSection
            evaluation={data.evaluation}
            submissionId={id}
            status={status}
            onApproved={fetchData}
          />
        )}

        {/* Quote */}
        {(status === "completed" || status === "human_approved" || status === "bound" || data.quote) && (
          <QuoteSection submissionId={id} existingQuote={data.quote} existingPolicy={data.policy} companyName={data.company_name} />
        )}

        {/* Audit Trail */}
        {data.audit_events?.length > 0 && <AuditTrail events={data.audit_events} />}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════ */

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    created: "bg-slate-100 text-slate-600",
    extracting: "bg-blue-100 text-blue-700",
    reconciling: "bg-blue-100 text-blue-700",
    scoring: "bg-blue-100 text-blue-700",
    awaiting_human_review: "bg-amber-100 text-amber-700",
    human_approved: "bg-emerald-100 text-emerald-700",
    completed: "bg-emerald-100 text-emerald-700",
    declined: "bg-red-100 text-red-700",
    bound: "bg-emerald-100 text-emerald-700",
  };
  const labels: Record<string, string> = {
    created: "Created",
    extracting: "Extracting...",
    reconciling: "Reconciling...",
    scoring: "Scoring...",
    scored_auto_bind: "Auto-bind Eligible",
    scored_human_review: "Human Review",
    scored_decline: "Declined",
    awaiting_human_review: "Awaiting Review",
    human_approved: "Approved",
    completed: "Completed",
    declined: "Declined",
    bound: "Policy Bound",
  };
  return (
    <span className={`ml-auto rounded-full px-3 py-1 text-xs font-semibold ${styles[status] || "bg-slate-100 text-slate-600"}`}>
      {labels[status] || status}
    </span>
  );
}

function PipelineStepper({ currentStep, status }: { currentStep: number; status: string }) {
  return (
    <div className="flex items-center gap-1">
      {PIPELINE_STEPS.map((step, i) => {
        const completed = i < currentStep;
        const active = i === currentStep;
        const failed = i === currentStep && status === "declined";
        return (
          <div key={step.key} className="flex flex-1 items-center">
            <div className="flex flex-1 flex-col items-center">
              <div className={`flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold transition-all ${
                completed ? "bg-emerald-500 text-white" :
                failed ? "bg-red-500 text-white" :
                active ? "bg-brand-600 text-white ring-4 ring-brand-100" :
                "bg-slate-200 text-slate-500"
              }`}>
                {completed ? <CheckCircle2 className="h-4 w-4" /> :
                 failed ? <XCircle className="h-4 w-4" /> :
                 active && !isTerminal(status) ? <Loader2 className="h-4 w-4 animate-spin" /> :
                 i + 1}
              </div>
              <span className={`mt-1.5 text-[11px] font-medium ${active ? "text-brand-700" : completed ? "text-emerald-600" : "text-slate-400"}`}>
                {step.label}
              </span>
            </div>
            {i < PIPELINE_STEPS.length - 1 && (
              <div className={`h-0.5 flex-1 ${completed ? "bg-emerald-400" : "bg-slate-200"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

function SourcesSection({ sources }: { sources: any[] }) {
  const icons: Record<string, React.ReactNode> = {
    pitch_deck: <FileText className="h-4 w-4" />,
    soc2_report: <ShieldCheck className="h-4 w-4" />,
    github_repo: <Github className="h-4 w-4" />,
  };
  const labels: Record<string, string> = {
    pitch_deck: "Pitch Deck",
    soc2_report: "SOC-2 Report",
    github_repo: "GitHub",
  };

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">Sources</h2>
      <div className="grid gap-3 sm:grid-cols-3">
        {sources.map((src: any) => (
          <div key={src.id} className={`rounded-xl border p-4 ${src.status === "completed" ? "border-emerald-200 bg-emerald-50/30" : src.status === "failed" ? "border-red-200 bg-red-50/30" : "border-slate-200 bg-white"}`}>
            <div className="mb-2 flex items-center gap-2">
              <div className={`rounded p-1.5 ${src.status === "completed" ? "bg-emerald-100 text-emerald-600" : "bg-slate-100 text-slate-500"}`}>
                {icons[src.source_type] || <FileText className="h-4 w-4" />}
              </div>
              <span className="text-sm font-medium text-slate-900">{labels[src.source_type] || src.source_type}</span>
              {src.status === "completed" && <CheckCircle2 className="ml-auto h-4 w-4 text-emerald-500" />}
              {src.status === "pending" && <Loader2 className="ml-auto h-4 w-4 animate-spin text-blue-500" />}
              {src.status === "failed" && <XCircle className="ml-auto h-4 w-4 text-red-500" />}
            </div>
            <p className="truncate text-xs text-slate-500">{src.source_ref}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function ReconciliationSection({ reconciled }: { reconciled: any }) {
  const fields = reconciled.merged_fields || {};
  const fieldSources = reconciled.field_sources || {};
  const conflicts = reconciled.conflicts || [];
  const coverage = reconciled.coverage_score;
  const conflictFields = new Set(conflicts.map((c: any) => c.field));

  const fieldEntries = Object.entries(fields).filter(([k]) => !k.startsWith("_"));

  const sourceTag = (src: string) => {
    const colors: Record<string, string> = {
      pitch_deck: "bg-blue-100 text-blue-700",
      soc2_report: "bg-teal-100 text-teal-700",
      github_repo: "bg-purple-100 text-purple-700",
    };
    const labels: Record<string, string> = {
      pitch_deck: "PDF", soc2_report: "SOC-2", github_repo: "GitHub",
    };
    return (
      <span className={`inline-block rounded px-1.5 py-0.5 text-[10px] font-medium ${colors[src] || "bg-slate-100 text-slate-600"}`}>
        {labels[src] || src}
      </span>
    );
  };

  return (
    <section>
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">Reconciled Profile</h2>
        {coverage != null && (
          <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">
            {Math.round(coverage * 100)}% field coverage
          </span>
        )}
      </div>
      <div className="overflow-hidden rounded-xl border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-2.5 text-left font-medium text-slate-600">Field</th>
              <th className="px-4 py-2.5 text-left font-medium text-slate-600">Value</th>
              <th className="px-4 py-2.5 text-left font-medium text-slate-600">Source</th>
              <th className="px-4 py-2.5 text-center font-medium text-slate-600">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {fieldEntries.map(([key, val]) => {
              const hasConflict = conflictFields.has(key);
              const srcs = fieldSources[key] || [];
              return (
                <tr key={key} className={hasConflict ? "bg-amber-50/50" : "hover:bg-slate-50"}>
                  <td className="whitespace-nowrap px-4 py-2.5 font-medium text-slate-900">
                    <div className="flex items-center gap-1.5">
                      {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                      {hasConflict && <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />}
                    </div>
                  </td>
                  <td className="max-w-xs truncate px-4 py-2.5 text-slate-700">{formatFieldValue(String(val))}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-1">
                      {srcs.length > 1 ? <span className="inline-block rounded bg-slate-200 px-1.5 py-0.5 text-[10px] font-medium text-slate-700">Multiple</span> : srcs.map((s: string) => <span key={s}>{sourceTag(s)}</span>)}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    {hasConflict ? (
                      <span className="inline-flex items-center gap-1 rounded bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                        <AlertTriangle className="h-3 w-3" /> Conflict
                      </span>
                    ) : (
                      <CheckCircle2 className="mx-auto h-4 w-4 text-emerald-400" />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function formatFieldValue(val: string): string {
  try {
    const parsed = JSON.parse(val);
    if (Array.isArray(parsed)) return parsed.join(", ");
    if (typeof parsed === "object") return JSON.stringify(parsed);
  } catch { /* not JSON */ }
  if (val === "true") return "Yes";
  if (val === "false") return "No";
  return val;
}

function EvaluationSection({ evaluation, submissionId, status, onApproved }: {
  evaluation: any; submissionId: string; status: string; onApproved: () => void;
}) {
  const [approving, setApproving] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);

  const score = parseFloat(evaluation.risk_score) || 0;
  const decision = evaluation.decision;
  const breakdown = evaluation.risk_breakdown || [];
  const reasons = evaluation.decision_reasons || [];

  const handleApprove = async () => {
    if (!confirm("Approve this submission for quoting?")) return;
    setApproving(true);
    try {
      await fetch(`/api/submissions/${submissionId}/approve`, { method: "POST" });
      onApproved();
    } finally {
      setApproving(false);
    }
  };

  const decisionColors: Record<string, string> = {
    auto_bind: "bg-emerald-100 text-emerald-800 ring-emerald-600/20",
    human_review: "bg-amber-100 text-amber-800 ring-amber-600/20",
    decline: "bg-red-100 text-red-800 ring-red-600/20",
  };
  const decisionLabels: Record<string, string> = {
    auto_bind: "AUTO-BIND ELIGIBLE",
    human_review: "HUMAN REVIEW REQUIRED",
    decline: "DECLINED",
  };

  return (
    <section>
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">Risk Evaluation</h2>
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex items-center gap-6">
          <RiskGauge score={score} />
          <div className="flex-1">
            <span className={`inline-flex items-center rounded-full px-4 py-1.5 text-sm font-bold ring-1 ring-inset ${decisionColors[decision] || ""}`}>
              {decisionLabels[decision] || decision}
            </span>
            <div className="mt-3 space-y-1">
              {reasons.map((r: string, i: number) => (
                <p key={i} className="text-sm text-slate-600">• {r}</p>
              ))}
            </div>
          </div>
        </div>

        {status === "awaiting_human_review" && (
          <div className="mt-4 rounded-lg bg-amber-50 p-4">
            <p className="mb-3 text-sm text-amber-800">This submission requires human review before proceeding.</p>
            <button onClick={handleApprove} disabled={approving} className="btn-primary">
              {approving ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Approve Submission
            </button>
          </div>
        )}

        {decision === "decline" && evaluation.decline_explanation && (
          <div className="mt-4 rounded-lg bg-red-50 p-4">
            <h3 className="mb-2 text-sm font-semibold text-red-800">Decline Details</h3>
            <pre className="whitespace-pre-wrap text-xs text-red-700">{evaluation.decline_explanation}</pre>
          </div>
        )}

        {/* Rules Breakdown */}
        <div className="mt-4 border-t border-slate-100 pt-4">
          <button onClick={() => setRulesOpen(!rulesOpen)} className="flex w-full items-center justify-between text-sm font-medium text-slate-700">
            Rules Breakdown ({breakdown.length} rules fired)
            <ChevronDown className={`h-4 w-4 transition ${rulesOpen ? "rotate-180" : ""}`} />
          </button>
          {rulesOpen && (
            <div className="mt-3 overflow-hidden rounded-lg border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-xs">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Rule</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Category</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-600">Points</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {breakdown.map((rule: any, i: number) => (
                    <tr key={i} className="hover:bg-slate-50">
                      <td className="whitespace-nowrap px-3 py-2 font-medium text-slate-900">{rule.name}</td>
                      <td className="px-3 py-2"><span className="rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">{rule.category}</span></td>
                      <td className={`px-3 py-2 text-right font-semibold ${rule.risk_points > 0 ? "text-red-600" : rule.risk_points < 0 ? "text-emerald-600" : "text-slate-500"}`}>
                        {rule.risk_points > 0 ? "+" : ""}{rule.risk_points}
                      </td>
                      <td className="max-w-xs truncate px-3 py-2 text-slate-500">{rule.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function RiskGauge({ score }: { score: number }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.min(score, 100) / 100;
  const offset = circumference * (1 - pct);
  const color = score < 40 ? "#22c55e" : score < 70 ? "#f59e0b" : "#ef4444";
  const label = score < 40 ? "Low" : score < 70 ? "Moderate" : score < 90 ? "High" : "Critical";

  return (
    <div className="relative h-28 w-28 flex-shrink-0">
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#e2e8f0" strokeWidth="8" />
        <circle cx="50" cy="50" r={radius} fill="none" stroke={color} strokeWidth="8" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset} className="transition-all duration-700" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-2xl font-extrabold text-slate-900">{Math.round(score)}</span>
        <span className="text-[10px] font-medium uppercase tracking-wider text-slate-500">{label}</span>
      </div>
    </div>
  );
}

function QuoteSection({ submissionId, existingQuote, existingPolicy, companyName }: {
  submissionId: string; existingQuote: any; existingPolicy: any; companyName: string;
}) {
  const [quote, setQuote] = useState(existingQuote);
  const [policy, setPolicy] = useState(existingPolicy);
  const [loadingQuote, setLoadingQuote] = useState(false);
  const [binding, setBinding] = useState(false);

  const generateQuote = async () => {
    setLoadingQuote(true);
    try {
      const res = await fetch("/api/quote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ submission_id: submissionId }),
      });
      if (res.ok) setQuote(await res.json());
    } finally {
      setLoadingQuote(false);
    }
  };

  const bindPolicy = async () => {
    if (!quote || !confirm("Bind this policy? This action cannot be undone.")) return;
    setBinding(true);
    try {
      const res = await fetch("/api/bind", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quote_id: quote.id }),
      });
      if (res.ok) {
        const data = await res.json();
        setPolicy(data.policy);
      }
    } finally {
      setBinding(false);
    }
  };

  const downloadCOI = () => {
    if (!policy) return;
    import("jspdf").then(({ jsPDF }) => {
      const doc = new jsPDF();
      doc.setFontSize(18);
      doc.text("CERTIFICATE OF LIABILITY INSURANCE", 105, 25, { align: "center" });
      doc.setFontSize(10);
      doc.text(`Certificate Number: ${policy.certificate_number || "N/A"}`, 20, 40);
      doc.text(`Date: ${new Date().toLocaleDateString()}`, 20, 47);
      doc.setFontSize(12);
      doc.text("INSURED:", 20, 60);
      doc.setFontSize(11);
      doc.text(companyName || policy.holder_name || "N/A", 20, 68);
      doc.setFontSize(10);
      doc.text(`Policy Number: ${policy.policy_number}`, 20, 82);
      doc.text(`Effective Date: ${policy.effective_date}`, 20, 89);
      doc.text(`Expiration Date: ${policy.expiration_date}`, 20, 96);
      doc.text(`Total Premium: $${parseFloat(policy.total_premium).toLocaleString()}`, 20, 103);

      doc.setFontSize(11);
      doc.text("COVERAGE SUMMARY", 20, 118);
      doc.setFontSize(9);
      let y = 128;
      const coverages = typeof policy.coverages === "string" ? JSON.parse(policy.coverages) : policy.coverages;
      if (Array.isArray(coverages)) {
        doc.text("Coverage", 20, y); doc.text("Limit", 100, y); doc.text("Premium", 150, y);
        y += 6;
        doc.line(20, y, 190, y); y += 4;
        coverages.forEach((c: any) => {
          doc.text(c.name || c.type, 20, y);
          doc.text("$1,000,000 / $2,000,000", 100, y);
          doc.text(`$${c.annual_premium?.toLocaleString()}`, 150, y);
          y += 6;
        });
      }

      y += 10;
      doc.setFontSize(10);
      doc.text("Corgi Insurance Services, Inc.", 20, y);
      y += 12;
      doc.setFontSize(7);
      doc.text("This certificate is issued as a matter of information only and confers no rights upon the certificate holder.", 20, y);
      y += 5;
      doc.text("This certificate does not amend, extend or alter the coverage afforded by the policies listed herein.", 20, y);

      doc.save(`COI-${policy.policy_number}.pdf`);
    });
  };

  if (policy) {
    return (
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">Policy</h2>
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/30 p-6">
          <div className="mb-4 flex items-center gap-3">
            <CheckCircle2 className="h-8 w-8 text-emerald-500" />
            <div>
              <h3 className="text-lg font-bold text-emerald-800">Policy Bound</h3>
              <p className="text-sm text-emerald-600">{policy.policy_number}</p>
            </div>
          </div>
          <div className="mb-4 grid grid-cols-3 gap-4 text-sm">
            <div><span className="text-slate-500">Effective</span><br /><span className="font-medium">{new Date(policy.effective_date).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}</span></div>
            <div><span className="text-slate-500">Expiration</span><br /><span className="font-medium">{new Date(policy.expiration_date).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}</span></div>
            <div><span className="text-slate-500">Premium</span><br /><span className="font-bold text-emerald-800">${parseFloat(policy.total_premium).toLocaleString()}</span></div>
          </div>
          <button onClick={downloadCOI} className="btn-primary">
            <Download className="h-4 w-4" /> Download Certificate of Insurance
          </button>
        </div>
      </section>
    );
  }

  if (!quote) {
    return (
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">Quote</h2>
        <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center">
          <p className="mb-4 text-sm text-slate-500">Generate a coverage quote for this submission</p>
          <button onClick={generateQuote} disabled={loadingQuote} className="btn-primary">
            {loadingQuote ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Generate Quote
          </button>
        </div>
      </section>
    );
  }

  const coverages = typeof quote.coverages === "string" ? JSON.parse(quote.coverages) : quote.coverages;

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">Quote</h2>
      <div className="rounded-xl border border-slate-200 bg-white p-6">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <span className="text-lg font-bold text-slate-900">{quote.quote_number}</span>
            <p className="text-xs text-slate-500">Valid until {new Date(quote.valid_until).toLocaleDateString()}</p>
          </div>
        </div>
        <div className="overflow-hidden rounded-lg border border-slate-200">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium text-slate-600">Coverage</th>
                <th className="px-4 py-2.5 text-right font-medium text-slate-600">Base</th>
                <th className="px-4 py-2.5 text-left font-medium text-slate-600">Adjustments</th>
                <th className="px-4 py-2.5 text-right font-medium text-slate-600">Annual Premium</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {coverages.map((c: any, i: number) => (
                <tr key={i} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-medium text-slate-900">{c.name}</td>
                  <td className="px-4 py-3 text-right text-slate-600">${c.base_premium?.toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {c.adjustments?.map((a: any, j: number) => (
                        <span key={j} className="rounded bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700">
                          +${a.amount} {a.label}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right font-semibold text-slate-900">${c.annual_premium?.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-slate-50">
              <tr>
                <td colSpan={3} className="px-4 py-3 text-right text-sm font-bold text-slate-900">Total Annual Premium</td>
                <td className="px-4 py-3 text-right text-lg font-bold text-brand-700">${parseFloat(quote.total_annual_premium).toLocaleString()}</td>
              </tr>
            </tfoot>
          </table>
        </div>
        <div className="mt-4">
          <button onClick={bindPolicy} disabled={binding} className="btn-primary w-full text-base">
            {binding ? <Loader2 className="h-5 w-5 animate-spin" /> : null}
            Bind Policy
          </button>
        </div>
      </div>
    </section>
  );
}

function AuditTrail({ events }: { events: any[] }) {
  const typeColors: Record<string, string> = {
    submission_started: "bg-blue-100 text-blue-700",
    extraction_completed: "bg-emerald-100 text-emerald-700",
    human_review_requested: "bg-amber-100 text-amber-700",
    submission_declined: "bg-red-100 text-red-700",
  };

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">Audit Trail</h2>
      <div className="space-y-0">
        {events.map((evt: any, i: number) => (
          <div key={evt.id} className="flex gap-3">
            <div className="flex flex-col items-center">
              <div className="h-2.5 w-2.5 rounded-full bg-slate-300" />
              {i < events.length - 1 && <div className="w-px flex-1 bg-slate-200" />}
            </div>
            <div className="pb-4">
              <div className="flex items-center gap-2">
                <span className={`rounded px-2 py-0.5 text-[10px] font-semibold ${typeColors[evt.event_type] || "bg-slate-100 text-slate-600"}`}>
                  {evt.event_type}
                </span>
                <span className="text-[11px] text-slate-400">{new Date(evt.created_at).toLocaleString()}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
