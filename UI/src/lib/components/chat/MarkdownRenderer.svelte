<script lang="ts">
  import { highlightCode } from './highlighter';

  let { content = '' }: { content: string } = $props();
  let copiedId = $state<string | null>(null);

  interface Block {
    type: 'code' | 'text';
    lang?: string;
    text: string;
    id: string;
  }

  let parsedBlocks = $derived.by<Block[]>(() => {
    if (!content) return [];
    const blocks: Block[] = [];
    const regex = /```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = regex.exec(content)) !== null) {
      if (match.index > lastIndex) {
        blocks.push({
          type: 'text',
          text: content.slice(lastIndex, match.index),
          id: `txt-${lastIndex}`
        });
      }
      blocks.push({
        type: 'code',
        lang: match[1] || 'plaintext',
        text: match[2].trimEnd(),
        id: `code-${match.index}`
      });
      lastIndex = regex.lastIndex;
    }

    if (lastIndex < content.length) {
      blocks.push({
        type: 'text',
        text: content.slice(lastIndex),
        id: `txt-${lastIndex}`
      });
    }

    return blocks;
  });

  function formatInline(text: string): string {
    let escaped = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');

    escaped = escaped.replace(/^---$/gm, '<hr class="border-[#27272a] my-4" />');

    escaped = escaped.replace(/^### (.*$)/gim, '<h3 class="text-xs font-semibold text-zinc-200 mt-3 mb-1 tracking-wide uppercase font-mono">$1</h3>');
    escaped = escaped.replace(/^## (.*$)/gim, '<h2 class="text-sm font-semibold text-zinc-100 mt-3 mb-1.5 font-sans">$1</h2>');
    escaped = escaped.replace(/^# (.*$)/gim, '<h1 class="text-base font-bold text-zinc-100 mt-4 mb-2 font-sans">$1</h1>');

    escaped = escaped.replace(/^(\d+)\.\s+(.*$)/gim, '<div class="flex items-center gap-2 mt-3 mb-1.5"><span class="font-mono text-amber-400 font-bold">$1.</span><span class="font-semibold text-zinc-200">$2</span></div>');

    escaped = escaped.replace(/^\s*[-*]\s+(.*$)/gim, '<li class="ml-4 list-disc text-zinc-300 my-0.5">$1</li>');

    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-zinc-100">$1</strong>');

    escaped = escaped.replace(/\*([^*\n]+)\*/g, '<em class="italic text-zinc-400">$1</em>');

    escaped = escaped.replace(/`([^`\n]+)`/g, '<code class="px-1.5 py-0.5 bg-[#202023] text-amber-300 rounded border border-[#2e2e33] font-mono text-[11px]">$1</code>');

    escaped = escaped.replace(/\n\n+/g, '<div class="h-2.5"></div>');
    escaped = escaped.replace(/\n/g, '<br/>');

    return escaped;
  }

  async function copyToClipboard(id: string, text: string) {
    await navigator.clipboard.writeText(text);
    copiedId = id;
    setTimeout(() => (copiedId = null), 1800);
  }
</script>

<div class="space-y-3 text-xs leading-relaxed text-zinc-300 font-sans select-text">
  {#each parsedBlocks as block (block.id)}
    {#if block.type === 'code'}
      {@const highlighted = highlightCode(block.text)}
      {@const lineCount = block.text.split('\n').length}

      <div class="rounded-lg overflow-hidden border border-[#2a2a2e] bg-[#0f0f11] my-3.5 shadow-xl font-mono">
        <div class="flex items-center justify-between px-3 py-1.5 bg-[#161618] border-b border-[#242428] text-[11px] text-zinc-400 select-none">
          <div class="flex items-center gap-2">
            <span class="w-2 h-2 rounded-full bg-zinc-600"></span>
            <span class="text-zinc-300 font-semibold lowercase tracking-wider">{block.lang || 'code'}</span>
          </div>

          <button
            type="button"
            onclick={() => copyToClipboard(block.id, block.text)}
            class="flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] bg-[#222226] hover:bg-[#2b2b30] text-zinc-300 border border-[#303036] transition-all cursor-pointer"
          >
            {#if copiedId === block.id}
              <span class="text-emerald-400 font-medium">Copied ✓</span>
            {:else}
              <svg class="w-3 h-3 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
              <span>Copy</span>
            {/if}
          </button>
        </div>

        <div class="flex text-[12px] leading-5 overflow-x-auto py-2.5 font-mono">
          <div class="select-none text-right pr-3 pl-3 text-zinc-600 border-r border-[#202024] shrink-0 font-mono text-[11px]">
            {#each Array(lineCount) as _, i}
              <div class="leading-5">{i + 1}</div>
            {/each}
          </div>

          <pre class="pl-3.5 pr-4 text-zinc-200 whitespace-pre overflow-x-visible leading-5 font-mono"><code>{@html highlighted}</code></pre>
        </div>
      </div>
    {:else}
      <div class="leading-relaxed">
        {@html formatInline(block.text)}
      </div>
    {/if}
  {/each}
</div>