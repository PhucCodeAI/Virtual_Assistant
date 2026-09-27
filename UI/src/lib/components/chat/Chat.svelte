<script lang="ts">
  import { agentSession } from '$lib/state/agent_session.svelte';
  import MarkdownRenderer from './MarkdownRenderer.svelte';
  
  let userInput = $state('');
  let textareaRef: HTMLTextAreaElement | null = $state(null);

  function submitCurrentPrompt() {
    if (!userInput.trim() || agentSession.isStreaming) return;
    const prompt = userInput.trim();
    userInput = '';
    agentSession.sendPrompt(prompt);
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.isComposing) return;

    if (e.key === 'Enter') {
      if (e.ctrlKey) {
        e.preventDefault();
        const target = e.currentTarget as HTMLTextAreaElement;
        const start = target.selectionStart;
        const end = target.selectionEnd;
        userInput = userInput.substring(0, start) + '\n' + userInput.substring(end);
        
        queueMicrotask(() => {
          target.selectionStart = target.selectionEnd = start + 1;
        });
        return;
      }

      if (!e.shiftKey) {
        e.preventDefault();
        submitCurrentPrompt();
      }
    }
  }

  function handleCancel() {
    agentSession.abortCurrentSession();
  }
</script>

<div class="flex flex-col h-full bg-[#18181b] text-zinc-200">
  <div class="px-3 py-2.5 border-b border-[#27272a] bg-[#141417] flex items-center justify-between gap-2 overflow-x-auto text-[11px] font-mono shrink-0 select-none">
    <div class="flex items-center gap-1.5 shrink-0">
      <span class="w-2 h-2 rounded-full {agentSession.isStreaming ? 'bg-amber-400 animate-pulse' : 'bg-emerald-500'}"></span>
      <span class="font-medium text-zinc-300 font-sans text-xs">Orchestrator</span>
    </div>

    <div class="flex items-center gap-1.5 shrink-0">
      <div class="px-2 py-0.5 rounded bg-[#1f1f23] border border-[#2c2c31] text-zinc-400">
        in: <span class="text-zinc-200 font-semibold">{agentSession.cumulativeMetrics.inputTokens.toLocaleString()}</span>
      </div>
      <div class="px-2 py-0.5 rounded bg-[#1f1f23] border border-[#2c2c31] text-zinc-400">
        out: <span class="text-zinc-200 font-semibold">{agentSession.cumulativeMetrics.outputTokens.toLocaleString()}</span>
      </div>
      <div class="px-2 py-0.5 rounded bg-[#1f1f23] border border-[#2c2c31] text-zinc-400">
        reason: <span class="text-amber-400 font-semibold">{agentSession.cumulativeMetrics.reasoningTokens.toLocaleString()}</span>
      </div>
      <div class="px-2 py-0.5 rounded bg-[#1f1f23] border border-[#2c2c31] text-zinc-400">
        cache: <span class="text-sky-400 font-semibold">{agentSession.cumulativeMetrics.cachedTokens.toLocaleString()}</span>
      </div>
      <div class="px-2 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-semibold">
        ${agentSession.cumulativeMetrics.cost.toFixed(4)}
      </div>
    </div>
  </div>

  <div class="flex-1 overflow-y-auto p-4 space-y-5">
    {#each agentSession.messages as msg (msg.id)}
      {#if msg.role === 'user'}
        <div class="flex flex-col items-end w-full">
          <div class="max-w-[92%] rounded-lg px-3 py-2 bg-[#1f1f23] border border-[#2f2f35] text-zinc-100 text-xs shadow-sm">
            <div class="flex items-center gap-1.5 mb-1 text-[10px] text-zinc-500 font-mono uppercase tracking-wider">
              <span>Prompt</span>
              <span>•</span>
              <span>{msg.timestamp}</span>
            </div>
            <p class="whitespace-pre-wrap leading-relaxed font-sans">{msg.content}</p>
          </div>
        </div>
      {:else}
        <div class="flex flex-col items-start space-y-2">
          {#if msg.actions && msg.actions.length > 0}
            <div class="space-y-1 font-mono text-[11px] w-full">
              {#each msg.actions as act (act.id)}
                <div class="flex items-center gap-2 px-2.5 py-1 rounded bg-[#1f1f23] border border-[#2c2c31]">
                  <span class="text-emerald-400">✓</span>
                  <span class="text-zinc-300 truncate">{act.label}</span>
                  <span class="text-zinc-600 text-[10px] ml-auto shrink-0">{act.timestamp}</span>
                </div>
              {/each}
            </div>
          {/if}

          <div class="w-full p-3.5 rounded-xl bg-[#141416] border border-[#27272a]">
            <MarkdownRenderer content={msg.content} />
          </div>

          {#if msg.latencyMs}
            <div class="flex items-center gap-1.5 text-[10px] font-mono text-zinc-500 ml-1">
              <span>Latency:</span>
              <span class="text-amber-400 font-semibold">{(msg.latencyMs / 1000).toFixed(2)}s</span>
              <span>•</span>
              <span>{msg.timestamp}</span>
            </div>
          {/if}
        </div>
      {/if}
    {/each}

    {#if agentSession.isStreaming}
      <div class="flex flex-col items-start space-y-2">
        {#if agentSession.actions.length > 0}
          <div class="space-y-1 font-mono text-[11px] w-full">
            {#each agentSession.actions as act (act.id)}
              <div class="flex items-center gap-2 px-2.5 py-1 rounded bg-[#1f1f23] border border-[#2c2c31]">
                {#if act.status === 'running'}
                  <span class="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping"></span>
                {:else if act.status === 'success'}
                  <span class="text-emerald-400 text-xs">✓</span>
                {:else}
                  <span class="text-rose-400 text-xs">✗</span>
                {/if}
                <span class="text-zinc-300 truncate">{act.label}</span>
                <span class="text-zinc-600 text-[10px] ml-auto shrink-0">{act.timestamp}</span>
              </div>
            {/each}
          </div>
        {/if}

        {#if agentSession.streamingMessage}
          <div class="w-full p-3.5 rounded-xl bg-[#141416] border border-amber-500/30 shadow-sm">
            <MarkdownRenderer content={agentSession.streamingMessage} />
          </div>
        {/if}
      </div>
    {/if}

    {#if agentSession.messages.length === 0 && !agentSession.isStreaming}
      <div class="flex flex-col items-center justify-center h-48 text-zinc-500 text-xs text-center space-y-1">
        <p class="font-medium text-zinc-400">Claude-Style Orchestrator</p>
        <p class="text-[11px]">Bấm <kbd class="px-1 py-0.5 bg-zinc-800 rounded font-mono text-zinc-300">Enter</kbd> để gửi lệnh, <kbd class="px-1 py-0.5 bg-zinc-800 rounded font-mono text-zinc-300">Ctrl + Enter</kbd> để xuống dòng.</p>
      </div>
    {/if}
  </div>

  <div class="p-3 border-t border-[#27272a] bg-[#141417]">
    <div class="relative bg-[#1c1c20] border border-[#303036] rounded-xl focus-within:border-amber-500/60 transition-colors">
      <textarea
        bind:this={textareaRef}
        bind:value={userInput}
        onkeydown={handleKeyDown}
        placeholder={agentSession.isStreaming ? "Agent đang giải trình và kiểm thử code..." : "Nhập chỉ thị (Enter để gửi, Ctrl + Enter để xuống dòng)..."}
        disabled={agentSession.isStreaming}
        rows="2"
        class="w-full bg-transparent px-3 py-2 text-xs focus:outline-none resize-none text-zinc-200 placeholder-zinc-500 disabled:opacity-50"
      ></textarea>
      
      <div class="flex items-center justify-between px-3 py-1.5 border-t border-[#26262b] text-xs select-none">
        <div class="flex items-center gap-1.5 text-zinc-500 font-mono text-[10px]">
          <span>Target:</span>
          <span class="text-zinc-300 bg-zinc-800 px-1 rounded">{agentSession.activeFile}</span>
        </div>

        <div class="flex items-center gap-2">
          {#if agentSession.isStreaming}
            <button
              type="button"
              onclick={handleCancel}
              class="px-3 py-1 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 border border-rose-500/40 font-semibold rounded text-[11px] transition-colors"
            >
              Stop Agent
            </button>
          {:else}
            <button
              type="button"
              onclick={submitCurrentPrompt}
              disabled={!userInput.trim()}
              class="px-3 py-1 bg-amber-500 hover:bg-amber-400 disabled:opacity-40 disabled:hover:bg-amber-500 text-zinc-950 font-semibold rounded text-[11px] transition-colors cursor-pointer"
            >
              Send Instruction
            </button>
          {/if}
        </div>
      </div>
    </div>
  </div>
</div>