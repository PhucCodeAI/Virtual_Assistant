<script lang="ts">
  import type { ChatService } from "$lib/state/chat.svelte";
  import type { Message } from "$lib/state/types";

  let { msg, index, chat }: { msg: Message; index: number; chat: ChatService } =
    $props();

  // BỘ PARSER MARKDOWN SCI-FI SIÊU NHẸ (BẢO VỆ HIỆU NĂNG)
  function renderMarkdown(text: string): string {
    if (!text) return "";
    let html = text;

    // Tránh lỗ hổng bảo mật XSS cơ bản trước khi chèn HTML custom
    html = html
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");

    // 1. Render Code Blocks mượt mà
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (match, lang, code) => {
      return `<div class="my-3 rounded-lg overflow-hidden border border-cyan-500/30 bg-[#0a0f1a] shadow-lg animate-fade-in">
                <div class="bg-cyan-900/30 px-4 py-1 text-[10px] font-mono text-cyan-400 uppercase tracking-widest border-b border-cyan-500/30 flex justify-between items-center">
                  <span>${lang || "CODE"}</span><span class="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse"></span>
                </div>
                <pre class="p-4 overflow-x-auto custom-scrollbar text-cyan-100 text-xs font-mono leading-relaxed">${code}</pre>
              </div>`;
    });

    // 2. Render Inline Code
    html = html.replace(
      /`([^`]+)`/g,
      '<code class="bg-cyan-950/50 text-cyan-300 font-mono text-xs px-1.5 py-0.5 rounded border border-cyan-500/20">$1</code>',
    );

    // 3. Render Tiêu đề (Headers)
    html = html.replace(
      /^### (.*$)/gim,
      '<h3 class="text-sm font-bold text-cyan-300 font-mono mt-4 mb-2 uppercase tracking-wider">$1</h3>',
    );
    html = html.replace(
      /^## (.*$)/gim,
      '<h2 class="text-base font-bold text-cyan-400 font-mono mt-5 mb-3 uppercase tracking-wider border-b border-cyan-900/30 pb-1">$1</h2>',
    );
    html = html.replace(
      /^# (.*$)/gim,
      '<h1 class="text-lg font-bold text-cyan-400 font-mono mt-6 mb-4 uppercase tracking-widest border-b border-cyan-500/30 pb-2 shadow-sm">$1</h1>',
    );

    // 4. Render Bôi đậm và In nghiêng
    html = html.replace(
      /\*\*([^*]+)\*\*/g,
      '<strong class="text-cyan-300 font-bold">$1</strong>',
    );
    html = html.replace(
      /\*([^*]+)\*/g,
      '<em class="text-gray-300 italic">$1</em>',
    );

    // 5. Render Danh sách không thứ tự (Unordered Lists) - Custom Bullet
    const lines = html.split("\n");
    let inList = false;
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line.startsWith("- ") || line.startsWith("* ")) {
        const content = line.substring(2);
        let replacement = `<li class="flex items-start gap-2 text-gray-300 text-xs my-1 font-sans">
            <span class="text-cyan-500 text-[10px] mt-1 flex-shrink-0 animate-pulse">✦</span>
            <span>${content}</span>
        </li>`;
        if (!inList) {
          replacement = '<ul class="my-2 space-y-1 pl-1">' + replacement;
          inList = true;
        }
        lines[i] = replacement;
      } else {
        if (inList) {
          lines[i] = "</ul>" + lines[i];
          inList = false;
        }
      }
    }
    if (inList) lines[lines.length - 1] += "</ul>";
    html = lines.join("\n");

    // 6. Ngắt dòng mượt mà
    html = html.replace(/\n$/gim, "<br />");

    return html;
  }
</script>

<div
  class="flex flex-col {msg.role === 'user'
    ? 'items-end'
    : 'items-start'} w-full"
>
  <div
    class="p-4 rounded-2xl {msg.role === 'user'
      ? 'max-w-[85%] bg-cyan-900/40 border border-cyan-500/50 text-cyan-50'
      : msg.isEditing
        ? 'w-full max-w-none border-l-4 border-l-purple-500/60 bg-black/25'
        : 'w-full max-w-4xl glass-panel text-gray-300'} relative transition-all duration-300"
  >
    {#if msg.image}
      <img
        src={msg.image}
        alt="Upload"
        class="max-w-md w-full h-auto rounded-xl mb-3 border border-cyan-500/30"
      />
    {/if}

    {#if msg.role === "assistant" && msg.content === "" && !msg.codingPlan && chat.isLoading}
      <div class="flex items-center gap-3 py-2 px-1">
        <div class="flex space-x-1">
          <div
            class="w-1.5 h-4 bg-cyan-400 rounded-full animate-[bounce_1s_infinite]"
          ></div>
          <div
            class="w-1.5 h-4 bg-purple-400 rounded-full animate-[bounce_1s_infinite_0.2s]"
          ></div>
          <div
            class="w-1.5 h-4 bg-cyan-400 rounded-full animate-[bounce_1s_infinite_0.4s]"
          ></div>
        </div>
        <span
          class="text-cyan-400 text-xs font-mono tracking-widest uppercase neon-text-cyan animate-pulse"
          >Đang suy nghĩ...</span
        >
      </div>
    {:else if msg.role === "assistant" && msg.isEditing}
      <div class="flex flex-col w-full animate-fade-in">
        <div class="flex items-center gap-2 mb-3">
          <span
            class="text-[9px] text-purple-400 uppercase tracking-widest font-mono border border-purple-800/50 px-2 py-0.5 rounded bg-purple-950/30 animate-pulse"
            >Edit Mode (DPO Override)</span
          >
        </div>
        <textarea
          bind:value={msg.editContent}
          class="w-full bg-[#030712]/90 text-cyan-100 font-mono text-sm p-4 rounded-xl border border-purple-500 focus:border-purple-400 focus:shadow-[0_0_15px_rgba(168,85,247,0.2)] focus:outline-none min-h-[50vh] max-h-[65vh] overflow-y-auto custom-scrollbar resize-none transition-all duration-300"
        ></textarea>
        <div class="flex gap-3 mt-4 justify-end">
          <button
            onclick={() => (msg.isEditing = false)}
            class="text-xs font-mono uppercase px-4 py-2 border border-gray-600 text-gray-400 hover:text-white rounded-lg transition-colors"
            >Abort</button
          >
          <button
            onclick={() => chat.updateDataset(index, "edited")}
            class="text-xs font-mono uppercase px-4 py-2 bg-purple-600/50 border border-purple-500 text-purple-100 hover:bg-purple-500 rounded-lg transition-colors shadow-[0_0_10px_rgba(168,85,247,0.4)]"
            >Override (DPO)</button
          >
        </div>
      </div>
    {:else if msg.codingPlan}
      <div class="flex flex-col w-full font-sans animate-fade-in">
        <div
          class="relative bg-cyan-950/20 border-l-4 border-cyan-500 p-5 rounded-r-2xl mb-8 shadow-[inset_4px_0_0_rgba(34,211,238,0.4)] overflow-hidden group"
        >
          <div
            class="absolute top-0 right-0 w-32 h-full bg-gradient-to-l from-cyan-500/10 to-transparent transform translate-x-full group-hover:translate-x-0 transition-transform duration-700"
          ></div>
          <div class="flex items-start gap-3">
            <svg
              class="w-5 h-5 text-cyan-400 flex-shrink-0 mt-1 animate-pulse"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              ><path
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              ></path></svg
            >
            <div>
              <span
                class="text-[10px] text-cyan-500 uppercase tracking-[0.2em] font-mono block mb-1"
                >Planing Agent</span
              >
              <p class="text-cyan-50 text-sm leading-relaxed tracking-wide">
                {msg.codingPlan.desc}
              </p>
            </div>
          </div>
        </div>
        <div
          class="relative before:absolute before:inset-y-2 before:left-[19px] before:w-[2px] before:bg-gradient-to-b before:from-cyan-500/50 before:via-purple-500/30 before:to-transparent space-y-6"
        >
          {#each msg.codingPlan.steps as step (step.step)}
            <div
              class="relative pl-14 group transition-transform duration-300 hover:translate-x-1"
            >
              <div
                class="absolute left-0 top-1 w-10 h-10 rounded-full bg-[#030712] border-2 border-cyan-800 flex items-center justify-center z-10 shadow-[0_0_10px_rgba(0,0,0,0.5)] group-hover:border-cyan-400 group-hover:shadow-[0_0_15px_rgba(34,211,238,0.4)] transition-all duration-300"
              >
                <span
                  class="text-xs font-mono font-bold text-gray-500 group-hover:text-cyan-300"
                  >{step.step < 10 ? `0${step.step}` : step.step}</span
                >
              </div>
              <div
                class="bg-gray-900/40 backdrop-blur-md border border-gray-700/50 group-hover:border-cyan-500/40 rounded-2xl p-5 transition-colors shadow-lg"
              >
                <div class="flex items-start gap-2 mb-3">
                  <span
                    class="text-[9px] text-cyan-600 uppercase tracking-widest font-mono mt-1 border border-cyan-800/50 px-1.5 py-0.5 rounded bg-cyan-950/30"
                    >Hành động</span
                  >
                  <h3 class="text-cyan-100 font-semibold text-sm leading-snug">
                    {step.action}
                  </h3>
                </div>
                <div
                  class="ml-2 pl-4 border-l-2 border-purple-500/30 group-hover:border-purple-400/60 transition-colors relative"
                >
                  <div
                    class="absolute -left-[2px] top-0 w-2 h-2 border-b-2 border-l-2 border-purple-500/30 group-hover:border-purple-400/60 rounded-bl-md"
                  ></div>
                  <span
                    class="text-[9px] text-purple-400/70 uppercase tracking-widest font-mono block mb-1"
                    >Mục tiêu</span
                  >
                  <p class="text-gray-400 font-mono text-xs leading-relaxed">
                    {step.target}
                  </p>
                </div>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {:else}
      <!-- CẬP NHẬT: Render qua bộ Custom Markdown Editor gọn nhẹ thay cho hàm regex cũ -->
      <div class="whitespace-pre-wrap leading-relaxed text-sm">
        {@html msg.role === "assistant"
          ? renderMarkdown(msg.content)
          : msg.content}
      </div>
    {/if}
  </div>

  {#if msg.role === "assistant" && msg.db_id && !msg.isEditing && (msg.content !== "" || msg.codingPlan)}
    <div class="flex items-center justify-between mt-2 ml-2 w-full max-w-4xl">
      <div class="flex gap-4 text-[10px] font-mono uppercase tracking-wider">
        {#if msg.status === "pending"}
          <button
            onclick={() => chat.updateDataset(index, "approved")}
            class="text-emerald-500 hover:text-emerald-300 transition-colors"
            >✓ Sync_SFT</button
          >
          <button
            onclick={() => {
              msg.isEditing = true;
              msg.editContent = msg.codingPlan
                ? JSON.stringify(msg.codingPlan, null, 2)
                : msg.content;
            }}
            class="text-purple-400 hover:text-purple-300 transition-colors"
            >✎ Edit_DPO</button
          >
          <button
            onclick={() => chat.updateDataset(index, "discarded")}
            class="text-red-500/70 hover:text-red-400 transition-colors"
            >✕ Purge</button
          >
        {:else if msg.status === "approved"}
          <span class="text-emerald-500/50">✓ SFT_Synchronized</span>
        {:else if msg.status === "edited"}
          <span class="text-purple-500/50">✓ DPO_Overridden</span>
        {:else if msg.status === "discarded"}
          <span class="text-red-500/50 line-through">✕ Data_Purged</span>
        {/if}
      </div>

      <!-- CẬP NHẬT: BADGE METRICS ĐỒNG BỘ 3 TRƯỜNG (TOKENS, THỜI GIAN, TỐC ĐỘ GENERATE) [2] -->
      {#if msg.generated_tokens || msg.elapsed_time_sec}
        <div
          class="flex items-center gap-2 px-3 py-1 bg-cyan-950/40 border border-cyan-800/50 rounded-lg text-[9px] font-mono text-cyan-400 uppercase tracking-widest shadow-[0_0_8px_rgba(6,182,212,0.1)]"
        >
          {#if msg.generated_tokens}
            <div class="flex items-center gap-0.5">
              <span class="text-cyan-600 font-bold">[</span>
              <span class="text-cyan-500">GEN TOKEN:</span>
              <span class="text-cyan-300">{msg.generated_tokens}T</span>
              <span class="text-cyan-600 font-bold">]</span>
            </div>
          {/if}

          {#if msg.elapsed_time_sec}
            <div class="flex items-center gap-0.5 ml-1">
              <span class="text-cyan-600 font-bold">[</span>
              <span class="text-purple-400">TIME:</span>
              <span class="text-purple-300"
                >{msg.elapsed_time_sec.toFixed(2)}s</span
              >
              <span class="text-cyan-600 font-bold">]</span>
            </div>
          {/if}

          {#if msg.context_length && msg.elapsed_time_sec}
            <div class="flex items-center gap-0.5 ml-1 text-emerald-400">
              <span class="text-cyan-600 font-bold">[</span>
              <span class="text-emerald-500">SPEED:</span>
              <span
                >{((msg.generated_tokens || 0) / msg.elapsed_time_sec).toFixed(
                  1,
                )}T/S</span
              >
              <span class="text-cyan-600 font-bold">]</span>
            </div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
</div>
