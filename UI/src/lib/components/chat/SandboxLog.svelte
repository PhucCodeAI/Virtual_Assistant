<script lang="ts">
  // Log danh sách lần chạy sandbox (UI-006).
  //
  // Mỗi entry: command, exit_code, duration_ms, is_timeout, stdout_summary.
  // Entry exit_code !== 0 hoặc is_timeout → style đỏ.
  //
  // Nút "Xem full log": BE đã confirm có thể defer. Hiện tại disabled —
  // route /traces/{id} chưa có ở UI, sẽ làm ở ticket sau.
  // Khi implement: component cần thêm prop traceId để build URL.
  // Xem ticket UI-FINAL-REPLY-2 §3 câu hỏi cuối.

  import type { SandboxEventData } from '$lib/state/types';
  import { formatDuration } from './terminal_status';

  let { events }: { events: SandboxEventData[] } = $props();

  function isFailure(evt: SandboxEventData): boolean {
    return evt.exit_code !== 0 || evt.is_timeout;
  }
</script>

{#if events.length > 0}
  <div class="w-full rounded-xl bg-[#141416] border border-[#27272a] overflow-hidden">
    <div class="px-3 py-1.5 border-b border-[#27272a] flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="text-xs font-semibold text-zinc-300">🧪 Sandbox Log</span>
        <span class="text-[10px] font-mono text-zinc-500">
          {events.length} lần chạy
        </span>
      </div>

      <!-- TODO(UI-XXX): mở trace detail + parse span sandbox để show full stdout.
           Cần route /traces/{id} ở UI trước. -->
      <button
        type="button"
        disabled
        title="Tính năng xem full log sẽ có ở ticket sau"
        class="text-[10px] font-mono px-2 py-0.5 rounded border border-zinc-700 text-zinc-600 cursor-not-allowed"
      >
        Xem full log
      </button>
    </div>

    <div class="divide-y divide-[#1f1f23]">
      {#each events as evt, i (i)}
        {@const failed = isFailure(evt)}
        <div class="p-3 space-y-2">
          <div class="flex items-center gap-2 text-[11px] font-mono">
            <span class="text-zinc-500">#{i + 1}</span>
            <code class="flex-1 truncate text-sky-300">
              $ {evt.command.join(' ')}
            </code>

            {#if evt.is_timeout}
              <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold
                           bg-amber-500/15 border border-amber-500/40 text-amber-400">
                TIMEOUT
              </span>
            {/if}

            <span class="px-1.5 py-0.5 rounded text-[10px] font-semibold border
                         {failed
                           ? 'bg-rose-500/10 border-rose-500/40 text-rose-400'
                           : 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400'}">
              exit={evt.exit_code}
            </span>

            <span class="text-zinc-600 text-[10px]">
              {formatDuration(evt.duration_ms)}
            </span>
          </div>

          {#if evt.stdout_summary}
            <pre class="text-[11px] font-mono leading-relaxed whitespace-pre-wrap break-words
                        p-2 rounded bg-black/40 border border-[#1f1f23]
                        {failed ? 'text-rose-300' : 'text-zinc-300'}">{evt.stdout_summary}</pre>
          {/if}
        </div>
      {/each}
    </div>
  </div>
{/if}