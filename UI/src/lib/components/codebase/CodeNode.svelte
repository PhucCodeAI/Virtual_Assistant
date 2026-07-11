<script lang="ts">
  import type { ChatService, CodeNode } from "$lib/state/chat.svelte";
  
  let { node, chat }: { node: CodeNode; chat: ChatService } = $props();
</script>

{#if node}
  <div class="ml-1 mt-1">
    <div class="flex items-center gap-1.5 group">
      {#if node.type === "folder"}
        <button onclick={() => chat.toggleCollapse(node.path)} class="text-cyan-600 hover:text-cyan-300 w-4 text-center transition-colors font-mono text-[10px]">
          {chat.isCollapsed(node.path) ? "▶" : "▼"}
        </button>
      {:else}
        <div class="w-4"></div>
      {/if}

      <label class="flex items-center gap-2 cursor-pointer flex-1">
        <div class="relative flex items-center justify-center w-3 h-3 rounded-sm border {chat.isIgnored(node.path, node.type) ? 'border-red-500 bg-red-900/50' : 'border-cyan-500 bg-cyan-900/50'} transition-colors">
          <input type="checkbox" class="absolute opacity-0 cursor-pointer" checked={chat.isIgnored(node.path, node.type)} onchange={() => chat.toggleIgnore(node.path, node.type)} />
          {#if chat.isIgnored(node.path, node.type)}
            <svg class="w-2 h-2 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          {:else}
            <div class="w-1.5 h-1.5 bg-cyan-400 rounded-sm"></div>
          {/if}
        </div>
        
        {#if node.type === "folder"}
          <span class="text-yellow-500/80 text-xs">📁</span>
          <span class="text-[11px] font-mono text-gray-300 group-hover:text-cyan-300 transition-colors truncate {chat.isIgnored(node.path, node.type) ? 'line-through opacity-40 text-red-300' : ''}">{node.name}/</span>
        {:else}
          <span class="text-cyan-600/50 text-xs">📄</span>
          <span class="text-[11px] font-mono text-gray-400 group-hover:text-cyan-300 transition-colors truncate {chat.isIgnored(node.path, node.type) ? 'line-through opacity-40 text-red-300' : ''}">{node.name}</span>
        {/if}
      </label>
    </div>

    {#if node.type === "folder" && node.children && node.children.length > 0 && !chat.isCollapsed(node.path) && !chat.isIgnored(node.path, node.type)}
      <div class="border-l border-cyan-800/40 pl-2 ml-2 mt-1 space-y-1">
        {#each node.children as child}
          <!-- Gọi lại chính nó (Đệ quy Component) -->
          <svelte:self node={child} {chat} />
        {/each}
      </div>
    {/if}
  </div>
{/if}