<script lang="ts">
  import type { TraceDetail } from '$lib/state/types';
  import {
    formatDuration,
    formatCost,
    formatNumber,
    absoluteTime,
    relativeTime,
    finalStatusView,
  } from './trace_format';
  import SmartValue from './SmartValue.svelte';

  let { trace }: { trace: TraceDetail } = $props();

  const statusView = $derived(finalStatusView(trace.status));

  // Trace-level metadata — optional, chỉ render khi BE push (UI-007-REPLY-4).
  const metaEntries = $derived.by(() => {
    const m = trace.metadata;
    if (typeof m !== 'object' || m === null || Array.isArray(m)) return [];
    return Object.entries(m);
  });
</script>

<div class="space-y-4">
  <!-- Header: trace_id + status badge -->
  <div class="flex items-center justify-between gap-3 flex-wrap">
    <div class="min-w-0">
      <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-500">
        Trace ID
      </div>
      <div class="text-sm font-mono text-zinc-200 truncate">{trace.trace_id}</div>
    </div>
    <div class="flex items-center gap-2">
      <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg border {statusView.badgeClass} text-xs">
        <span class="text-base">{statusView.icon}</span>
        <span class="font-semibold">{statusView.label}</span>
      </span>
    </div>
  </div>

  <!-- Prompt -->
  <div class="rounded-lg bg-[#141416] border border-[#27272a] p-3">
    <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">
      Prompt
    </div>
    <p class="text-xs text-zinc-300 whitespace-pre-wrap leading-relaxed">{trace.prompt}</p>
  </div>

  <!-- Metrics grid -->
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
    <div class="rounded-lg bg-[#141416] border border-[#27272a] p-3">
      <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">
        Duration
      </div>
      <div class="text-lg font-mono text-zinc-200">{formatDuration(trace.duration_ms)}</div>
    </div>

    <div class="rounded-lg bg-[#141416] border border-[#27272a] p-3">
      <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">
        Tokens
      </div>
      <div class="text-lg font-mono text-zinc-200">{formatNumber(trace.total_tokens)}</div>
      <div class="text-[10px] font-mono text-zinc-500 mt-1 space-y-0.5">
        <div>in: {formatNumber(trace.input_tokens)}</div>
        <div>out: {formatNumber(trace.output_tokens)}</div>
        <div class="text-amber-400">reas: {formatNumber(trace.reasoning_tokens)}</div>
        <div class="text-sky-400">cache: {formatNumber(trace.cache_tokens)}</div>
      </div>
    </div>

    <div class="rounded-lg bg-[#141416] border border-[#27272a] p-3">
      <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">
        Cost
      </div>
      <div class="text-lg font-mono text-emerald-400">{formatCost(trace.cost)}</div>
    </div>

    <div class="rounded-lg bg-[#141416] border border-[#27272a] p-3">
      <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">
        Created
      </div>
      <div class="text-sm font-mono text-zinc-200" title={absoluteTime(trace.created_at)}>
        {relativeTime(trace.created_at)}
      </div>
      {#if trace.finished_at}
        <div class="text-[10px] font-mono text-zinc-500 mt-1" title={absoluteTime(trace.finished_at)}>
          finish: {relativeTime(trace.finished_at)}
        </div>
      {/if}
    </div>
  </div>

  <!-- Error banner -->
  {#if trace.status === "FAILED" && trace.error_message}
    <div class="rounded-lg bg-rose-500/10 border border-rose-500/40 p-3 flex items-start gap-2">
      <span class="text-rose-400 text-lg shrink-0">⚠</span>
      <div class="flex-1 min-w-0">
        <div class="text-rose-300 text-xs font-semibold mb-1">Lỗi pipeline</div>
        <div class="text-[11px] font-mono text-zinc-400 whitespace-pre-wrap break-words">
          {trace.error_message}
        </div>
      </div>
    </div>
  {:else if trace.status === "CANCELLED"}
    <div class="rounded-lg bg-zinc-500/10 border border-zinc-500/40 p-3 flex items-center gap-2">
      <span class="text-zinc-400 text-lg">⏹️</span>
      <span class="text-zinc-300 text-xs">Pipeline đã bị dừng bởi người dùng.</span>
    </div>
  {/if}

  <!-- Trace-level metadata — chỉ hiện khi BE push (UI-007-REPLY-4) -->
  {#if metaEntries.length > 0}
    <div class="space-y-2">
      <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-500 border-b border-[#1f1f23] pb-1">
        Metadata
      </div>
      <div class="space-y-2">
        {#each metaEntries as [key, val] (key)}
          <SmartValue label={key} value={val} />
        {/each}
      </div>
    </div>
  {/if}
</div>