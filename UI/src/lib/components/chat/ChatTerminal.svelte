<script lang="ts">
  import type { ChatService } from "$lib/state/chat.svelte";
  import ChatMessage from "./ChatMessage.svelte";
  import ChatInput from "./ChatInput.svelte";
  
  let { chat }: { chat: ChatService } = $props();
</script>

<main class="flex-1 flex flex-col py-4 relative min-w-0">
  <div class="absolute top-4 left-1/2 -translate-x-1/2 px-6 py-1 bg-gray-900/80 border border-cyan-500/30 rounded-full backdrop-blur-md z-10 flex items-center gap-3">
    <span class="relative flex h-2 w-2">
      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
      <span class="relative inline-flex rounded-full h-2 w-2 bg-cyan-500"></span>
    </span>
    <span class="text-[10px] uppercase font-mono tracking-widest text-cyan-400">Trợ lý ảo cá nhân</span>
  </div>

  <div class="flex-1 overflow-y-auto mt-8 mb-4 space-y-6 px-4 custom-scrollbar">
    {#if chat.messages.length === 0}
      <div class="flex h-full flex-col items-center justify-center text-cyan-600/50 space-y-4">
        <svg class="w-16 h-16 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1" d="M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5"></path></svg>
        <div class="text-sm font-mono uppercase tracking-widest text-cyan-500/70">Mời chủ nhân ra lệnh...</div>
      </div>
    {/if}

    {#each chat.messages as msg, index}
      {#if msg.role !== "system"}
        <ChatMessage {msg} {index} {chat} />
      {/if}
    {/each}
  </div>

  <ChatInput {chat} />
</main>