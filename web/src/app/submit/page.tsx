"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Upload, Github, ShieldCheck, FileText, CheckCircle2, Loader2, AlertCircle, ArrowRight } from "lucide-react";

type SourceStatus = "empty" | "uploaded" | "entered" | "ready";

interface SourceState {
  pitchDeck: { file: File | null; status: SourceStatus };
  github: { url: string; status: SourceStatus };
  soc2: { file: File | null; status: SourceStatus };
}

export default function SubmitPage() {
  const router = useRouter();
  const [companyName, setCompanyName] = useState("");
  const [sources, setSources] = useState<SourceState>({
    pitchDeck: { file: null, status: "empty" },
    github: { url: "", status: "empty" },
    soc2: { file: null, status: "empty" },
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pitchRef = useRef<HTMLInputElement>(null);
  const soc2Ref = useRef<HTMLInputElement>(null);

  const hasAnySrc = sources.pitchDeck.file || sources.github.url.trim() || sources.soc2.file;
  const canSubmit = companyName.trim() && hasAnySrc && !submitting;

  const handlePitchDeck = useCallback((file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) return;
    setSources((s) => ({ ...s, pitchDeck: { file, status: "ready" } }));
  }, []);

  const handleSoc2 = useCallback((file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) return;
    setSources((s) => ({ ...s, soc2: { file, status: "ready" } }));
  }, []);

  const handleGithubUrl = useCallback((url: string) => {
    const valid = /^https?:\/\/(www\.)?github\.com\/[\w-]+/i.test(url);
    setSources((s) => ({ ...s, github: { url, status: url.trim() ? (valid ? "ready" : "entered") : "empty" } }));
  }, []);

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);

    try {
      const form = new FormData();
      form.append("company_name", companyName.trim());
      if (sources.pitchDeck.file) form.append("pitch_deck", sources.pitchDeck.file);
      if (sources.soc2.file) form.append("soc2_report", sources.soc2.file);
      if (sources.github.url.trim()) form.append("github_url", sources.github.url.trim());

      const resp = await fetch("/api/submissions", { method: "POST", body: form });
      if (!resp.ok) {
        const data = await resp.json().catch(() => null);
        throw new Error(data?.error || `Failed (${resp.status})`);
      }
      const data = await resp.json();
      router.push(`/submission/${data.submission_id}`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Submission failed");
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-6 py-10">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">New Submission</h1>
        <p className="mt-1 text-sm text-slate-500">
          Upload documents and provide sources for underwriting analysis.
        </p>
      </div>

      {/* Company Name */}
      <div className="mb-8">
        <label className="mb-2 block text-sm font-medium text-slate-700">Company Name</label>
        <input
          type="text"
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          placeholder="e.g., Coinbase, HealthPulse"
          className="w-full rounded-lg border border-slate-300 px-4 py-3 text-lg font-medium text-slate-900 placeholder-slate-400 transition-colors focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        />
      </div>

      {/* Source Cards */}
      <div className="mb-8 space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-500">Sources</h2>

        {/* Pitch Deck */}
        <SourceCard
          icon={<FileText className="h-5 w-5" />}
          title="Pitch Deck"
          description="Company pitch deck or investor presentation"
          status={sources.pitchDeck.status}
          detail={sources.pitchDeck.file ? `${sources.pitchDeck.file.name} (${(sources.pitchDeck.file.size / 1024).toFixed(0)} KB)` : undefined}
        >
          <div
            onClick={() => pitchRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handlePitchDeck(f); }}
            className="cursor-pointer rounded-lg border-2 border-dashed border-slate-300 px-4 py-6 text-center transition-colors hover:border-brand-400 hover:bg-brand-50/30"
          >
            <Upload className="mx-auto mb-2 h-6 w-6 text-slate-400" />
            <p className="text-sm text-slate-600">Drop PDF here or click to browse</p>
            <input ref={pitchRef} type="file" accept=".pdf" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) handlePitchDeck(f); e.target.value = ""; }} />
          </div>
        </SourceCard>

        {/* GitHub */}
        <SourceCard
          icon={<Github className="h-5 w-5" />}
          title="GitHub Repository"
          description="Public GitHub organization URL"
          status={sources.github.status}
          detail={sources.github.status === "ready" ? sources.github.url : undefined}
        >
          <input
            type="url"
            value={sources.github.url}
            onChange={(e) => handleGithubUrl(e.target.value)}
            placeholder="https://github.com/org-name"
            className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm text-slate-900 placeholder-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
          {sources.github.status === "entered" && sources.github.url.trim() && (
            <p className="mt-1 text-xs text-amber-600">Enter a valid GitHub URL (https://github.com/...)</p>
          )}
        </SourceCard>

        {/* SOC-2 */}
        <SourceCard
          icon={<ShieldCheck className="h-5 w-5" />}
          title="SOC-2 Report"
          description="SOC-2 Type II audit report"
          status={sources.soc2.status}
          detail={sources.soc2.file ? `${sources.soc2.file.name} (${(sources.soc2.file.size / 1024).toFixed(0)} KB)` : undefined}
        >
          <div
            onClick={() => soc2Ref.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) handleSoc2(f); }}
            className="cursor-pointer rounded-lg border-2 border-dashed border-slate-300 px-4 py-6 text-center transition-colors hover:border-brand-400 hover:bg-brand-50/30"
          >
            <Upload className="mx-auto mb-2 h-6 w-6 text-slate-400" />
            <p className="text-sm text-slate-600">Drop PDF here or click to browse</p>
            <input ref={soc2Ref} type="file" accept=".pdf" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) handleSoc2(f); e.target.value = ""; }} />
          </div>
        </SourceCard>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}

      <button onClick={handleSubmit} disabled={!canSubmit} className="btn-primary w-full text-base">
        {submitting ? (
          <>
            <Loader2 className="h-5 w-5 animate-spin" />
            Starting Analysis...
          </>
        ) : (
          <>
            Analyze
            <ArrowRight className="h-5 w-5" />
          </>
        )}
      </button>

      {!hasAnySrc && (
        <p className="mt-3 text-center text-xs text-slate-400">Provide at least one source to continue</p>
      )}
    </div>
  );
}

function SourceCard({
  icon, title, description, status, detail, children,
}: {
  icon: React.ReactNode; title: string; description: string;
  status: SourceStatus; detail?: string; children: React.ReactNode;
}) {
  const ready = status === "ready";
  return (
    <div className={`rounded-xl border bg-white p-5 shadow-sm transition-all ${ready ? "border-emerald-300 ring-1 ring-emerald-100" : "border-slate-200"}`}>
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`rounded-lg p-2 ${ready ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-500"}`}>
            {icon}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
            <p className="text-xs text-slate-500">{description}</p>
          </div>
        </div>
        {ready && <CheckCircle2 className="h-5 w-5 text-emerald-500" />}
      </div>
      {ready && detail ? (
        <div className="rounded-lg bg-emerald-50/50 px-3 py-2 text-sm text-emerald-700">{detail}</div>
      ) : (
        children
      )}
    </div>
  );
}
