"use client";

import { useEffect, useState } from "react";

export default function StatusIndicator({ endpoint = "/api/health" }: { endpoint?: string }) {
  const [ok, setOk] = useState<boolean | null>(null);

  useEffect(() => {
    let mounted = true;

    async function ping() {
      try {
        const res = await fetch(endpoint, { cache: "no-store" });
        if (mounted) setOk(res.ok);
      } catch {
        if (mounted) setOk(false);
      }
    }

    ping();
    const id = setInterval(ping, 30_000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, [endpoint]);

  if (ok === null) {
    return (
      <span className="relative flex h-2.5 w-2.5">
        <span className="h-2.5 w-2.5 rounded-full bg-slate-300" />
      </span>
    );
  }

  return (
    <span className="relative flex h-2.5 w-2.5" title={ok ? "Services healthy" : "Services degraded"}>
      <span
        className={`absolute inline-flex h-full w-full animate-ping rounded-full opacity-75 ${
          ok ? "bg-emerald-400" : "bg-red-400"
        }`}
      />
      <span
        className={`relative inline-flex h-2.5 w-2.5 rounded-full ${
          ok ? "bg-emerald-500" : "bg-red-500"
        }`}
      />
    </span>
  );
}
