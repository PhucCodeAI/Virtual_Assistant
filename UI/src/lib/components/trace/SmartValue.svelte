<script lang="ts">
  // Dispatcher thông minh cho value trong Span Detail.
  //
  // Heuristic pickRenderer (ưu tiên từ trên xuống):
  //   - array{role,content}          → messages
  //   - array{path,...}              → filelist
  //   - array<string> + key command  → command
  //   - string + key stdout/stderr/log → terminal
  //   - string + key code/diff/source → code
  //   - string + key text / dài / multi-line → text
  //   - plain object                 → expand đệ quy (depth <= 3)
  //   - còn lại                      → json fallback
  //
  // Svelte 5 KHÔNG cho self-import component → recursion qua snippet.
  //
  // Palette: dùng theme.ts để đảm bảo contrast nhất quán.

  import JsonBlock from './JsonBlock.svelte';
  import CommandRenderer from './CommandRenderer.svelte';
  import TerminalRenderer from './TerminalRenderer.svelte';
  import CodeRenderer from './CodeRenderer.svelte';
  import MessagesRenderer from './MessagesRenderer.svelte';
  import FileListRenderer from './FileListRenderer.svelte';
  import TextRenderer from './TextRenderer.svelte';

  let {
    label,
    value,
    depth = 0,
  }: {
    label: string;
    value: unknown;
    depth?: number;
  } = $props();

  const MAX_DEPTH = 3;

  // Key gợi ý nội dung là text tự nhiên (không phải code/log).
  const TEXT_KEYS = [
    'explanation', 'content', 'message', 'description', 'summary',
    'text', 'reasoning', 'thought', 'prompt', 'note', 'comment',
    'answer', 'response', 'output',
  ];

  let mode = $state<'smart' | 'json'>('smart');

  function isPrimitive(x: unknown): boolean {
    return x === null || x === undefined || typeof x !== 'object';
  }

  function isPlainObject(x: unknown): x is Record<string, unknown> {
    return typeof x === 'object' && x !== null && !Array.isArray(x);
  }

  function isStringArray(x: unknown): x is string[] {
    return Array.isArray(x) && x.length > 0 && x.every((v) => typeof v === 'string');
  }

  function isMessagesArray(x: unknown): boolean {
    if (!Array.isArray(x) || x.length === 0) return false;
    return x.every(
      (m) =>
        typeof m === 'object' &&
        m !== null &&
        'role' in m &&
        'content' in m &&
        typeof (m as Record<string, unknown>).role === 'string',
    );
  }

  function isFileListArray(x: unknown): boolean {
    if (!Array.isArray(x) || x.length === 0) return false;
    return x.every(
      (f) =>
        typeof f === 'object' &&
        f !== null &&
        'path' in f &&
        typeof (f as Record<string, unknown>).path === 'string',
    );
  }

  function isTextKey(key: string): boolean {
    return TEXT_KEYS.includes(key.toLowerCase());
  }

  /** String nên render dạng paragraph? */
  function shouldUseTextRenderer(key: string, val: unknown): boolean {
    if (typeof val !== 'string' || val.length === 0) return false;
    if (isTextKey(key)) return true;
    if (val.includes('\n')) return true;
    if (val.length > 120) return true;
    return false;
  }

  type RendererType =
    | 'messages'
    | 'filelist'
    | 'command'
    | 'terminal'
    | 'code'
    | 'text'
    | 'json';

  function pickRenderer(key: string, val: unknown): RendererType {
    const k = key.toLowerCase();

    if (isMessagesArray(val)) return 'messages';
    if (isFileListArray(val)) return 'filelist';

    if (isStringArray(val)) {
      if (k.includes('command') || k === 'cmd' || k === 'args') return 'command';
      return 'json';
    }

    if (typeof val === 'string' && val.length > 0) {
      // Log output — "stdout"/"stderr"/"log" chứ không phải "output" chung,
      // vì output của LLM thường là câu trả lời tự nhiên.
      if (k.includes('stdout') || k.includes('stderr') || k === 'log') {
        return 'terminal';
      }
      if (k.includes('code') || k === 'diff' || k === 'source') {
        return 'code';
      }
      if (shouldUseTextRenderer(k, val)) return 'text';
    }

    return 'json';
  }

  function primitiveToString(v: unknown): string {
    if (v === null) return 'null';
    if (v === undefined) return 'undefined';
    if (typeof v === 'string') return v;
    if (typeof v === 'number' || typeof v === 'boolean') return String(v);
    return JSON.stringify(v);
  }
</script>

<!-- Recursive snippet: dùng {@render} cho nested objects. -->
{#snippet renderBody(lbl: string, val: unknown, lvl: number)}
  {#if isPrimitive(val)}
    {#if shouldUseTextRenderer(lbl, val)}
      <TextRenderer content={val as string} label={lbl} showLabel={lvl > 0} />
    {:else}
      <div class="flex items-baseline gap-2 text-[12px] font-mono py-0.5 {lvl > 0 ? 'pl-3' : ''}">
        <span class="text-zinc-400 shrink-0">{lbl}:</span>
        <span class="text-zinc-50 break-all">{primitiveToString(val)}</span>
      </div>
    {/if}
  {:else}
    {@const renderer = pickRenderer(lbl, val)}
    {@const shouldExpand =
      renderer === 'json' && isPlainObject(val) && lvl < MAX_DEPTH}

    {#if shouldExpand}
      {@const entries = Object.entries(val as Record<string, unknown>)}
      <div class="space-y-1">
        {#if lvl === 0}
          <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-300 mb-1 font-semibold">
            {lbl}
          </div>
        {:else}
          <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-400 mb-0.5 pl-3 font-semibold">
            {lbl}
          </div>
        {/if}
        {#each entries as [childKey, childVal] (childKey)}
          {@render renderBody(childKey, childVal, lvl + 1)}
        {/each}
      </div>
    {:else if renderer === 'messages' && Array.isArray(val)}
      <MessagesRenderer messages={val as { role: string; content: string }[]} />
    {:else if renderer === 'filelist' && Array.isArray(val)}
      <FileListRenderer files={val as Record<string, unknown>[]} />
    {:else if renderer === 'command' && isStringArray(val)}
      <CommandRenderer parts={val} />
    {:else if renderer === 'terminal' && typeof val === 'string'}
      <TerminalRenderer content={val} />
    {:else if renderer === 'code' && typeof val === 'string'}
      <CodeRenderer code={val} />
    {:else if renderer === 'text' && typeof val === 'string'}
      <TextRenderer content={val} label={lbl} showLabel={lvl > 0} />
    {:else}
      <JsonBlock data={val} />
    {/if}
  {/if}
{/snippet}

<!-- Entry point -->
{#if depth === 0}
  <div class="rounded-lg border border-[#52525b] bg-[#18181b] overflow-hidden shadow-sm shadow-black/40">
    <div class="flex items-center justify-between px-3 py-1.5 bg-[#232326] border-b border-[#52525b]">
      <span class="text-[10px] font-mono uppercase tracking-wider text-zinc-200 font-semibold">
        {label}
      </span>
      <div class="flex items-center gap-1 p-0.5 rounded bg-[#0f0f11] border border-[#3f3f46]">
        <button
          type="button"
          onclick={() => (mode = 'smart')}
          class="px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold transition-colors
                 {mode === 'smart' ? 'bg-amber-500/25 text-amber-200' : 'text-zinc-400 hover:text-zinc-100'}"
        >
          Smart
        </button>
        <button
          type="button"
          onclick={() => (mode = 'json')}
          class="px-1.5 py-0.5 rounded text-[9px] font-mono font-semibold transition-colors
                 {mode === 'json' ? 'bg-sky-500/25 text-sky-200' : 'text-zinc-400 hover:text-zinc-100'}"
        >
          JSON
        </button>
      </div>
    </div>
    <div class="p-3">
      {#if mode === 'json'}
        <JsonBlock data={value} />
      {:else}
        {@render renderBody(label, value, 0)}
      {/if}
    </div>
  </div>
{:else}
  {@render renderBody(label, value, depth)}
{/if}