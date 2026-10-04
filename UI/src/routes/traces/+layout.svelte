<script lang="ts">
  // Layout chung cho Trace Explorer — full screen, cột trái + cột phải.
  // Không kế thừa app shell 3-panel (chat/canvas/explorer).

  import { resolve } from '$app/paths';
  import type { Snippet } from 'svelte';

  let { children }: { children: Snippet } = $props();

  const homeHref = resolve('/');
</script>

<div class="h-screen flex flex-col bg-[#0a0a0c] text-zinc-200">
  <header class="shrink-0 border-b border-[#27272a] bg-[#141417]">
    <div class="px-4 h-12 flex items-center gap-3">
      <a
        href={homeHref}
        class="flex items-center gap-1.5 text-xs font-medium text-zinc-400 hover:text-zinc-200 transition-colors"
      >
        <span>←</span>
        <span>Về Chat</span>
      </a>
      <span class="text-zinc-700">|</span>
      <h1 class="text-sm font-semibold text-zinc-200">Trace Explorer</h1>
    </div>
  </header>

  <div class="flex-1 min-h-0">
    {@render children()}
  </div>
</div>