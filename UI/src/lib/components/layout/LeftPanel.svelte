<script lang="ts">
  import type { ChatService } from "$lib/state/chat.svelte";
  import CodeNode from "$lib/components/codebase/CodeNode.svelte";

  let { chat }: { chat: ChatService } = $props();
</script>

<!-- Đổi w-1/4 thành w-[20%] min-w-[240px] để chiếm đúng 20% tỉ lệ màn hình -->
<aside
  class="w-[20%] min-w-[240px] glass-panel m-4 rounded-2xl p-5 flex flex-col border-l-4 {chat.mode ===
  'coding'
    ? 'border-l-emerald-500'
    : 'border-l-cyan-500'} transition-all custom-scrollbar overflow-y-auto"
>
  {#if chat.mode === "coding"}
    <h2
      class="text-[10px] font-bold text-emerald-400 mb-4 uppercase tracking-[0.2em] flex items-center gap-2"
    >
      <svg
        class="w-4 h-4 animate-spin-slow"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        ><path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4"
        ></path></svg
      >
      Cấu trúc Codebase
    </h2>
    <div class="space-y-3 flex-1 flex flex-col font-sans">
      <div class="flex flex-col gap-1">
        <label class="text-[9px] font-mono text-gray-500 uppercase"
          >Root Absolute Path</label
        >
        <input
          type="text"
          bind:value={chat.codebasePath}
          placeholder="e.g. D:/Projects/AI"
          class="bg-black/50 border border-emerald-900/50 rounded-lg p-2 text-xs font-mono text-emerald-100 focus:border-emerald-500 outline-none"
        />
      </div>
      <div class="flex flex-col gap-1">
        <label class="text-[9px] font-mono text-gray-500 uppercase"
          >Ignore Extensions</label
        >
        <input
          type="text"
          bind:value={chat.extensionsInput}
          placeholder=".pyc, .md"
          class="bg-black/50 border border-emerald-900/50 rounded-lg p-2 text-xs font-mono text-emerald-100 focus:border-emerald-500 outline-none"
        />
      </div>

      {#if !chat.codeTree}
        <button
          onclick={() => chat.scanCodebase()}
          disabled={chat.isScanning || !chat.codebasePath}
          class="w-full bg-emerald-900/30 border border-emerald-500 text-emerald-400 hover:bg-emerald-500 hover:text-black font-mono text-xs uppercase py-2 rounded-lg transition-all shadow-[0_0_10px_rgba(16,185,129,0.2)] disabled:opacity-50"
        >
          {chat.isScanning ? "Scanning..." : "Scan Directory"}
        </button>
      {:else}
        <div class="flex flex-col gap-1">
          <button
            onclick={() => chat.scanCodebase()}
            disabled={chat.isScanning}
            class="w-full bg-yellow-900/30 border border-yellow-500 text-yellow-400 hover:bg-yellow-500 hover:text-black font-mono text-xs uppercase py-2 rounded-lg transition-all shadow-[0_0_10px_rgba(234,179,8,0.3)] disabled:opacity-50"
          >
            {chat.isScanning ? "Updating Context..." : "Update Codebase"}
          </button>
          <span class="text-[8px] text-gray-500 text-center uppercase"
            >Bấm để đồng bộ Ignore List lên Backend</span
          >
        </div>
      {/if}

      <div
        class="flex-1 mt-2 bg-black/30 border border-gray-800 rounded-lg p-2 overflow-y-auto custom-scrollbar"
      >
        {#if chat.codeTree}
          <div class="text-[9px] font-mono text-gray-500 uppercase mb-2">
            Tích chéo (X) để bỏ qua thư mục/file
          </div>
          <CodeNode node={chat.codeTree} {chat} />
        {:else}
          <div
            class="h-full flex flex-col items-center justify-center text-[10px] font-mono text-gray-600 uppercase text-center p-4"
          >
            <span>Chưa có dữ liệu Codebase.</span>
          </div>
        {/if}
      </div>
    </div>
  {:else}
    <h2
      class="text-[10px] font-bold text-cyan-400 mb-6 uppercase tracking-[0.2em] flex items-center gap-2"
    >
      <div class="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></div>
       Cốt lõi hệ thống
    </h2>
    <div class="space-y-4 text-sm font-mono">
      <div
        class="p-3 bg-gray-900/60 rounded-xl border border-cyan-900/50 flex flex-col gap-1 relative overflow-hidden"
      >
        <div
          class="absolute top-0 left-0 w-full h-[1px] bg-gradient-to-r from-transparent via-cyan-500 to-transparent opacity-50"
        ></div>
        <span class="text-gray-500 text-[10px] uppercase">Engine</span>
        <span class="text-cyan-300 font-medium">QWEN_3.5_2B</span>
      </div>
      <div
        class="p-3 bg-gray-900/60 rounded-xl border border-yellow-900/50 flex flex-col gap-1"
      >
        <span class="text-gray-500 text-[10px] uppercase">Active Tool</span>
        <span class="text-yellow-400/90 font-medium animate-pulse"
          >IDLE_MODE</span
        >
      </div>
    </div>
  {/if}
</aside>
