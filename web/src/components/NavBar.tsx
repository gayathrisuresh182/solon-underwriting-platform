"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import StatusIndicator from "./StatusIndicator";

const TABS = [
  { href: "/submit", label: "New Submission" },
  { href: "/history", label: "History" },
  { href: "/metrics", label: "Metrics" },
];

export default function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 border-b border-slate-200 bg-white/90 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
        <Link href="/submit" className="text-lg font-bold tracking-tight text-slate-900">
          Hammurabi
        </Link>

        <div className="flex items-center gap-1">
          {TABS.map((tab) => {
            const active = pathname === tab.href || (tab.href === "/submit" && pathname === "/");
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                  active
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400">System</span>
          <StatusIndicator />
        </div>
      </div>
    </nav>
  );
}
