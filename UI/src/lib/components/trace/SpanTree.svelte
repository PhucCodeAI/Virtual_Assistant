<script lang="ts">
  import type { SpanDTO } from '$lib/state/types';
  import { formatDuration, spanTypeView, spanStatusView } from './trace_format';

  let {
    spans,
    selectedSpanId,
    onSelect,
  }: {
    spans: SpanDTO[];
    selectedSpanId: string | null;
    onSelect: (spanId: string) => void;
  } = $props();
</script>

{#if spans.length === 0}
  <div class="p-8 text-center text-xs text-zinc-400">Trace không có span nào.</div>
{:else}
  <div class="divide-y divide-[#27272a]">
    {#each spans as span (span.span_id)}
      {@const tv = spanTypeView(span.span_type)}
      {@const sv = spanStatusView(span.status)}
      <button
        type="button"
        onclick={() => onSelect(span.span_id)}
        class="w-full flex items-center gap-2.5 px-3 py-2.5 text-left font-mono text-[12px] transition-colors
               {selectedSpanId === span.span_id
                 ? 'bg-amber-500/15 border-l-2 border-amber-400'
                 : 'border-l-2 border-transparent hover:bg-[#18181b]'}"
      >
        <span class="shrink-0 text-base {tv.colorClass}">{tv.icon}</span>
        <span class="flex-1 truncate text-zinc-100 font-medium">{span.name}</span>
        <span class="shrink-0 text-zinc-400">{formatDuration(span.duration_ms)}</span>
        <span class="shrink-0 px-1.5 py-0.5 rounded border text-[10px] font-bold {sv.badgeClass}">
          {sv.label}
        </span>
      </button>
    {/each}
  </div>
{/if}