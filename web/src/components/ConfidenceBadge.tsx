"use client";

function colorClass(value: number): string {
  if (value >= 0.8) return "bg-emerald-100 text-emerald-800 ring-emerald-600/20";
  if (value >= 0.5) return "bg-amber-100 text-amber-800 ring-amber-600/20";
  return "bg-red-100 text-red-800 ring-red-600/20";
}

export default function ConfidenceBadge({ value }: { value: number }) {
  return (
    <span
      className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${colorClass(value)}`}
    >
      {Math.round(value * 100)}%
    </span>
  );
}
