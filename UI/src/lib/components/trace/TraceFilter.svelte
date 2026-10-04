<script lang="ts">
  // Filter compact cho sidebar hẹp (360px). Row 1: status + page size.
  // Row 2: session input với debounce.

  import type { FinalStatus } from '$lib/state/types';

  export interface TraceFilterValue {
    status: FinalStatus | "";
    session_id: string;
    limit: number;
  }

  let {
    value = $bindable(),
    onChange
  }: {
    value: TraceFilterValue;
    onChange?: () => void;
  } = $props();

  let sessionInput = $state(value.session_id);
  let debounceTimer: ReturnType<typeof setTimeout> | null = null;

  function handleSessionInput(e: Event) {
    const target = e.currentTarget as HTMLInputElement;
    sessionInput = target.value;
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      value.session_id = sessionInput;
      onChange?.();
    }, 300);
  }

  function handleStatusChange(e: Event) {
    const target = e.currentTarget as HTMLSelectElement;
    value.status = target.value as FinalStatus | "";
    onChange?.();
  }

  function handleLimitChange(e: Event) {
    const target = e.currentTarget as HTMLSelectElement;
    value.limit = Number(target.value);
    onChange?.();
  }
</script>

<div class="shrink-0 border-b border-[#27272a] p-2 space-y-2 bg-[#0f0f11]">
  <div class="flex items-center gap-1.5">
    <label for="tf-status" class="sr-only">Status</label>
    <select
      id="tf-status"
      value={value.status}
      onchange={handleStatusChange}
      class="flex-1 min-w-0 bg-[#1f1f23] border border-[#2c2c31] text-zinc-200 text-[11px] rounded px-2 py-1 focus:outline-none focus:border-amber-500/60"
    >
      <option value="">All status</option>
      <option value="SUCCESS">SUCCESS</option>
      <option value="FAILED">FAILED</option>
      <option value="CANCELLED">CANCELLED</option>
    </select>

    <label for="tf-limit" class="sr-only">Page size</label>
    <select
      id="tf-limit"
      value={String(value.limit)}
      onchange={handleLimitChange}
      class="shrink-0 bg-[#1f1f23] border border-[#2c2c31] text-zinc-200 text-[11px] rounded px-2 py-1 focus:outline-none focus:border-amber-500/60"
    >
      <option value="10">10</option>
      <option value="20">20</option>
      <option value="50">50</option>
    </select>
  </div>

  <input
    id="tf-session"
    type="text"
    value={sessionInput}
    oninput={handleSessionInput}
    placeholder="Lọc theo session_id..."
    class="w-full bg-[#1f1f23] border border-[#2c2c31] text-zinc-200 text-[11px] rounded px-2 py-1 focus:outline-none focus:border-amber-500/60 placeholder-zinc-600"
  />
</div>