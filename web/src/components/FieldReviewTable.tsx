"use client";

import { useCallback, useState } from "react";
import type { DisplayField, RiskProfile, ConfidenceLevel } from "@/lib/types";
import {
  FIELD_CATEGORIES,
  FIELD_LABELS,
  confidenceToNumeric,
} from "@/lib/types";
import ConfidenceBadge from "./ConfidenceBadge";
import { ChevronDown, ChevronRight, AlertTriangle, Check, X } from "lucide-react";

function formatValue(value: string): string {
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) return parsed.join(", ");
  } catch {
    /* not JSON */
  }
  if (value === "true") return "Yes";
  if (value === "false") return "No";
  return value;
}

function buildDisplayFields(profile: RiskProfile): DisplayField[] {
  const fields = profile.extracted_fields ?? {};
  const confs = profile.confidence_scores ?? {};
  const cites = profile.source_citations ?? {};

  return Object.entries(fields).map(([key, value]) => {
    const category =
      Object.entries(FIELD_CATEGORIES).find(([, def]) =>
        def.fields.includes(key),
      )?.[0] ?? "other";
    const level = (confs[key] as ConfidenceLevel) ?? "medium";

    return {
      field_name: key,
      field_value: String(value),
      confidence: level,
      confidence_numeric: confidenceToNumeric(level),
      source: cites[key] ?? "",
      category,
    };
  });
}

interface FieldRowProps {
  field: DisplayField;
  profileId: string;
  onOverride: (fieldName: string, newValue: string) => void;
}

function FieldRow({ field, profileId, onOverride }: FieldRowProps) {
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const needsReview = field.confidence_numeric < 0.5;

  const startEdit = () => {
    setEditValue(formatValue(field.field_value));
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditValue("");
  };

  const saveEdit = async () => {
    if (editValue === formatValue(field.field_value)) {
      cancelEdit();
      return;
    }
    setSaving(true);
    try {
      const resp = await fetch("/api/profiles", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile_id: profileId,
          field_name: field.field_name,
          original_value: field.field_value,
          override_value: editValue,
        }),
      });
      if (resp.ok) {
        onOverride(field.field_name, editValue);
        setEditing(false);
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <tr
        className={`group transition-colors hover:bg-slate-50 ${
          needsReview ? "border-l-2 border-l-amber-400" : ""
        }`}
      >
        <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-900">
          <div className="flex items-center gap-2">
            {FIELD_LABELS[field.field_name] ?? field.field_name}
            {needsReview && (
              <span className="badge bg-amber-100 text-amber-700 ring-1 ring-inset ring-amber-600/20 text-[10px]">
                <AlertTriangle className="mr-0.5 h-3 w-3" />
                Review
              </span>
            )}
          </div>
        </td>
        <td className="px-4 py-3 text-slate-700">
          {editing ? (
            <div className="flex items-center gap-1.5">
              <input
                className="rounded border border-brand-300 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") saveEdit();
                  if (e.key === "Escape") cancelEdit();
                }}
                disabled={saving}
                autoFocus
              />
              <button
                onClick={saveEdit}
                disabled={saving}
                className="rounded p-1 text-emerald-600 hover:bg-emerald-50"
              >
                <Check className="h-3.5 w-3.5" />
              </button>
              <button
                onClick={cancelEdit}
                className="rounded p-1 text-slate-400 hover:bg-slate-100"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ) : (
            <button
              onClick={startEdit}
              className="rounded px-1 py-0.5 text-left transition-colors hover:bg-brand-50 hover:text-brand-700"
              title="Click to override"
            >
              {formatValue(field.field_value)}
            </button>
          )}
        </td>
        <td className="px-4 py-3 text-center">
          <ConfidenceBadge value={field.confidence_numeric} />
        </td>
        <td className="px-4 py-3">
          {field.source && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
            >
              {expanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              {expanded ? "Hide" : "Show"}
            </button>
          )}
        </td>
      </tr>
      {expanded && field.source && (
        <tr className="bg-slate-50/50">
          <td colSpan={4} className="px-4 py-2">
            <p className="text-xs italic text-slate-500">
              &ldquo;{field.source}&rdquo;
            </p>
          </td>
        </tr>
      )}
    </>
  );
}

interface FieldReviewTableProps {
  profile: RiskProfile;
  onFieldOverride?: (fieldName: string, newValue: string) => void;
}

export default function FieldReviewTable({
  profile,
  onFieldOverride,
}: FieldReviewTableProps) {
  const [localOverrides, setLocalOverrides] = useState<
    Record<string, string>
  >({});

  const displayFields = buildDisplayFields(profile);

  const handleOverride = useCallback(
    (fieldName: string, newValue: string) => {
      setLocalOverrides((prev) => ({ ...prev, [fieldName]: newValue }));
      onFieldOverride?.(fieldName, newValue);
    },
    [onFieldOverride],
  );

  const effectiveFields = displayFields.map((f) =>
    localOverrides[f.field_name]
      ? { ...f, field_value: localOverrides[f.field_name] }
      : f,
  );

  const grouped = effectiveFields.reduce<Record<string, DisplayField[]>>(
    (acc, f) => {
      (acc[f.category] ??= []).push(f);
      return acc;
    },
    {},
  );

  const categoryOrder = [...Object.keys(FIELD_CATEGORIES), "other"];
  const categories = categoryOrder.filter((c) => grouped[c]?.length);

  if (effectiveFields.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">
        No fields extracted yet.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {categories.map((cat) => (
        <div key={cat}>
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            {FIELD_CATEGORIES[cat]?.label ?? "Other"}
          </h3>
          <div className="overflow-hidden rounded-lg border border-slate-200">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-2.5 text-left font-medium text-slate-600">
                    Field
                  </th>
                  <th className="px-4 py-2.5 text-left font-medium text-slate-600">
                    Value
                  </th>
                  <th className="px-4 py-2.5 text-center font-medium text-slate-600">
                    Confidence
                  </th>
                  <th className="w-20 px-4 py-2.5 text-left font-medium text-slate-600">
                    Source
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {grouped[cat].map((f) => (
                  <FieldRow
                    key={f.field_name}
                    field={f}
                    profileId={profile.id}
                    onOverride={handleOverride}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
