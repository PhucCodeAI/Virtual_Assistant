<script lang="ts">
  // Master-detail layout cho trace explorer.
  //
  // URL `/traces`         → list only, right panel empty state
  // URL `/traces/{id}`    → list + detail của trace {id}
  //
  // Click trace ở cột trái → goto SPA → right panel load detail, không
  // reload list. Filter + page giữ nguyên.

  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import {
    listTraces,
    countTraces,
    deleteTrace,
    getTrace,
    TraceApiError,
  } from '$lib/services/trace_api';
  import TraceFilter, { type TraceFilterValue } from '$lib/components/trace/TraceFilter.svelte';
  import TraceListSidebar from '$lib/components/trace/TraceListSidebar.svelte';
  import TraceDetailPanel from '$lib/components/trace/TraceDetailPanel.svelte';
  import type { TraceSummary, TraceDetail } from '$lib/state/types';

  const selectedId = $derived($page.params.trace_id ?? null);

  // ---- List state ----
  let filter = $state<TraceFilterValue>({
    status: '',
    session_id: '',
    limit: 20,
  });
  let listPage = $state(1);
  let traces = $state<TraceSummary[]>([]);
  let totalCount = $state(0);
  let listLoading = $state(false);
  let listError = $state<string | null>(null);

  const totalPages = $derived(
    Math.max(1, Math.ceil(totalCount / filter.limit)),
  );

  // ---- Detail state ----
  let detail = $state<TraceDetail | null>(null);
  let detailLoading = $state(false);
  let detailError = $state<string | null>(null);

  // Load list khi filter/page thay đổi. Snapshot để tránh đọc reactive
  // sau await.
  $effect(() => {
    const snap = {
      limit: filter.limit,
      status: filter.status,
      session_id: filter.session_id,
      offset: (listPage - 1) * filter.limit,
    };
    void loadList(snap);
  });

  // Load detail khi selectedId thay đổi.
  $effect(() => {
    const id = selectedId;
    if (!id) {
      detail = null;
      detailError = null;
      return;
    }
    void loadDetail(id);
  });

  async function loadList(snap: {
    limit: number;
    status: TraceFilterValue['status'];
    session_id: string;
    offset: number;
  }) {
    listLoading = true;
    listError = null;
    try {
      const [items, count] = await Promise.all([
        listTraces({
          limit: snap.limit,
          offset: snap.offset,
          status: snap.status,
          session_id: snap.session_id,
        }),
        countTraces({
          status: snap.status,
          session_id: snap.session_id,
        }),
      ]);
      traces = items;
      totalCount = count;
    } catch (err) {
      listError =
        err instanceof Error ? err.message : 'Không tải được danh sách trace.';
      traces = [];
      totalCount = 0;
    } finally {
      listLoading = false;
    }
  }

  async function loadDetail(id: string) {
    detailLoading = true;
    detailError = null;
    detail = null;
    try {
      detail = await getTrace(id);
    } catch (err) {
      if (err instanceof TraceApiError && err.status === 404) {
        detailError = `Không tìm thấy trace "${id}".`;
      } else {
        detailError =
          err instanceof Error ? err.message : 'Không tải được trace.';
      }
    } finally {
      detailLoading = false;
    }
  }

  function handleFilterChange() {
    listPage = 1;
  }

  function selectTrace(id: string) {
    void goto(resolve(`/traces/${id}`));
  }

  async function handleDelete(id: string) {
    try {
      await deleteTrace(id);
      // Đang xem trace bị xoá → quay về empty detail.
      if (selectedId === id) void goto(resolve('/traces'));
      // Reload list với filter hiện tại.
      const snap = {
        limit: filter.limit,
        status: filter.status,
        session_id: filter.session_id,
        offset: (listPage - 1) * filter.limit,
      };
      await loadList(snap);
    } catch (err) {
      listError =
        err instanceof Error ? `Xoá thất bại: ${err.message}` : 'Xoá trace thất bại.';
    }
  }

  function goPrev() {
    if (listPage > 1) listPage -= 1;
  }
  function goNext() {
    if (listPage < totalPages) listPage += 1;
  }
</script>

<div class="h-full flex">
  <!-- ══════════════ LEFT: sidebar list ══════════════ -->
  <aside class="w-[360px] shrink-0 border-r border-[#27272a] flex flex-col bg-[#0a0a0c]">
    <TraceFilter value={filter} onChange={handleFilterChange} />

    <div class="flex-1 min-h-0 overflow-y-auto">
      <TraceListSidebar
        traces={traces}
        selectedId={selectedId}
        loading={listLoading}
        error={listError}
        onSelect={selectTrace}
        onDelete={handleDelete}
      />
    </div>

    {#if totalCount > 0}
      <div class="shrink-0 border-t border-[#27272a] px-3 py-2 flex items-center justify-between gap-2 text-[10px] font-mono">
        <button
          type="button"
          onclick={goPrev}
          disabled={listPage <= 1}
          class="px-2 py-0.5 rounded border border-[#303036] bg-[#1f1f23] text-zinc-300 hover:bg-[#2b2b30] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          ◀
        </button>
        <span class="text-zinc-500">
          {listPage} / {totalPages} · {totalCount} trace
        </span>
        <button
          type="button"
          onclick={goNext}
          disabled={listPage >= totalPages}
          class="px-2 py-0.5 rounded border border-[#303036] bg-[#1f1f23] text-zinc-300 hover:bg-[#2b2b30] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          ▶
        </button>
      </div>
    {/if}
  </aside>

  <!-- ══════════════ RIGHT: detail panel ══════════════ -->
  <main class="flex-1 min-w-0 overflow-y-auto">
    <TraceDetailPanel
      trace={detail}
      loading={detailLoading}
      error={detailError}
    />
  </main>
</div>