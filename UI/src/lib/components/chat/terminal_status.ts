// src/lib/components/chat/terminal_status.ts
//
// Mapping FinalStatus → view model cho terminal badge.
// Dùng chung ở Chat, DoneMetrics, và bất kỳ chỗ nào hiển thị kết quả phiên.
//
// Icon + label theo UI-001-REPLY Q2:
//   SUCCESS   → ✅ xanh, hiện commit link
//   FAILED    → ❌ đỏ, ẩn commit link
//   CANCELLED → ⏹️ xám, ẩn commit link

import type { FinalStatus } from "$lib/state/types";

export interface TerminalView {
  icon: string;
  label: string;
  /** Tailwind classes cho badge container. */
  badgeClass: string;
  /** Tailwind class cho text/icon đơn sắc. */
  textClass: string;
  /** Quyết định có hiện link commit không. */
  showCommit: boolean;
}

export function resolveTerminalView(status: FinalStatus): TerminalView {
  switch (status) {
    case "SUCCESS":
      return {
        icon: "✅",
        label: "Thành công",
        badgeClass: "bg-emerald-500/10 border-emerald-500/40 text-emerald-400",
        textClass: "text-emerald-400",
        showCommit: true,
      };
    case "FAILED":
      return {
        icon: "❌",
        label: "Thất bại",
        badgeClass: "bg-rose-500/10 border-rose-500/40 text-rose-400",
        textClass: "text-rose-400",
        showCommit: false,
      };
    case "CANCELLED":
      return {
        icon: "⏹️",
        label: "Đã dừng bởi người dùng",
        badgeClass: "bg-zinc-500/10 border-zinc-500/40 text-zinc-400",
        textClass: "text-zinc-400",
        showCommit: false,
      };
    default: {
      const _exhaustive: never = status;
      void _exhaustive;
      // Fallback an toàn — không nên chạm tới vì union đã covered.
      return {
        icon: "•",
        label: "Không xác định",
        badgeClass: "bg-zinc-500/10 border-zinc-500/40 text-zinc-400",
        textClass: "text-zinc-400",
        showCommit: false,
      };
    }
  }
}

/** Format duration_ms → "5.2s" hoặc "1m 12s". */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const totalSec = ms / 1000;
  if (totalSec < 60) return `${totalSec.toFixed(1)}s`;
  const min = Math.floor(totalSec / 60);
  const sec = Math.floor(totalSec % 60);
  return `${min}m ${sec}s`;
}

/** Format cost với 4 chữ số thập phân. */
export function formatCost(usd: number): string {
  return `$${usd.toFixed(4)}`;
}

/** Format số nguyên với dấu phân cách nghìn. */
export function formatNumber(n: number): string {
  return n.toLocaleString();
}