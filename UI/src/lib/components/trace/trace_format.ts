// src/lib/components/trace/trace_format.ts
//
// Helper format cho trace dashboard.
// Không cài dayjs/date-fns — logic < 30 dòng, tự viết (rule #1).

import type { FinalStatus, SpanType, SpanStatus } from "$lib/state/types";

// ============================================================
// Relative time — "2m ago", "1h ago", "3d ago"
// ============================================================

export function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return iso;

  const diff = Math.max(0, Date.now() - then);
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;

  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;

  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;

  const day = Math.floor(hr / 24);
  return `${day}d ago`;
}

export function absoluteTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

// ============================================================
// Duration — "890ms", "12.6s", "1m 30s"
// ============================================================

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const min = Math.floor(sec / 60);
  const rem = Math.floor(sec % 60);
  return `${min}m ${rem}s`;
}

// ============================================================
// Cost
// ============================================================

export function formatCost(usd: number): string {
  if (usd === 0) return "$0";
  return `$${usd.toFixed(4)}`;
}

// ============================================================
// Number
// ============================================================

export function formatNumber(n: number): string {
  return n.toLocaleString();
}

// ============================================================
// Status view models
// ============================================================

export interface StatusView {
  icon: string;
  label: string;
  badgeClass: string;
  textClass: string;
  dotClass: string;
}

export function finalStatusView(status: FinalStatus): StatusView {
  switch (status) {
    case "SUCCESS":
      return {
        icon: "✅",
        label: "Thành công",
        badgeClass: "bg-emerald-500/10 border-emerald-500/40 text-emerald-400",
        textClass: "text-emerald-400",
        dotClass: "bg-emerald-500",
      };
    case "FAILED":
      return {
        icon: "❌",
        label: "Thất bại",
        badgeClass: "bg-rose-500/10 border-rose-500/40 text-rose-400",
        textClass: "text-rose-400",
        dotClass: "bg-rose-500",
      };
    case "CANCELLED":
      return {
        icon: "⏹️",
        label: "Đã dừng",
        badgeClass: "bg-zinc-500/10 border-zinc-500/40 text-zinc-400",
        textClass: "text-zinc-400",
        dotClass: "bg-zinc-500",
      };
    default: {
      const _exhaustive: never = status;
      void _exhaustive;
      return {
        icon: "•",
        label: "Không xác định",
        badgeClass: "bg-zinc-500/10 border-zinc-500/40 text-zinc-400",
        textClass: "text-zinc-400",
        dotClass: "bg-zinc-500",
      };
    }
  }
}

// ============================================================
// Span type view models
// ============================================================

export interface SpanTypeView {
  icon: string;
  label: string;
  colorClass: string;
}

export function spanTypeView(type: SpanType): SpanTypeView {
  switch (type) {
    case "llm":
      return { icon: "🤖", label: "LLM", colorClass: "text-sky-400" };
    case "tool":
      return { icon: "🔧", label: "Tool", colorClass: "text-amber-400" };
    case "sandbox":
      return { icon: "📦", label: "Sandbox", colorClass: "text-purple-400" };
    case "git":
      return { icon: "🌿", label: "Git", colorClass: "text-emerald-400" };
    case "internal":
      // Q6 UI-001-REPLY: reserved, chưa emit. Icon trung tính.
      return { icon: "⚙️", label: "Internal", colorClass: "text-zinc-400" };
    default: {
      const _exhaustive: never = type;
      void _exhaustive;
      return { icon: "•", label: "Unknown", colorClass: "text-zinc-400" };
    }
  }
}

export function spanStatusView(status: SpanStatus): {
  label: string;
  badgeClass: string;
} {
  switch (status) {
    case "OK":
      return {
        label: "OK",
        badgeClass: "bg-emerald-500/10 border-emerald-500/40 text-emerald-400",
      };
    case "ERROR":
      return {
        label: "ERROR",
        badgeClass: "bg-rose-500/10 border-rose-500/40 text-rose-400",
      };
    default: {
      const _exhaustive: never = status;
      void _exhaustive;
      return {
        label: "?",
        badgeClass: "bg-zinc-500/10 border-zinc-500/40 text-zinc-400",
      };
    }
  }
}