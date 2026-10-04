<script lang="ts">
  // Metrics cuối phiên từ DoneEventData (UI-006).
  // 3 trạng thái: SUCCESS / FAILED / CANCELLED render khác nhau rõ ràng.
  //
  // Link "Xem trace" trỏ tới /traces/{trace_id}. Route này CHƯA tồn tại ở UI
  // (sẽ làm ở ticket sau). Dùng resolve() để tuân thủ lint rule của SvelteKit.

  import { resolve } from '$app/paths';
  import type { DoneEventData } from '$lib/state/types';
  import {
    resolveTerminalView,
    formatDuration,
    formatCost,
    formatNumber
  } from './terminal_status';

  let { done }: { done: DoneEventData } = $props();

  const view = $derived(resolveTerminalView(done.status));
  // Route /traces/{id} chưa tồn tại ở UI → click sẽ 404 tới khi có route.
  // Vẫn dùng resolve() để tránh base path mismatch khi deploy.
  const traceHref = $derived(resolve(`/traces/${done.trace_id}`));
</script>

<div class="w-full rounded-xl bg-[#141416] border border-[#27272a] overflow-hidden">
  <div class="px-3 py-2 border-b border-[#27272a] flex items-center justify-between gap-3">
    <div class="flex items-center gap-2">
      <span class="text-base">{view.icon}</span>
      <span class="text-xs font-semibold {view.textClass}">{view.label}</span>
    </div>

    {#if view.showCommit}
      <a
        href={traceHref}
        class="text-[10px] font-mono px-2 py-0.5 rounded border border-sky-500/40 text-sky-400 hover:bg-sky-500/10 transition-colors"
      >
        Xem trace →
      </a>
    {/if}
  </div>

  <div class="grid grid-cols-2 gap-x-4 gap-y-1.5 p-3 text-[11px] font-mono">
    <div class="flex items-center justify-between">
      <span class="text-zinc-500">Duration</span>
      <span class="text-zinc-200">{formatDuration(done.duration_ms)}</span>
    </div>
    <div class="flex items-center justify-between">
      <span class="text-zinc-500">Cost</span>
      <span class="text-emerald-400 font-semibold">{formatCost(done.cost)}</span>
    </div>
    <div class="flex items-center justify-between">
      <span class="text-zinc-500">Total</span>
      <span class="text-zinc-200">{formatNumber(done.total_tokens)}</span>
    </div>
    <div class="flex items-center justify-between">
      <span class="text-zinc-500">In / Out</span>
      <span class="text-zinc-200">
        {formatNumber(done.input_tokens)} / {formatNumber(done.output_tokens)}
      </span>
    </div>
    <div class="flex items-center justify-between">
      <span class="text-zinc-500">Reasoning</span>
      <span class="text-amber-400">{formatNumber(done.reasoning_tokens)}</span>
    </div>
    <div class="flex items-center justify-between">
      <span class="text-zinc-500">Cache</span>
      <span class="text-sky-400">{formatNumber(done.cache_tokens)}</span>
    </div>
  </div>
</div>