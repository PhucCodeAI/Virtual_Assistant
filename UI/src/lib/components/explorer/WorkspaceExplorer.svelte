<script lang="ts">
  import { agentSession } from '$lib/state/agent_session.svelte';
  import type { FileNode } from '$lib/state/types';

  function renderStatusBadge(status: FileNode['status']) {
    switch (status) {
      case 'editing':
        return '<span class="text-[10px] px-1 py-0.2 bg-amber-500/10 text-amber-400 border border-amber-500/30 rounded">Editing</span>';
      case 'testing':
        return '<span class="text-[10px] px-1 py-0.2 bg-sky-500/10 text-sky-400 border border-sky-500/30 rounded">Testing</span>';
      default:
        return '';
    }
  }
</script>

<div class="flex flex-col h-full text-xs">
  <div class="p-3 uppercase tracking-wider text-[11px] font-semibold text-zinc-500 border-b border-[#27272a] flex items-center justify-between">
    <span>Workspace Explorer</span>
    <span class="text-[10px] font-mono lowercase text-zinc-600">fastapi-env</span>
  </div>

  <div class="flex-1 overflow-y-auto p-2 space-y-1">
    {#each agentSession.fileTree as node (node.id)}
      <div class="font-mono">
        <div class="flex items-center gap-1.5 py-1 px-2 text-zinc-400 font-medium">
          <svg class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z"/></svg>
          <span>{node.name}</span>
        </div>
        {#if node.children}
          <div class="pl-4 space-y-0.5">
            {#each node.children as child (child.id)}
              <div
                class="flex items-center justify-between px-2 py-1 rounded cursor-pointer transition-all duration-150 {child.status === 'editing' ? 'bg-amber-500/10 border-l-2 border-amber-400 text-amber-200' : 'hover:bg-zinc-800/60 text-zinc-400'}"
              >
                <span class="truncate">{child.name}</span>
                {@html renderStatusBadge(child.status)}
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/each}
  </div>

  <div class="h-48 border-t border-[#27272a] flex flex-col bg-[#111113]">
    <div class="p-2.5 uppercase tracking-wider text-[10px] font-semibold text-zinc-500 border-b border-[#202023] flex items-center justify-between">
      <span>Auto-Commit Trail</span>
      <span class="text-sky-400 font-mono text-[9px]">● HEAD</span>
    </div>
    <div class="flex-1 overflow-y-auto p-2 space-y-2">
      {#each agentSession.commits as commit (commit.hash)}
        <div
          class="p-2 rounded border transition-colors cursor-pointer text-left {commit.isActive ? 'bg-[#18181b] border-sky-500/40 text-zinc-200' : 'bg-transparent border-[#232326] text-zinc-500 hover:border-zinc-700'}"
        >
          <div class="flex items-center justify-between font-mono text-[10px]">
            <span class="font-bold text-sky-400">{commit.shortHash}</span>
            <span>{commit.timestamp}</span>
          </div>
          <p class="text-[11px] font-medium mt-1 truncate">{commit.message}</p>
        </div>
      {/each}
    </div>
  </div>
</div>