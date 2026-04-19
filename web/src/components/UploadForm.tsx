"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, Loader2, AlertCircle } from "lucide-react";

interface UploadFormProps {
  onUploadComplete: (profileId: string) => void;
}

export default function UploadForm({ onUploadComplete }: UploadFormProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setError("Only PDF files are supported.");
        return;
      }
      if (file.size > 20 * 1024 * 1024) {
        setError("File is too large (max 20 MB).");
        return;
      }

      setError(null);
      setUploading(true);

      try {
        const form = new FormData();
        form.append("file", file);

        const resp = await fetch("/api/extract", {
          method: "POST",
          body: form,
        });

        if (!resp.ok) {
          const body = await resp.json().catch(() => null);
          throw new Error(body?.error ?? `Upload failed (${resp.status})`);
        }

        const data = await resp.json();
        onUploadComplete(data.id);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [onUploadComplete],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !uploading && inputRef.current?.click()}
        className={`
          flex cursor-pointer flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed
          px-6 py-16 text-center transition-all
          ${dragging ? "border-brand-400 bg-brand-50" : "border-slate-300 hover:border-brand-300 hover:bg-slate-50/50"}
          ${uploading ? "pointer-events-none" : ""}
        `}
      >
        {uploading ? (
          <>
            <Loader2 className="h-12 w-12 animate-spin text-brand-500" />
            <div>
              <p className="text-base font-semibold text-slate-800">
                Extracting risk fields...
              </p>
              <p className="mt-1 text-sm text-slate-500">
                GPT-4o is analyzing each page. This may take a minute.
              </p>
            </div>
          </>
        ) : (
          <>
            <Upload className="h-12 w-12 text-slate-400" />
            <div>
              <p className="text-base font-semibold text-slate-800">
                Upload a pitch deck to analyze
              </p>
              <p className="mt-1 text-sm text-slate-500">
                Drag and drop a PDF here, or click to browse
              </p>
            </div>
          </>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
          e.target.value = "";
        }}
      />

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          {error}
        </div>
      )}
    </div>
  );
}
