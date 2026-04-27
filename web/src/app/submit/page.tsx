"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Upload, Github, ShieldCheck, FileText, CheckCircle2,
  Loader2, AlertCircle, ArrowRight, X,
} from "lucide-react";

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
  const readySources = [sources.pitchDeck.status, sources.github.status, sources.soc2.status].filter(s => s === "ready").length;

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
    setSources((s) => ({
      ...s,
      github: { url, status: url.trim() ? (valid ? "ready" : "entered") : "empty" },
    }));
  }, []);

  const clearPitchDeck = useCallback(() => {
    setSources((s) => ({ ...s, pitchDeck: { file: null, status: "empty" } }));
  }, []);

  const clearSoc2 = useCallback(() => {
    setSources((s) => ({ ...s, soc2: { file: null, status: "empty" } }));
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
    <div className="mx-auto max-w-2xl px-6 py-12">
      <div className="mb-10">
        <h1 className="text-3xl font-bold text-navy-900">New Submission</h1>
        <p className="mt-2 text-base text-slate-500">
          Provide company details and upload documents for AI-powered risk assessment.
        </p>
      </div>

      <div className="mb-10">
        <label className="mb-2 block text-sm font-semibold text-navy-800">
          Company Name
        </label>
        <input
          type="text"
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
          placeholder="e.g., Coinbase, Stripe, HealthPulse"
          className="input-field text-lg font-medium"
        />
      </div>

      <div className="mb-10 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="section-title">Data Sources</h2>
          {readySources > 0 && (
            <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-semibold text-brand-700">
              {readySources} of 3 ready
            </span>
          )}
        </div>

        <SourceCard
          icon={<FileText className="h-5 w-5" />}
          title="Pitch Deck"
          description="Investor presentation or company overview PDF"
          status={sources.pitchDeck.status}
          detail={sources.pitchDeck.file?.name}
          fileSize={sources.pitchDeck.file?.size}
          onClear={clearPitchDeck}
        >
          <DropZone
            inputRef={pitchRef}
            onFile={handlePitchDeck}
            label="Drop your pitch deck here, or click to browse"
          />
        </SourceCard>

        <SourceCard
          icon={<Github className="h-5 w-5" />}
          title="GitHub Organization"
          description="Public GitHub organization URL for code analysis"
          status={sources.github.status}
          detail={sources.github.status === "ready" ? sources.github.url : undefined}
        >
          <input
            type="url"
            value={sources.github.url}
            onChange={(e) => handleGithubUrl(e.target.value)}
            placeholder="https://github.com/org-name"
            className="input-field"
          />
          {sources.github.status === "entered" && sources.github.url.trim() && (
            <p className="mt-2 text-xs text-amber-600">Please enter a valid GitHub URL</p>
          )}
        </SourceCard>

        <SourceCard
          icon={<ShieldCheck className="h-5 w-5" />}
          title="SOC-2 Report"
          description="SOC-2 Type II audit report PDF"
          status={sources.soc2.status}
          detail={sources.soc2.file?.name}
          fileSize={sources.soc2.file?.size}
          onClear={clearSoc2}
        >
          <DropZone
            inputRef={soc2Ref}
            onFile={handleSoc2}
            label="Drop your SOC-2 report here, or click to browse"
          />
        </SourceCard>
      </div>

      {error && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <button onClick={handleSubmit} disabled={!canSubmit} className="btn-primary w-full py-4 text-base">
        {submitting ? (
          <>
            <Loader2 className="h-5 w-5 animate-spin" />
            Starting Analysis...
          </>
        ) : (
          <>
            Start Risk Analysis
            <ArrowRight className="h-5 w-5" />
          </>
        )}
      </button>

      {!hasAnySrc && (
        <p className="mt-4 text-center text-sm text-slate-400">
          Provide at least one data source to continue
        </p>
      )}
    </div>
  );
}

function SourceCard({
  icon, title, description, status, detail, fileSize, onClear, children,
}: {
  icon: React.ReactNode; title: string; description: string;
  status: SourceStatus; detail?: string; fileSize?: number;
  onClear?: () => void; children: React.ReactNode;
}) {
  const ready = status === "ready";
  return (
    <div className={`rounded-2xl border bg-white p-5 transition-all duration-200 ${
      ready
        ? "border-brand-200 shadow-card"
        : "border-slate-200/80 shadow-card hover:shadow-card-hover"
    }`}>
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${
            ready ? "bg-brand-50 text-brand-600" : "bg-slate-50 text-slate-400"
          }`}>
            {icon}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-navy-900">{title}</h3>
            <p className="text-xs text-slate-400">{description}</p>
          </div>
        </div>
        {ready && (
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-5 w-5 text-brand-500" />
            {onClear && (
              <button
                onClick={onClear}
                className="rounded-lg p-1 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        )}
      </div>
      {ready && detail ? (
        <div className="rounded-xl bg-brand-50/60 px-4 py-3">
          <p className="text-sm font-medium text-brand-800">{detail}</p>
          {fileSize && (
            <p className="mt-0.5 text-xs text-brand-600">
              {(fileSize / 1024).toFixed(0)} KB
            </p>
          )}
        </div>
      ) : (
        children
      )}
    </div>
  );
}

function DropZone({
  inputRef, onFile, label,
}: {
  inputRef: React.RefObject<HTMLInputElement>;
  onFile: (f: File) => void;
  label: string;
}) {
  const [dragging, setDragging] = useState(false);

  return (
    <div
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files[0];
        if (f) onFile(f);
      }}
      className={`cursor-pointer rounded-xl border-2 border-dashed px-4 py-8 text-center transition-all duration-200 ${
        dragging
          ? "border-brand-400 bg-brand-50/40"
          : "border-slate-200 hover:border-brand-300 hover:bg-slate-50/50"
      }`}
    >
      <Upload className={`mx-auto mb-3 h-8 w-8 ${dragging ? "text-brand-500" : "text-slate-300"}`} />
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-1 text-xs text-slate-400">PDF files only</p>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
          e.target.value = "";
        }}
      />
    </div>
  );
}
