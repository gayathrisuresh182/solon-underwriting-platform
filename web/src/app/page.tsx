"use client";

import { useCallback, useEffect, useState } from "react";
import type { RiskProfile } from "@/lib/types";
import UploadForm from "@/components/UploadForm";
import RiskProfileCard from "@/components/RiskProfileCard";
import FieldReviewTable from "@/components/FieldReviewTable";
import { Clock, FileText } from "lucide-react";

export default function Home() {
  const [profiles, setProfiles] = useState<RiskProfile[]>([]);
  const [selected, setSelected] = useState<RiskProfile | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchProfiles = useCallback(async () => {
    try {
      const res = await fetch("/api/profiles");
      if (res.ok) setProfiles(await res.json());
    } catch {
      /* db may not be ready */
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchDetail = useCallback(async (id: string) => {
    try {
      const res = await fetch(`/api/profiles?id=${id}`);
      if (res.ok) setSelected(await res.json());
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    fetchProfiles();
  }, [fetchProfiles]);

  const handleUploadComplete = useCallback(
    (profileId: string) => {
      fetchProfiles();
      fetchDetail(profileId);
    },
    [fetchProfiles, fetchDetail],
  );

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="grid gap-8 lg:grid-cols-[1fr_280px]">
        {/* ── Main column ── */}
        <div className="space-y-8">
          {/* Section 1: Upload */}
          <section>
            <UploadForm onUploadComplete={handleUploadComplete} />
          </section>

          {/* Section 2: Results (shown after extraction) */}
          {selected && (
            <section className="space-y-6">
              <RiskProfileCard profile={selected} />
              <FieldReviewTable
                profile={selected}
                onFieldOverride={() => fetchDetail(selected.id)}
              />
            </section>
          )}
        </div>

        {/* ── History sidebar ── */}
        <aside>
          <div className="sticky top-20">
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Clock className="h-4 w-4 text-slate-400" />
              History
            </h2>
            {loading ? (
              <p className="text-xs text-slate-400">Loading...</p>
            ) : profiles.length === 0 ? (
              <p className="text-xs text-slate-400">No profiles yet</p>
            ) : (
              <ul className="space-y-1">
                {profiles.map((p) => (
                  <li key={p.id}>
                    <button
                      onClick={() => fetchDetail(p.id)}
                      className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${
                        selected?.id === p.id
                          ? "bg-brand-50 ring-1 ring-brand-200"
                          : "hover:bg-slate-100"
                      }`}
                    >
                      <FileText className="h-4 w-4 flex-shrink-0 text-slate-400" />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-slate-900">
                          {p.company_name}
                        </p>
                        <p className="text-[11px] text-slate-400">
                          {new Date(p.created_at).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                          })}
                          {p.risk_score !== null && (
                            <span
                              className={`ml-2 font-semibold ${
                                p.risk_score < 40
                                  ? "text-emerald-600"
                                  : p.risk_score < 70
                                    ? "text-amber-500"
                                    : "text-red-500"
                              }`}
                            >
                              {p.risk_score}
                            </span>
                          )}
                        </p>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
