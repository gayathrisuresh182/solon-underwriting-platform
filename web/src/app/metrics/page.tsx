"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
  LineChart, Line,
} from "recharts";

const PIE_COLORS = ["#22c55e", "#f59e0b", "#ef4444"];

export default function MetricsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/metrics")
      .then((r) => r.json())
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-brand-500" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-5xl px-6 py-8">
        <div className="rounded-lg bg-red-50 p-6 text-center text-red-700">Failed to load metrics</div>
      </div>
    );
  }

  const totalDecided = data.auto_bind_count + data.review_count + data.decline_count;
  const autoBindRate = totalDecided > 0 ? Math.round((data.auto_bind_count / totalDecided) * 100) : 0;

  const pieData = [
    { name: "Auto-bind", value: data.auto_bind_count },
    { name: "Human Review", value: data.review_count },
    { name: "Decline", value: data.decline_count },
  ].filter((d) => d.value > 0);

  const distData = (data.risk_distribution || []).map((d: any) => ({
    bucket: d.bucket,
    count: parseInt(d.count),
  }));

  const timelineData = (data.timeline || []).map((d: any) => ({
    date: new Date(d.date).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    count: parseInt(d.count),
  }));

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <h1 className="mb-6 text-2xl font-bold text-slate-900">Metrics Dashboard</h1>

      {/* Summary Cards */}
      <div className="mb-8 grid grid-cols-4 gap-4">
        <SummaryCard label="Total Submissions" value={data.total_submissions} />
        <SummaryCard
          label="Avg Risk Score"
          value={data.avg_risk_score != null ? Math.round(data.avg_risk_score) : "—"}
          color={
            data.avg_risk_score != null
              ? data.avg_risk_score < 40 ? "text-emerald-600" : data.avg_risk_score < 70 ? "text-amber-500" : "text-red-500"
              : undefined
          }
        />
        <SummaryCard label="Auto-Bind Rate" value={totalDecided > 0 ? `${autoBindRate}%` : "—"} />
        <SummaryCard label="Total Decided" value={totalDecided || "—"} />
      </div>

      {/* Charts */}
      <div className="mb-8 grid grid-cols-2 gap-6">
        {/* Risk Distribution */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Risk Score Distribution</h3>
          {distData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={distData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="bucket" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#4c6ef5" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-60 items-center justify-center text-sm text-slate-400">No data yet</div>
          )}
        </div>

        {/* Decision Distribution */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Decision Distribution</h3>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={2} dataKey="value" label={({ name, value }) => `${name}: ${value}`}>
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-60 items-center justify-center text-sm text-slate-400">No data yet</div>
          )}
        </div>
      </div>

      {/* Submissions Timeline */}
      <div className="mb-8 rounded-xl border border-slate-200 bg-white p-5">
        <h3 className="mb-4 text-sm font-semibold text-slate-700">Submissions Over Time</h3>
        {timelineData.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={timelineData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey="count" stroke="#4c6ef5" strokeWidth={2} dot={{ fill: "#4c6ef5", r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-48 items-center justify-center text-sm text-slate-400">No data yet</div>
        )}
      </div>

      {/* Top Rules */}
      {data.top_rules?.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h3 className="mb-4 text-sm font-semibold text-slate-700">Top Rules Fired</h3>
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium text-slate-600">Rule ID</th>
                  <th className="px-4 py-2.5 text-right font-medium text-slate-600">Times Fired</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.top_rules.map((r: any) => (
                  <tr key={r.rule_id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5 font-medium text-slate-900">{r.rule_id}</td>
                    <td className="px-4 py-2.5 text-right text-slate-600">{r.fire_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-xs font-medium uppercase tracking-wider text-slate-500">{label}</p>
      <p className={`mt-1 text-2xl font-bold ${color || "text-slate-900"}`}>{value}</p>
    </div>
  );
}
