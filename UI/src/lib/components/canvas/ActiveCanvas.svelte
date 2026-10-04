<script lang="ts">
  // Diff viewer + sandbox mini console.
  //
  // UI-005: badge file event gần nhất theo activeFile.
  // Update: button "Xem Trace" navigate sang /traces dashboard.

  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { agentSession } from '$lib/state/agent_session.svelte';
  import type { FileEventData, FileActionType } from '$lib/state/types';

  let isTerminalExpanded = $state(true);

  function toggleTerminal() {
    isTerminalExpanded = !isTerminalExpanded;
  }

  // Navigate sang trace dashboard. Nếu pipeline gần nhất có trace_id →
  // mở thẳng detail. Ngược lại → list.
  function goToTrace() {
    const lastTraceId = agentSession.lastDone?.trace_id;
    if (lastTraceId) {
      void goto(resolve(`/traces/${lastTraceId}`));
    } else {
      void goto(resolve('/traces'));
    }
  }

  // File event gần nhất tương ứng với activeFile — cho badge header.
  const recentFileEvent = $derived<FileEventData | null>(
    [...agentSession.fileEvents]
      .reverse()
      .find((f) => f.path === agentSession.activeFile) ?? null,
  );

  const actionMeta: Record<FileActionType, { cls: string; icon: string; label: string }> = {
    create: { cls: 'bg-emerald-500/10 border-emerald-500/40 text-emerald-400', icon: '+', label: 'Created' },
    update: { cls: 'bg-amber-500/10 border-amber-500/40 text-amber-400',       icon: '~', label: 'Updated' },
    delete: { cls: 'bg-rose-500/10 border-rose-500/40 text-rose-400',          icon: '−', label: 'Deleted' },
  };

  const sandboxDotCls = $derived(
    agentSession.sandbox.status === 'passed'    ? 'bg-emerald-500' :
    agentSession.sandbox.status === 'running'   ? 'bg-amber-400 animate-ping' :
    agentSession.sandbox.status === 'failed'    ? 'bg-rose-500' :
    agentSession.sandbox.status === 'cancelled' ? 'bg-zinc-500' :
                                                  'bg-zinc-600',
  );
</script>

<div class="flex flex-col h-full bg-[#121214]">
  <!-- ══════════════ Header ══════════════ -->
  <div class="h-10 px-4 border-b border-[#27272a] flex items-center justify-between bg-[#151518] shrink-0">
    <div class="flex items-center gap-3 font-mono text-xs min-w-0">
      <div class="flex items-center gap-2 min-w-0">
        <span class="text-zinc-600 shrink-0">target:</span>
        <span class="text-zinc-200 font-semibold truncate">{agentSession.activeFile}</span>
      </div>

      {#if recentFileEvent}
        {@const meta = actionMeta[recentFileEvent.action]}
        <span
          class="flex items-center gap-1.5 px-2 py-0.5 rounded border text-[10px] shrink-0 {meta.cls}"
          title="{meta.label} {recentFileEvent.path}"
        >
          <span class="font-bold">{meta.icon}</span>
          <span class="font-semibold">{meta.label}</span>
          <span class="text-emerald-400">+{recentFileEvent.lines_added}</span>
          <span class="text-rose-400">−{recentFileEvent.lines_removed}</span>
        </span>
      {/if}
    </div>

    <div class="flex items-center gap-3 shrink-0">
      <span class="text-[10px] font-mono px-2 py-0.5 rounded border border-amber-500/40 text-amber-400 bg-amber-500/5">
        {agentSession.activeFileStatus}
      </span>
      <div class="flex items-center gap-1">
        <button
          type="button"
          class="px-2 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-[11px] rounded font-medium transition-colors"
        >
          Revert
        </button>
        <button
          type="button"
          class="px-2 py-1 bg-sky-600 hover:bg-sky-500 text-white text-[11px] rounded font-medium transition-colors"
        >
          Commit Patch
        </button>
        <button
          type="button"
          onclick={goToTrace}
          class="px-2 py-1 bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/40 text-[11px] rounded font-medium transition-colors flex items-center gap-1"
          title="Mở Trace Explorer — xem lịch sử toàn bộ request"
        >
          <span>📊</span>
          <span>Xem Trace</span>
        </button>
      </div>
    </div>
  </div>

  <!-- ══════════════ Diff viewer ══════════════ -->
  <div class="flex-1 overflow-y-auto font-mono text-xs bg-[#121214] select-text">
    <div class="min-w-max p-2 space-y-0.5">
      {#each agentSession.diffLines ?? [] as line, i (i)}
        <div class="flex items-center leading-5 hover:bg-zinc-800/30
                    {line.type === 'add' ? 'bg-[#166534]/20 text-emerald-300'
                     : line.type === 'del' ? 'bg-[#991b1b]/20 text-rose-300'
                     : 'text-zinc-400'}">
          <div class="w-9 px-1 text-right text-zinc-600 select-none text-[10px] shrink-0 border-r border-[#27272a]/40">
            {line.oldLineNumber ?? ''}
          </div>
          <div class="w-9 px-1 text-right text-zinc-600 select-none text-[10px] shrink-0 border-r border-[#27272a]/40 mr-2">
            {line.newLineNumber ?? ''}
          </div>
          <div class="w-4 select-none text-center shrink-0 font-bold">
            {line.type === 'add' ? '+' : line.type === 'del' ? '-' : ' '}
          </div>
          <pre class="font-mono text-xs whitespace-pre">{line.content}</pre>
        </div>
      {/each}
    </div>
  </div>

  <!-- ══════════════ Sandbox mini console ══════════════ -->
  <div class="border-t border-[#27272a] bg-[#0c0c0e] shrink-0 flex flex-col transition-all duration-200
              {isTerminalExpanded ? 'h-52' : 'h-8'}">
    <button
      type="button"
      aria-expanded={isTerminalExpanded}
      aria-label="Toggle Sandbox Mini Console"
      onclick={toggleTerminal}
      class="w-full h-8 px-3 border-b border-[#1c1c1f] flex items-center justify-between select-none cursor-pointer bg-[#121215] text-left hover:bg-[#18181c] transition-colors focus:outline-none focus:ring-1 focus:ring-amber-500"
    >
      <div class="flex items-center gap-2">
        <span class="w-2 h-2 rounded-full {sandboxDotCls}"></span>
        <span class="font-mono text-[11px] font-semibold tracking-wide text-zinc-400">
          Sandbox Mini Console
        </span>
        {#if agentSession.sandbox.durationMs}
          <span class="text-[10px] font-mono text-zinc-600">
            ({agentSession.sandbox.durationMs}ms)
          </span>
        {/if}
      </div>
      <span class="text-zinc-500 text-xs font-mono">{isTerminalExpanded ? '▼' : '▲'}</span>
    </button>

    {#if isTerminalExpanded}
      <div class="flex-1 p-2.5 overflow-y-auto font-mono text-[11px] leading-relaxed text-zinc-400 bg-black/40">
        {#if agentSession.sandbox.command}
          <div class="text-sky-400 font-bold mb-1">$ {agentSession.sandbox.command}</div>
        {/if}
        {#each agentSession.sandbox.output ?? [] as out, i (i)}
          <div class="{out.includes('PASSED') ? 'text-emerald-400'
                        : out.includes('FAIL') || out.includes('Error') ? 'text-rose-400'
                        : out.includes('Cancelled') ? 'text-zinc-500'
                        : 'text-zinc-400'}">
            {out}
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>