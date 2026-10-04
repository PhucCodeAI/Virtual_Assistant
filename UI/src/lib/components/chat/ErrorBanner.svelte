<script lang="ts">
  // Banner đỏ hiển thị khi có event "error" hoặc transport error.
  // Không chặn input — chỉ inform user.

  import type { ErrorEventData } from '$lib/state/types';
  import { getErrorMessage } from '$lib/state/types/errors';

  let { error }: { error: ErrorEventData } = $props();
</script>

<div class="w-full rounded-xl bg-rose-500/10 border border-rose-500/40 p-3 flex items-start gap-3">
  <span class="text-rose-400 text-lg shrink-0">⚠</span>
  <div class="flex-1 min-w-0">
    <div class="text-rose-300 text-xs font-semibold">
      {getErrorMessage(error.code)}
    </div>
    <div class="text-[10px] font-mono text-zinc-500 mt-1 truncate">
      [{error.code}] {error.message}
    </div>
  </div>
</div>