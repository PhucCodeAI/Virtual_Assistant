<script lang="ts">
  // Phase 1: span list dạng bảng, click row → expand inline JSON.
  // Phase 2 sẽ thay bằng SpanWaterfall + SpanDetail panel (chờ BE push
  // start_offset_ms — xem UI-007-REPLY-2 Q1).

  import { SvelteSet } from 'svelte/reactivity';
  import type { SpanDTO } from '$lib/state/types';
  import { formatDuration, spanTypeView, spanStatusView } from './trace_format';
  import JsonBlock from './JsonBlock.svelte';

  let { spans }: { spans: SpanDTO[] } = $props();

  // SvelteSet: Set có reactivity built-in (Svelte 5 runes).
  // Không cần reassign sau mutation — SvelteSet tự track.
  const expandedIds = new SvelteSet<string>();

  function toggle(spanId: string) {
    if (expandedIds.has(spanId)) expandedIds.delete(spanId);
    else expandedIds.add(spanId);
  }
</script>

{#if spans.length === 0}
  <div class="rounded-lg bg-[#141416] border border-[#27272a] p-8 text-center">
    <p class="text-xs text-zinc-500">Trace này không có span nào.</p>
  </div>
{:else}
  <div class="rounded-lg border border-[#27272a] overflow-hidden">
    <table class="w-full text-xs font-mono">
      <thead class="bg-[#141417] border-b border-[#27272a] text-[10px] uppercase tracking-wider text-zinc-500">
        <tr>
          <th class="w-8 px-2 py-2"></th>
          <th class="text-left px-3 py-2 font-medium">Span</th>
          <th class="text-left px-3 py-2 font-medium">Type</th>
          <th class="text-right px-3 py-2 font-medium">Duration</th>
          <th class="text-left px-3 py-2 font-medium">Status</th>
        </tr>
      </thead>
      <tbody>
        {#each spans as span (span.span_id)}
          {@const typeView = spanTypeView(span.span_type)}
          {@const statusView = spanStatusView(span.status)}
          {@const isExpanded = expandedIds.has(span.span_id)}

          <tr
            class="border-b border-[#1f1f23] hover:bg-[#1a1a1d] cursor-pointer transition-colors"
            onclick={() => toggle(span.span_id)}
          >
            <td class="px-2 py-2 text-center text-zinc-500">
              {isExpanded ? "▼" : "▶"}
            </td>
            <td class="px-3 py-2 text-zinc-300">{span.name}</td>
            <td class="px-3 py-2">
              <span class="inline-flex items-center gap-1 {typeView.colorClass}">
                <span>{typeView.icon}</span>
                <span class="text-[10px] font-semibold">{typeView.label}</span>
              </span>
            </td>
            <td class="px-3 py-2 text-right text-zinc-300">
              {formatDuration(span.duration_ms)}
            </td>
            <td class="px-3 py-2">
              <span class="inline-flex px-1.5 py-0.5 rounded border text-[10px] font-semibold {statusView.badgeClass}">
                {statusView.label}
              </span>
            </td>
          </tr>

          {#if isExpanded}
            <tr class="bg-[#0f0f11]">
              <td colspan="5" class="p-3 space-y-3">
                <div>
                  <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">
                    Input
                  </div>
                  <JsonBlock data={span.input_data} />
                </div>
                <div>
                  <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">
                    Output
                  </div>
                  <JsonBlock data={span.output_data} />
                </div>
                <div>
                  <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-500 mb-1">
                    Metadata
                  </div>
                  <JsonBlock data={span.metadata} />
                </div>
              </td>
            </tr>
          {/if}
        {/each}
      </tbody>
    </table>
  </div>
{/if}