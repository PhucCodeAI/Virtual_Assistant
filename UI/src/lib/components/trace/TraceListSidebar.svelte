<script lang="ts">
  // Compact list cho sidebar 360px. Mỗi item là 1 card dense 3 dòng:
  //   [icon] trace_id                    [relative time]
  //   prompt (truncate)
  //   duration · tokens · cost · [delete]
  //
  // Selected row: viền trái vàng + background highlight.
  //
  // Row dùng <div role="button"> vì bên trong có <button> delete — HTML
  // không cho phép nested interactive element (nếu dùng <button> ngoài
  // → hydration mismatch khi SSR).

  import type { TraceSummary } from '$lib/state/types';
  import {
    relativeTime,
    absoluteTime,
    formatDuration,
    formatCost,
    finalStatusView,
  } from './trace_format';

  let {
    traces,
    selectedId,
    loading,
    error,
    onSelect,
    onDelete,
  }: {
    traces: TraceSummary[];
    selectedId: string | null;
    loading: boolean;
    error: string | null;
    onSelect: (id: string) => void;
    onDelete: (id: string) => void;
  } = $props();

  // Inline confirm — không dùng window.confirm.
  let pendingDeleteId = $state<string | null>(null);

  function handleRowClick(id: string) {
    if (pendingDeleteId === id) return; // đang confirm xoá — không navigate
    onSelect(id);
  }

  function handleRowKeydown(e: KeyboardEvent, id: string) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleRowClick(id);
    }
  }

  function requestDelete(id: string, e: MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    pendingDeleteId = id;
  }
  function confirmDelete(id: string, e: MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    onDelete(id);
    pendingDeleteId = null;
  }
  function cancelDelete(e: MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    pendingDeleteId = null;
  }
</script>

{#if error}
  <div class="m-3 rounded bg-rose-500/10 border border-rose-500/40 p-2 text-[11px] text-rose-300">
    {error}
  </div>
{/if}

{#if loading}
  <div class="p-8 text-center text-[11px] text-zinc-500">Đang tải...</div>
{:else if traces.length === 0}
  <div class="p-8 text-center text-zinc-500 space-y-1">
    <div class="text-3xl">📭</div>
    <p class="text-[11px]">Chưa có trace nào</p>
  </div>
{:else}
  <ul class="divide-y divide-[#1f1f23]">
    {#each traces as trace (trace.trace_id)}
      {@const sv = finalStatusView(trace.status)}
      {@const isSelected = selectedId === trace.trace_id}
      <li>
        <div
          role="button"
          tabindex="0"
          aria-pressed={isSelected}
          onclick={() => handleRowClick(trace.trace_id)}
          onkeydown={(e) => handleRowKeydown(e, trace.trace_id)}
          class="w-full text-left px-3 py-2.5 transition-colors group cursor-pointer
                 focus:outline-none focus:ring-1 focus:ring-amber-500/60
                 {isSelected
                   ? 'bg-amber-500/10 border-l-2 border-amber-500'
                   : 'border-l-2 border-transparent hover:bg-[#141417]'}"
        >
          <!-- Row 1: status icon + trace_id + relative time -->
          <div class="flex items-center gap-2 mb-1">
            <span class="text-sm shrink-0">{sv.icon}</span>
            <span
              class="text-[11px] font-mono text-zinc-300 truncate flex-1"
              title={trace.trace_id}
            >
              {trace.trace_id}
            </span>
            <span
              class="text-[10px] text-zinc-500 shrink-0"
              title={absoluteTime(trace.created_at)}
            >
              {relativeTime(trace.created_at)}
            </span>
          </div>

          <!-- Row 2: prompt -->
          <div class="text-[11px] text-zinc-400 truncate mb-1" title={trace.prompt}>
            {trace.prompt}
          </div>

          <!-- Row 3: metrics + delete -->
          <div class="flex items-center gap-3 text-[10px] font-mono text-zinc-600">
            <span>{formatDuration(trace.duration_ms)}</span>
            <span>{trace.total_tokens} tok</span>
            <span class="text-emerald-500/70">{formatCost(trace.cost)}</span>

            <span class="ml-auto flex items-center gap-1">
              {#if pendingDeleteId === trace.trace_id}
                <button
                  type="button"
                  onclick={(e) => confirmDelete(trace.trace_id, e)}
                  class="px-1.5 py-0.5 rounded text-[9px] bg-rose-500/20 border border-rose-500/40 text-rose-300 hover:bg-rose-500/30"
                >
                  Xoá
                </button>
                <button
                  type="button"
                  onclick={cancelDelete}
                  class="px-1.5 py-0.5 rounded text-[9px] bg-[#222226] border border-[#303036] text-zinc-400 hover:bg-[#2b2b30]"
                >
                  Huỷ
                </button>
              {:else}
                <button
                  type="button"
                  onclick={(e) => requestDelete(trace.trace_id, e)}
                  class="text-[11px] text-zinc-600 hover:text-rose-400 opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
                  title="Xoá trace"
                >
                  🗑️
                </button>
              {/if}
            </span>
          </div>
        </div>
      </li>
    {/each}
  </ul>
{/if}