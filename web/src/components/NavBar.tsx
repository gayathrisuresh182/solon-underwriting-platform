"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Scale } from "lucide-react";
import StatusIndicator from "./StatusIndicator";

const TABS = [
  { href: "/submit", label: "New Submission" },
  { href: "/history", label: "History" },
  { href: "/metrics", label: "Metrics" },
];

export default function NavBar() {
  const pathname = usePathname();

  return (
    <nav className="sticky top-0 z-50 border-b border-slate-100 bg-white/95 backdrop-blur-lg">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Link href="/submit" className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500">
            <Scale className="h-4 w-4 text-white" />
          </div>
          <span className="text-lg font-bold text-navy-900">Solon</span>
        </Link>

        <div className="flex items-center gap-1">
          {TABS.map((tab) => {
            const active =
              pathname === tab.href ||
              pathname?.startsWith(tab.href + "/") ||
              (tab.href === "/submit" && pathname === "/");
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={`rounded-full px-4 py-2 text-sm font-medium transition-all duration-200 ${
                  active
                    ? "bg-navy-900 text-white"
                    : "text-navy-500 hover:text-navy-900"
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>

        <div className="flex items-center gap-2">
          <StatusIndicator />
        </div>
      </div>
    </nav>
  );
}
