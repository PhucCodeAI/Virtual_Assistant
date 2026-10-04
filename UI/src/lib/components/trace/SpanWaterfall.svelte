<script lang="ts">
  // Waterfall: mỗi span là 1 thanh bar, vị trí & độ dài theo thời gian.
  //
  // BE push start_offset_ms 2026-10-05 (UI-007-REPLY-7). Field có default=0
  // → nếu BE chưa populate orchestrator, mọi span có value 0 → fallback
  // sequential (cộng dồn duration) để không chồng chữ nhật.
  //
  // Heuristic: nếu có >=1 span start_offset_ms > 0 → tin BE.
  //            Ngược lại → sequential.

  import type { SpanDTO } from '$lib/state/types';
  import { spanTypeView, spanStatusView } from './trace_format';

  let {
    spans,
    totalDurationMs,
    selectedSpanId,
    onSelect,
  }: {
    spans: SpanDTO[];
    totalDurationMs: number;
    selectedSpanId: string | null;
    onSelect: (spanId: string) => void;
  } = $props();

  // Detect BE đã populate start_offset_ms chưa.
  const bePopulated = $derived(
    spans.length > 1 && spans.some((s) => s.start_offset_ms > 0),
  );

  function computeOffsets(list: SpanDTO[]): { span: SpanDTO; offset: number }[] {
    let acc = 0;
    return list.map((span) => {
      const offset = bePopulated ? span.start_offset_ms : acc;
      acc = offset + span.duration_ms;
      return { span, offset };
    });
  }

  const offsets = $derived(computeOffsets(spans));

  const maxMs = $derived.by(() => {
    if (totalDurationMs > 0) return totalDurationMs;
    const last = offsets.reduce(
      (m, o) => Math.max(m, o.offset + o.span.duration_ms),
      0,
    );
    return last > 0 ? last : 1;
  });
</script>

{#if spans.length === 0}
  <div class="p-8 text-center text-xs text-zinc-400">Trace không có span nào.</div>
{:else}
  <div class="p-2 space-y-1">
    {#each offsets as { span, offset } (span.span_id)}
      {@const tv = spanTypeView(span.span_type)}
      {@const sv = spanStatusView(span.status)}
      {@const leftPct = (offset / maxMs) * 100}
      {@const widthPct = Math.max(0.8, (span.duration_ms / maxMs) * 100)}
      {@const isError = span.status === 'ERROR'}
      <button
        type="button"
        onclick={() => onSelect(span.span_id)}
        class="relative w-full h-9 rounded transition-colors group
               {selectedSpanId === span.span_id ? 'ring-1 ring-amber-400/60' : ''}"
        title="{span.name} · {span.duration_ms}ms · offset {offset}ms"
      >
        <!-- Bar -->
        <div
          class="absolute top-1.5 bottom-1.5 rounded-sm transition-all
                 {isError
                   ? 'bg-rose-500/60 group-hover:bg-rose-500/80'
                   : 'bg-sky-500/55 group-hover:bg-sky-500/75'}"
          style="left: {leftPct}%; width: {widthPct}%;"
        ></div>

        <!-- Labels overlay -->
        <div class="absolute inset-0 flex items-center px-2 gap-2 text-[11px] font-mono pointer-events-none">
          <span class="shrink-0 text-base {tv.colorClass}">{tv.icon}</span>
          <span class="shrink-0 text-zinc-100 font-medium truncate max-w-[180px]">{span.name}</span>
          <span class="ml-auto flex items-center gap-2 text-zinc-300">
            <span class={sv.badgeClass.split(' ').pop() + ' font-semibold'}>{sv.label}</span>
            <span>{span.duration_ms}ms</span>
          </span>
        </div>
      </button>
    {/each}
  </div>
{/if}