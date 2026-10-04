<script lang="ts">
  // Container cho right panel. 4 trạng thái:
  //   loading | error | empty (chưa chọn trace) | có trace
  //
  // Có trace → render: MetricsCard → Span view (Tree/Waterfall toggle)
  // → SpanDetail (nếu span được chọn).
  //
  // selectedSpanId giữ ở đây. Không dùng $effect để reset — vì effect
  // chạy sau DOM update sẽ ghi đè state user vừa set khi click.
  // Thay vào đó: $derived tự trả null khi selectedSpanId không khớp span
  // nào trong trace hiện tại (VD: user chuyển sang trace khác).

  import type { TraceDetail } from '$lib/state/types';
  import TraceMetricsCard from './TraceMetricsCard.svelte';
  import SpanTree from './SpanTree.svelte';
  import SpanWaterfall from './SpanWaterfall.svelte';
  import SpanDetail from './SpanDetail.svelte';

  let {
    trace,
    loading,
    error,
  }: {
    trace: TraceDetail | null;
    loading: boolean;
    error: string | null;
  } = $props();

  type ViewMode = 'tree' | 'waterfall';
  let viewMode = $state<ViewMode>('tree');
  let selectedSpanId = $state<string | null>(null);

  // selectedSpan tự trả null khi:
  //   - Chưa có trace
  //   - Chưa chọn span
  //   - span_id không tồn tại trong trace hiện tại (trace đã đổi)
  const selectedSpan = $derived.by(() => {
    if (!trace || !selectedSpanId) return null;
    return trace.spans.find((s) => s.span_id === selectedSpanId) ?? null;
  });

  function handleSelectSpan(id: string) {
    selectedSpanId = id;
  }

  function handleCloseSpan() {
    selectedSpanId = null;
  }
</script>

{#if loading}
  <div class="p-12 text-center text-xs text-zinc-500">Đang tải trace...</div>
{:else if error}
  <div class="m-6 rounded-lg bg-rose-500/10 border border-rose-500/40 p-4 flex items-start gap-3">
    <span class="text-rose-400 text-xl shrink-0">⚠</span>
    <div>
      <div class="text-sm text-rose-300 font-semibold mb-1">Không tải được trace</div>
      <div class="text-xs text-zinc-400">{error}</div>
    </div>
  </div>
{:else if !trace}
  <div class="flex flex-col items-center justify-center h-full text-zinc-500 space-y-2 px-4">
    <div class="text-5xl">👈</div>
    <p class="text-sm text-zinc-300">Chọn một trace ở danh sách bên trái</p>
    <p class="text-[11px] text-center max-w-md text-zinc-500">
      Chi tiết span, waterfall và metadata sẽ hiển thị ở đây.
    </p>
  </div>
{:else}
  <div class="p-4 space-y-4">
    <TraceMetricsCard {trace} />

    <div class="space-y-2">
      <div class="flex items-center justify-between">
        <h2 class="text-xs font-mono uppercase tracking-wider text-zinc-300 font-semibold">
          Spans ({trace.spans.length})
        </h2>
        <div class="flex items-center gap-1 p-0.5 rounded bg-[#1f1f23] border border-[#3f3f46]">
          <button
            type="button"
            onclick={() => (viewMode = 'tree')}
            class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold transition-colors
                   {viewMode === 'tree'
                     ? 'bg-amber-500/25 text-amber-200'
                     : 'text-zinc-400 hover:text-zinc-100'}"
          >
            Tree
          </button>
          <button
            type="button"
            onclick={() => (viewMode = 'waterfall')}
            class="px-2 py-0.5 rounded text-[10px] font-mono font-semibold transition-colors
                   {viewMode === 'waterfall'
                     ? 'bg-amber-500/25 text-amber-200'
                     : 'text-zinc-400 hover:text-zinc-100'}"
          >
            Waterfall
          </button>
        </div>
      </div>

      <div class="rounded-lg border border-[#52525b] overflow-hidden bg-[#18181b]">
        {#if viewMode === 'tree'}
          <SpanTree
            spans={trace.spans}
            selectedSpanId={selectedSpanId}
            onSelect={handleSelectSpan}
          />
        {:else}
          <SpanWaterfall
            spans={trace.spans}
            totalDurationMs={trace.duration_ms}
            selectedSpanId={selectedSpanId}
            onSelect={handleSelectSpan}
          />
        {/if}
      </div>
    </div>

    {#if selectedSpan}
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <h2 class="text-xs font-mono uppercase tracking-wider text-zinc-300 font-semibold">
            Span Detail
          </h2>
          <button
            type="button"
            onclick={handleCloseSpan}
            class="text-[10px] font-mono text-zinc-400 hover:text-zinc-100 transition-colors"
          >
            Đóng ✕
          </button>
        </div>
        <div class="rounded-lg border border-[#52525b] bg-[#18181b] overflow-hidden">
          <SpanDetail span={selectedSpan} />
        </div>
      </div>
    {/if}
  </div>
{/if}