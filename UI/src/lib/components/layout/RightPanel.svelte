<script lang="ts">
  import type { ChatService } from "$lib/state/chat.svelte";

  let { chat }: { chat: ChatService } = $props();
</script>

<!-- Đổi w-[28%] thành w-[20%] min-w-[240px] để chiếm đúng 20% tỉ lệ màn hình -->
<aside
  class="w-[20%] min-w-[240px] glass-panel m-4 rounded-2xl p-5 flex flex-col gap-6 custom-scrollbar overflow-y-auto border-r-4 border-r-purple-500/50"
>
  <section>
    <h2
      class="text-[10px] font-bold text-purple-400 uppercase tracking-[0.2em] mb-4 flex items-center gap-2"
    >
      <svg
        class="w-4 h-4 animate-spin-slow"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        ><circle cx="12" cy="12" r="10" stroke-dasharray="4 4" /></svg
      > Thống kê phần cứng
    </h2>
    <div class="space-y-4 bg-black/30 p-4 rounded-xl border border-gray-800">
      <div>
        <div
          class="flex justify-between text-[10px] font-mono text-gray-500 mb-1 uppercase"
        >
          <span>CPU</span><span class="text-cyan-400"
            >{chat.metrics.cpu.toFixed(1)}%</span
          >
        </div>
        <div class="w-full bg-gray-900 rounded-full h-1 overflow-hidden">
          <div
            class="{chat.metrics.cpu > 80
              ? 'bg-red-500 shadow-[0_0_8px_red]'
              : 'bg-cyan-500 shadow-[0_0_8px_cyan]'} h-full transition-all duration-500"
            style="width: {chat.metrics.cpu}%"
          ></div>
        </div>
      </div>
      <div>
        <div
          class="flex justify-between text-[10px] font-mono text-gray-500 mb-1 uppercase"
        >
          <span>RAM</span><span class="text-emerald-400"
            >{chat.metrics.ram.toFixed(1)} GB</span
          >
        </div>
        <div class="w-full bg-gray-900 rounded-full h-1 overflow-hidden">
          <div
            class="bg-emerald-500 shadow-[0_0_8px_#10b981] h-full transition-all duration-500"
            style="width: {(chat.metrics.ram / 32) * 100}%"
          ></div>
        </div>
      </div>
      <div>
        <div
          class="flex justify-between text-[10px] font-mono text-gray-500 mb-1 uppercase"
        >
          <span>GPU_VRAM</span><span
            class={chat.metrics.gpu_vram > 5.5
              ? "text-red-400 animate-pulse"
              : "text-purple-400"}>{chat.metrics.gpu_vram.toFixed(1)} GB</span
          >
        </div>
        <div class="w-full bg-gray-900 rounded-full h-1 overflow-hidden">
          <div
            class="{chat.metrics.gpu_vram > 5.5
              ? 'bg-red-500'
              : 'bg-purple-500 shadow-[0_0_8px_#a855f7]'} h-full transition-all duration-500"
            style="width: {(chat.metrics.gpu_vram / 6) * 100}%"
          ></div>
        </div>
      </div>
    </div>
    <!-- CẬP NHẬT: PHÂN CHIA HỆ THỐNG ĐO LƯỜNG SỦ DỤNG GRID 2 CỘT [5] -->
    <div class="mt-4 grid grid-cols-2 gap-3 relative overflow-hidden group">
      <!-- Cột trái: Tốc độ Generation hiện tại -->
      <div
        class="p-3 bg-gradient-to-br from-cyan-900/20 to-transparent rounded-xl border border-cyan-900/50 text-center relative overflow-hidden transition-all duration-300 hover:border-cyan-500/40"
      >
        <div
          class="text-cyan-600/70 text-[9px] uppercase font-mono tracking-wider mb-1"
        >
          Throughput
        </div>
        <div
          class="text-lg font-mono font-bold text-cyan-300 neon-text-cyan flex justify-center items-baseline gap-1"
        >
          {chat.metrics.throughput}
          <span class="text-[9px] text-cyan-600/50 font-sans font-normal"
            >T/S</span
          >
        </div>
      </div>

      <!-- Cột phải: Tổng số token lũy kế toàn session -->
      <div
        class="p-3 bg-gradient-to-br from-purple-900/20 to-transparent rounded-xl border border-purple-900/50 text-center relative overflow-hidden transition-all duration-300 hover:border-purple-500/40"
      >
        <div
          class="text-purple-600/70 text-[9px] uppercase font-mono tracking-wider mb-1"
        >
          Total_Tokens
        </div>
        <div
          class="text-lg font-mono font-bold text-purple-300 flex justify-center items-baseline gap-1"
        >
          {chat.totalTokens}
          <span class="text-[9px] text-purple-600/50 font-sans font-normal"
            >T</span
          >
        </div>
      </div>
    </div>
  </section>

  <div class="flex flex-col gap-2 mb-4">
    <label
      class="text-[10px] font-bold text-pink-700 uppercase tracking-[0.2em] mb-4"
      >Chế độ</label
    >
    <select
      bind:value={chat.mode}
      onchange={chat.handleModeChange}
      class="w-full bg-black/50 border border-gray-700 rounded-lg p-2 text-sm text-cyan-100 font-mono focus:border-cyan-500 outline-none cursor-pointer appearance-none"
    >
      <option value="chat">Trò chuyện</option>
      <option value="coding">Viết mã</option>
      <option value="research">Nghiên cứu</option>
      <option value="analysis">Phân tích</option>
    </select>
  </div>

  <section>
    <h2
      class="text-[10px] font-bold text-emerald-400 uppercase tracking-[0.2em] mb-4"
    >
      Dữ liệu Huấn luyện
    </h2>
    <div class="grid grid-cols-2 gap-3">
      <div
        class="p-3 bg-black/40 rounded-xl border border-emerald-900/50 flex flex-col items-center"
      >
        <span class="text-[9px] font-mono text-gray-500 uppercase">SFT</span
        ><span class="text-xl font-mono text-emerald-400"
          >{chat.datasetStats.sft}</span
        >
      </div>
      <div
        class="p-3 bg-black/40 rounded-xl border border-purple-900/50 flex flex-col items-center"
      >
        <span class="text-[9px] font-mono text-gray-500 uppercase">DPO</span
        ><span class="text-xl font-mono text-purple-400"
          >{chat.datasetStats.dpo}</span
        >
      </div>
    </div>
  </section>

  <section>
    <h2
      class="text-[10px] font-bold text-yellow-500/80 uppercase tracking-[0.2em] mb-4"
    >
      Tham số mô hình
    </h2>
    <div
      class="flex flex-col gap-4 p-4 bg-black/30 rounded-xl border border-gray-800"
    >
      <div class="flex flex-col gap-2">
        <div class="flex justify-between text-[10px] font-mono text-gray-500">
          <span>Temp</span><span class="text-cyan-400"
            >{chat.temperature.toFixed(2)}</span
          >
        </div>
        <input
          type="range"
          min="0"
          max="2"
          step="0.05"
          bind:value={chat.temperature}
          class="w-full accent-cyan-500 h-0.5 bg-gray-800 appearance-none"
        />
      </div>
      <div class="flex flex-col gap-2">
        <div class="flex justify-between text-[10px] font-mono text-gray-500">
          <span>Top_P</span><span class="text-cyan-400"
            >{chat.topP.toFixed(2)}</span
          >
        </div>
        <input
          type="range"
          min="0.05"
          max="1"
          step="0.05"
          bind:value={chat.topP}
          class="w-full accent-cyan-500 h-0.5 bg-gray-800 appearance-none"
        />
      </div>
    </div>
    {#if chat.mode === "chat"}
      <div class="mt-4 flex flex-col gap-2">
        <label class="text-[9px] font-mono text-gray-500 uppercase"
          >System Prompt</label
        >
        <textarea
          bind:value={chat.systemPrompt}
          rows="3"
          class="w-full bg-black/50 border border-gray-800 rounded-xl p-3 text-xs font-mono text-yellow-100/70 focus:border-yellow-500/50 outline-none resize-y custom-scrollbar"
          placeholder="// Enter root directive..."
        ></textarea>
      </div>
    {/if}
  </section>
</aside>
