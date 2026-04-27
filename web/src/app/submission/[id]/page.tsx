"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft, CheckCircle2, XCircle, Loader2,
  AlertTriangle, ChevronDown, ShieldCheck, FileText,
  Github, Download, Clock, Zap,
} from "lucide-react";

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

  useEffect(() => {
    fetchData();

    const es = new EventSource(`/api/submissions/${id}/stream`);

    es.addEventListener("update", (e) => {
      setData(JSON.parse(e.data));
      setLoading(false);
    });

    es.addEventListener("complete", () => {
      es.close();
    });

    es.addEventListener("error", () => {
      es.close();
    });

    return () => es.close();
  }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <Loader2 className="mx-auto h-8 w-8 animate-spin text-brand-500" />
          <p className="mt-3 text-sm text-slate-400">Loading submission...</p>
        </div>
      </div>
    );
  }
  if (error && !data) {
    return (
      <div className="mx-auto max-w-3xl px-6 py-10">
        <div className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center text-red-700">{error}</div>
      </div>
    );
  }
  if (!data) return null;

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
      <div className="mb-8 flex items-center gap-4">
        <Link
          href="/history"
          className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-400 transition-all hover:bg-slate-100 hover:text-slate-600"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-navy-900">{data.company_name || "Submission"}</h1>
          <p className="mt-0.5 text-xs font-mono text-slate-400">{id}</p>
        </div>
        <StatusBadge status={status} />
      </div>

      <PipelineStepper currentStep={currentStep} status={status} />

      <div className="mt-10 space-y-10">
        {data.sources && <SourcesSection sources={data.sources} />}
        {data.reconciled && <ReconciliationSection reconciled={data.reconciled} />}
        {data.evaluation && (
          <EvaluationSection
            evaluation={data.evaluation}
            submissionId={id}
            status={status}
            onApproved={fetchData}
          />
        )}
        {(status === "completed" || status === "human_approved" || status === "bound" || data.quote) && (
          <QuoteSection submissionId={id} existingQuote={data.quote} existingPolicy={data.policy} companyName={data.company_name} />
        )}
        {data.audit_events?.length > 0 && <AuditTrail events={data.audit_events} />}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { label: string; cls: string }> = {
    created: { label: "Created", cls: "bg-slate-100 text-slate-600" },
    extracting: { label: "Extracting", cls: "bg-blue-50 text-blue-700 ring-1 ring-blue-200" },
    reconciling: { label: "Reconciling", cls: "bg-blue-50 text-blue-700 ring-1 ring-blue-200" },
    scoring: { label: "Scoring", cls: "bg-blue-50 text-blue-700 ring-1 ring-blue-200" },
    awaiting_human_review: { label: "Awaiting Review", cls: "bg-amber-50 text-amber-700 ring-1 ring-amber-200" },
    human_approved: { label: "Approved", cls: "bg-brand-50 text-brand-700 ring-1 ring-brand-200" },
    completed: { label: "Completed", cls: "bg-brand-50 text-brand-700 ring-1 ring-brand-200" },
    declined: { label: "Declined", cls: "bg-red-50 text-red-700 ring-1 ring-red-200" },
    bound: { label: "Policy Bound", cls: "bg-brand-50 text-brand-700 ring-1 ring-brand-200" },
  };
  const c = config[status] || config.created;
  return (
    <span className={`rounded-full px-4 py-1.5 text-xs font-semibold ${c.cls}`}>
      {c.label}
    </span>
  );
}

function PipelineStepper({ currentStep, status }: { currentStep: number; status: string }) {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
      <div className="flex items-center">
        {PIPELINE_STEPS.map((step, i) => {
          const completed = i < currentStep;
          const active = i === currentStep;
          const failed = i === currentStep && status === "declined";
          return (
            <div key={step.key} className="flex flex-1 items-center">
              <div className="flex flex-1 flex-col items-center">
                <div className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold transition-all duration-300 ${
                  completed ? "bg-brand-500 text-white" :
                  failed ? "bg-red-500 text-white" :
                  active ? "bg-navy-900 text-white ring-4 ring-navy-100" :
                  "bg-slate-100 text-slate-400"
                }`}>
                  {completed ? <CheckCircle2 className="h-5 w-5" /> :
                   failed ? <XCircle className="h-5 w-5" /> :
                   active && !isTerminal(status) ? <Loader2 className="h-5 w-5 animate-spin" /> :
                   i + 1}
                </div>
                <span className={`mt-2 text-xs font-medium ${
                  active ? "text-navy-900" :
                  completed ? "text-brand-600" :
                  "text-slate-400"
                }`}>
                  {step.label}
                </span>
              </div>
              {i < PIPELINE_STEPS.length - 1 && (
                <div className={`mx-1 h-0.5 flex-1 rounded-full transition-colors duration-500 ${
                  completed ? "bg-brand-400" : "bg-slate-200"
                }`} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SourcesSection({ sources }: { sources: any[] }) {
  const icons: Record<string, React.ReactNode> = {
    pitch_deck: <FileText className="h-5 w-5" />,
    soc2_report: <ShieldCheck className="h-5 w-5" />,
    github_repo: <Github className="h-5 w-5" />,
  };
  const labels: Record<string, string> = {
    pitch_deck: "Pitch Deck",
    soc2_report: "SOC-2 Report",
    github_repo: "GitHub",
  };

  return (
    <section>
      <h2 className="section-title mb-4">Sources</h2>
      <div className="grid gap-4 sm:grid-cols-3">
        {sources.map((src: any) => {
          const isCompleted = src.status === "completed";
          const isFailed = src.status === "failed";
          return (
            <div key={src.id} className={`rounded-2xl border p-5 transition-all duration-200 ${
              isCompleted ? "border-brand-200 bg-brand-50/30" :
              isFailed ? "border-red-200 bg-red-50/30" :
              "border-slate-200/80 bg-white"
            }`}>
              <div className="mb-3 flex items-center gap-3">
                <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${
                  isCompleted ? "bg-brand-100 text-brand-600" :
                  isFailed ? "bg-red-100 text-red-500" :
                  "bg-slate-100 text-slate-400"
                }`}>
                  {icons[src.source_type] || <FileText className="h-5 w-5" />}
                </div>
                <span className="flex-1 text-sm font-semibold text-navy-900">
                  {labels[src.source_type] || src.source_type}
                </span>
                {isCompleted && <CheckCircle2 className="h-5 w-5 text-brand-500" />}
                {src.status === "pending" && <Loader2 className="h-5 w-5 animate-spin text-blue-400" />}
                {isFailed && <XCircle className="h-5 w-5 text-red-400" />}
              </div>
              <p className="truncate text-xs text-slate-400">{src.source_ref}</p>
            </div>
          );
        })}
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

  const sourceColors: Record<string, string> = {
    pitch_deck: "bg-blue-50 text-blue-700 ring-1 ring-blue-200",
    soc2_report: "bg-teal-50 text-teal-700 ring-1 ring-teal-200",
    github_repo: "bg-purple-50 text-purple-700 ring-1 ring-purple-200",
  };
  const sourceLabels: Record<string, string> = {
    pitch_deck: "PDF", soc2_report: "SOC-2", github_repo: "GitHub",
  };

  return (
    <section>
      <div className="mb-4 flex items-center justify-between">
        <h2 className="section-title">Reconciled Profile</h2>
        {coverage != null && (
          <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">
            {Math.round(coverage * 100)}% field coverage
          </span>
        )}
      </div>
      <div className="overflow-hidden rounded-2xl border border-slate-200/80 shadow-card">
        <table className="min-w-full divide-y divide-slate-100 text-sm">
          <thead>
            <tr className="bg-slate-50/80">
              <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">Field</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">Value</th>
              <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">Source</th>
              <th className="px-5 py-3 text-center text-xs font-semibold text-slate-500">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {fieldEntries.map(([key, val]) => {
              const hasConflict = conflictFields.has(key);
              const srcs = fieldSources[key] || [];
              return (
                <tr key={key} className={hasConflict ? "bg-amber-50/40" : "hover:bg-slate-50/60"}>
                  <td className="whitespace-nowrap px-5 py-3 font-medium text-navy-900">
                    <div className="flex items-center gap-2">
                      {key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                      {hasConflict && <AlertTriangle className="h-3.5 w-3.5 text-amber-500" />}
                    </div>
                  </td>
                  <td className="max-w-xs truncate px-5 py-3 text-slate-600">{formatFieldValue(String(val))}</td>
                  <td className="px-5 py-3">
                    <div className="flex gap-1.5">
                      {srcs.length > 1
                        ? <span className="inline-block rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-600">Multiple</span>
                        : srcs.map((s: string) => (
                          <span key={s} className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-medium ${sourceColors[s] || "bg-slate-100 text-slate-600"}`}>
                            {sourceLabels[s] || s}
                          </span>
                        ))}
                    </div>
                  </td>
                  <td className="px-5 py-3 text-center">
                    {hasConflict ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-medium text-amber-700">
                        Conflict
                      </span>
                    ) : (
                      <CheckCircle2 className="mx-auto h-4 w-4 text-brand-400" />
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
  } catch {}
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

  const decisionConfig: Record<string, { label: string; cls: string; icon: React.ReactNode }> = {
    auto_bind: {
      label: "Auto-Bind Eligible",
      cls: "bg-brand-50 text-brand-800 ring-1 ring-brand-200",
      icon: <Zap className="h-4 w-4" />,
    },
    human_review: {
      label: "Human Review Required",
      cls: "bg-amber-50 text-amber-800 ring-1 ring-amber-200",
      icon: <Clock className="h-4 w-4" />,
    },
    decline: {
      label: "Declined",
      cls: "bg-red-50 text-red-800 ring-1 ring-red-200",
      icon: <XCircle className="h-4 w-4" />,
    },
  };

  const d = decisionConfig[decision];

  return (
    <section>
      <h2 className="section-title mb-4">Risk Evaluation</h2>
      <div className="rounded-2xl border border-slate-200/80 bg-white p-8 shadow-card">
        <div className="flex items-center gap-8">
          <RiskGauge score={score} />
          <div className="flex-1">
            {d && (
              <span className={`inline-flex items-center gap-2 rounded-full px-5 py-2 text-sm font-bold ${d.cls}`}>
                {d.icon}
                {d.label}
              </span>
            )}
            {reasons.length > 0 && (
              <div className="mt-4 space-y-1.5">
                {reasons.map((r: string, i: number) => (
                  <p key={i} className="text-sm text-slate-600">{r}</p>
                ))}
              </div>
            )}
          </div>
        </div>

        {status === "awaiting_human_review" && (
          <div className="mt-6 rounded-xl bg-amber-50/80 p-5">
            <p className="mb-3 text-sm text-amber-800">This submission requires human review before proceeding to quoting.</p>
            <button onClick={handleApprove} disabled={approving} className="btn-primary">
              {approving ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}
              Approve Submission
            </button>
          </div>
        )}

        {decision === "decline" && evaluation.decline_explanation && (
          <div className="mt-6 rounded-xl bg-red-50/80 p-5">
            <h3 className="mb-2 text-sm font-semibold text-red-800">Remediation Path</h3>
            <pre className="whitespace-pre-wrap text-xs leading-relaxed text-red-700">{evaluation.decline_explanation}</pre>
          </div>
        )}

        <div className="mt-6 border-t border-slate-100 pt-4">
          <button
            onClick={() => setRulesOpen(!rulesOpen)}
            className="flex w-full items-center justify-between rounded-xl px-1 py-2 text-sm font-semibold text-navy-800 transition-colors hover:bg-slate-50"
          >
            Rules Breakdown ({breakdown.length} rules fired)
            <ChevronDown className={`h-4 w-4 text-slate-400 transition-transform duration-200 ${rulesOpen ? "rotate-180" : ""}`} />
          </button>
          {rulesOpen && (
            <div className="mt-3 overflow-hidden rounded-xl border border-slate-200/80">
              <table className="min-w-full divide-y divide-slate-100 text-xs">
                <thead>
                  <tr className="bg-slate-50/80">
                    <th className="px-4 py-2.5 text-left font-semibold text-slate-500">Rule</th>
                    <th className="px-4 py-2.5 text-left font-semibold text-slate-500">Category</th>
                    <th className="px-4 py-2.5 text-right font-semibold text-slate-500">Points</th>
                    <th className="px-4 py-2.5 text-left font-semibold text-slate-500">Description</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {breakdown.map((rule: any, i: number) => (
                    <tr key={i} className="hover:bg-slate-50/60">
                      <td className="whitespace-nowrap px-4 py-2.5 font-medium text-navy-900">{rule.name}</td>
                      <td className="px-4 py-2.5">
                        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">{rule.category}</span>
                      </td>
                      <td className={`px-4 py-2.5 text-right font-bold ${
                        rule.risk_points > 0 ? "text-red-500" : rule.risk_points < 0 ? "text-brand-600" : "text-slate-400"
                      }`}>
                        {rule.risk_points > 0 ? "+" : ""}{rule.risk_points}
                      </td>
                      <td className="max-w-xs truncate px-4 py-2.5 text-slate-500">{rule.description}</td>
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
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  const pct = Math.min(score, 100) / 100;
  const offset = circumference * (1 - pct);
  const color = score < 40 ? "#f97316" : score < 70 ? "#f59e0b" : "#ef4444";
  const label = score < 40 ? "Low" : score < 70 ? "Moderate" : score < 90 ? "High" : "Critical";

  return (
    <div className="relative h-32 w-32 flex-shrink-0">
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="#f1f5f9" strokeWidth="6" />
        <circle
          cx="50" cy="50" r={radius} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={offset}
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold text-navy-900">{Math.round(score)}</span>
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">{label}</span>
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
      doc.setFontSize(16);
      doc.text("CERTIFICATE OF LIABILITY INSURANCE", 105, 25, { align: "center" });
      doc.setFontSize(9);
      doc.text(`Certificate Number: ${policy.certificate_number || "N/A"}`, 20, 40);
      doc.text(`Date: ${new Date().toLocaleDateString()}`, 20, 47);
      doc.setFontSize(11);
      doc.text("INSURED:", 20, 60);
      doc.text(companyName || policy.holder_name || "N/A", 20, 68);
      doc.setFontSize(9);
      doc.text(`Policy Number: ${policy.policy_number}`, 20, 82);
      doc.text(`Effective: ${policy.effective_date}`, 20, 89);
      doc.text(`Expiration: ${policy.expiration_date}`, 20, 96);
      doc.text(`Total Premium: $${parseFloat(policy.total_premium).toLocaleString()}`, 20, 103);

      doc.setFontSize(10);
      doc.text("COVERAGE SUMMARY", 20, 118);
      doc.setFontSize(8);
      let y = 128;
      const coverages = typeof policy.coverages === "string" ? JSON.parse(policy.coverages) : policy.coverages;
      if (Array.isArray(coverages)) {
        doc.text("Coverage", 20, y); doc.text("Limit", 100, y); doc.text("Premium", 155, y);
        y += 5; doc.line(20, y, 190, y); y += 4;
        coverages.forEach((c: any) => {
          doc.text(c.name || c.type, 20, y);
          doc.text("$1,000,000 / $2,000,000", 100, y);
          doc.text(`$${c.annual_premium?.toLocaleString()}`, 155, y);
          y += 6;
        });
      }
      y += 10;
      doc.setFontSize(9);
      doc.text("Solon Insurance Services — Demo Platform", 20, y);
      y += 10;
      doc.setFontSize(6);
      doc.text("This certificate is issued as a matter of information only and confers no rights upon the certificate holder.", 20, y);
      y += 4;
      doc.text("This certificate does not amend, extend or alter the coverage afforded by the policies listed herein.", 20, y);

      doc.save(`COI-${policy.policy_number}.pdf`);
    });
  };

  if (policy) {
    return (
      <section>
        <h2 className="section-title mb-4">Policy</h2>
        <div className="rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50/50 to-white p-8">
          <div className="mb-6 flex items-center gap-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-100">
              <CheckCircle2 className="h-7 w-7 text-brand-600" />
            </div>
            <div>
              <h3 className="text-xl font-bold text-navy-900">Policy Bound</h3>
              <p className="text-sm font-mono text-brand-600">{policy.policy_number}</p>
            </div>
          </div>
          <div className="mb-6 grid grid-cols-3 gap-6">
            <div className="rounded-xl bg-white/80 p-4">
              <span className="text-xs font-medium text-slate-400">Effective</span>
              <p className="mt-1 text-sm font-semibold text-navy-900">
                {new Date(policy.effective_date).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
              </p>
            </div>
            <div className="rounded-xl bg-white/80 p-4">
              <span className="text-xs font-medium text-slate-400">Expiration</span>
              <p className="mt-1 text-sm font-semibold text-navy-900">
                {new Date(policy.expiration_date).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
              </p>
            </div>
            <div className="rounded-xl bg-white/80 p-4">
              <span className="text-xs font-medium text-slate-400">Annual Premium</span>
              <p className="mt-1 text-lg font-bold text-brand-700">
                ${parseFloat(policy.total_premium).toLocaleString()}
              </p>
            </div>
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
        <h2 className="section-title mb-4">Quote</h2>
        <div className="rounded-2xl border-2 border-dashed border-slate-200 p-10 text-center">
          <Zap className="mx-auto mb-3 h-8 w-8 text-slate-300" />
          <p className="mb-4 text-sm text-slate-500">Generate a coverage quote based on the risk assessment</p>
          <button onClick={generateQuote} disabled={loadingQuote} className="btn-primary">
            {loadingQuote ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}
            Generate Quote
          </button>
        </div>
      </section>
    );
  }

  const coverages = typeof quote.coverages === "string" ? JSON.parse(quote.coverages) : quote.coverages;

  return (
    <section>
      <h2 className="section-title mb-4">Quote</h2>
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
        <div className="mb-5 flex items-center justify-between">
          <div>
            <span className="text-lg font-bold text-navy-900">{quote.quote_number}</span>
            <p className="mt-0.5 text-xs text-slate-400">
              Valid until {new Date(quote.valid_until).toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}
            </p>
          </div>
        </div>
        <div className="overflow-hidden rounded-xl border border-slate-200/80">
          <table className="min-w-full divide-y divide-slate-100 text-sm">
            <thead>
              <tr className="bg-slate-50/80">
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">Coverage</th>
                <th className="px-5 py-3 text-right text-xs font-semibold text-slate-500">Base</th>
                <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">Adjustments</th>
                <th className="px-5 py-3 text-right text-xs font-semibold text-slate-500">Annual Premium</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {coverages.map((c: any, i: number) => (
                <tr key={i} className="hover:bg-slate-50/60">
                  <td className="px-5 py-3.5 font-medium text-navy-900">{c.name}</td>
                  <td className="px-5 py-3.5 text-right text-slate-500">${c.base_premium?.toLocaleString()}</td>
                  <td className="px-5 py-3.5">
                    <div className="flex flex-wrap gap-1">
                      {c.adjustments?.map((a: any, j: number) => (
                        <span key={j} className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700 ring-1 ring-amber-200">
                          +${a.amount} {a.label}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-5 py-3.5 text-right font-semibold text-navy-900">${c.annual_premium?.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="bg-navy-900">
                <td colSpan={3} className="px-5 py-4 text-right text-sm font-bold text-white">Total Annual Premium</td>
                <td className="px-5 py-4 text-right text-xl font-bold text-white">${parseFloat(quote.total_annual_premium).toLocaleString()}</td>
              </tr>
            </tfoot>
          </table>
        </div>
        <div className="mt-5">
          <button onClick={bindPolicy} disabled={binding} className="btn-primary w-full py-4 text-base">
            {binding ? <Loader2 className="h-5 w-5 animate-spin" /> : <CheckCircle2 className="h-5 w-5" />}
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
    extraction_completed: "bg-brand-100 text-brand-700",
    human_review_requested: "bg-amber-100 text-amber-700",
    submission_declined: "bg-red-100 text-red-700",
  };

  return (
    <section>
      <h2 className="section-title mb-4">Audit Trail</h2>
      <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
        <div className="space-y-0">
          {events.map((evt: any, i: number) => (
            <div key={evt.id} className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className={`h-3 w-3 rounded-full ${
                  i === 0 ? "bg-brand-500 ring-4 ring-brand-100" : "bg-slate-300"
                }`} />
                {i < events.length - 1 && <div className="w-px flex-1 bg-slate-200" />}
              </div>
              <div className="pb-5">
                <div className="flex items-center gap-2">
                  <span className={`rounded-full px-2.5 py-0.5 text-[10px] font-semibold ${typeColors[evt.event_type] || "bg-slate-100 text-slate-600"}`}>
                    {evt.event_type.replace(/_/g, " ")}
                  </span>
                  <span className="text-[11px] text-slate-400">
                    {new Date(evt.created_at).toLocaleString("en-US", {
                      month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
                    })}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
