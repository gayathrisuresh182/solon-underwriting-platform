import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import StatusIndicator from "@/components/StatusIndicator";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Hammurabi — Startup Risk Engine",
  description: "AI-powered underwriting engine for startup pitch deck analysis",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <nav className="sticky top-0 z-50 border-b border-slate-200 bg-white/80 backdrop-blur-md">
          <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-6">
            <span className="text-lg font-bold tracking-tight text-slate-900">
              Hammurabi
            </span>
            <StatusIndicator />
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
