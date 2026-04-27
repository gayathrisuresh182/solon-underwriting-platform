"use client";

import { useEffect, useState } from "react";
import { Loader2, TrendingUp, Shield, Zap, BarChart3 } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell,
  LineChart, Line,
} from "recharts";

const PIE_COLORS = ["#f97316", "#f59e0b", "#ef4444"];
const CHART_ORANGE = "#f97316";

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
        <div className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center text-red-700">Failed to load metrics</div>
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
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-navy-900">Metrics</h1>
        <p className="mt-1 text-sm text-slate-400">Overview of underwriting pipeline performance</p>
      </div>

      <div className="mb-8 grid grid-cols-4 gap-4">
        <SummaryCard
          icon={<BarChart3 className="h-5 w-5 text-brand-500" />}
          label="Total Submissions"
          value={data.total_submissions}
        />
        <SummaryCard
          icon={<Shield className="h-5 w-5 text-amber-500" />}
          label="Avg Risk Score"
          value={data.avg_risk_score != null ? Math.round(data.avg_risk_score) : "\u2014"}
          valueColor={
            data.avg_risk_score != null
              ? data.avg_risk_score < 40 ? "text-brand-600" : data.avg_risk_score < 70 ? "text-amber-500" : "text-red-500"
              : undefined
          }
        />
        <SummaryCard
          icon={<Zap className="h-5 w-5 text-brand-500" />}
          label="Auto-Bind Rate"
          value={totalDecided > 0 ? `${autoBindRate}%` : "\u2014"}
        />
        <SummaryCard
          icon={<TrendingUp className="h-5 w-5 text-blue-500" />}
          label="Total Decided"
          value={totalDecided || "\u2014"}
        />
      </div>

      <div className="mb-8 grid grid-cols-2 gap-6">
        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
          <h3 className="mb-5 text-sm font-semibold text-navy-900">Risk Score Distribution</h3>
          {distData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={distData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#94a3b8" }} />
                <Tooltip
                  contentStyle={{
                    borderRadius: 12, border: "1px solid #e2e8f0",
                    boxShadow: "0 4px 12px rgb(0 0 0 / 0.06)", fontSize: 12,
                  }}
                />
                <Bar dataKey="count" fill={CHART_ORANGE} radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart />
          )}
        </div>

        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
          <h3 className="mb-5 text-sm font-semibold text-navy-900">Decision Distribution</h3>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie
                  data={pieData} cx="50%" cy="50%"
                  innerRadius={65} outerRadius={95} paddingAngle={3}
                  dataKey="value" strokeWidth={0}
                  label={({ name, value }) => `${name}: ${value}`}
                >
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    borderRadius: 12, border: "1px solid #e2e8f0",
                    boxShadow: "0 4px 12px rgb(0 0 0 / 0.06)", fontSize: 12,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <EmptyChart />
          )}
        </div>
      </div>

      <div className="mb-8 rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
        <h3 className="mb-5 text-sm font-semibold text-navy-900">Submissions Over Time</h3>
        {timelineData.length > 0 ? (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={timelineData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#94a3b8" }} />
              <Tooltip
                contentStyle={{
                  borderRadius: 12, border: "1px solid #e2e8f0",
                  boxShadow: "0 4px 12px rgb(0 0 0 / 0.06)", fontSize: 12,
                }}
              />
                <Line
                type="monotone" dataKey="count" stroke={CHART_ORANGE} strokeWidth={2.5}
                dot={{ fill: CHART_ORANGE, r: 4, strokeWidth: 0 }}
                activeDot={{ fill: CHART_ORANGE, r: 6, strokeWidth: 2, stroke: "#fff" }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <EmptyChart height="h-48" />
        )}
      </div>

      {data.top_rules?.length > 0 && (
        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card">
          <h3 className="mb-5 text-sm font-semibold text-navy-900">Top Rules Fired</h3>
          <div className="overflow-hidden rounded-xl border border-slate-200/80">
            <table className="min-w-full divide-y divide-slate-100 text-sm">
              <thead>
                <tr className="bg-slate-50/80">
                  <th className="px-5 py-3 text-left text-xs font-semibold text-slate-500">Rule ID</th>
                  <th className="px-5 py-3 text-right text-xs font-semibold text-slate-500">Times Fired</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.top_rules.map((r: any) => (
                  <tr key={r.rule_id} className="hover:bg-slate-50/60">
                    <td className="px-5 py-3 font-medium text-navy-900">{r.rule_id}</td>
                    <td className="px-5 py-3 text-right">
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                        {r.fire_count}
                      </span>
                    </td>
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

function SummaryCard({ icon, label, value, valueColor }: {
  icon: React.ReactNode; label: string; value: string | number; valueColor?: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-card">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-slate-50">
        {icon}
      </div>
      <p className="text-xs font-medium text-slate-400">{label}</p>
      <p className={`mt-1 text-3xl font-bold ${valueColor || "text-navy-900"}`}>{value}</p>
    </div>
  );
}

function EmptyChart({ height = "h-60" }: { height?: string }) {
  return (
    <div className={`flex ${height} items-center justify-center`}>
      <p className="text-sm text-slate-300">No data yet</p>
    </div>
  );
}
