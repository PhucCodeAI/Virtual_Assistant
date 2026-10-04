<script lang="ts">
  import { highlightCode } from '$lib/components/chat/highlighter';
  import { sanitizeHtml } from '$lib/components/chat/safe_html';
  import { T } from './theme';

  let {
    code,
    lang = 'plaintext',
  }: {
    code: string;
    lang?: string;
  } = $props();

  let copied = $state(false);

  const highlighted = $derived(sanitizeHtml(highlightCode(code)));
  const lineCount = $derived(code.split('\n').length);
  const lineNumbers = $derived(Array.from({ length: lineCount }, (_, i) => i + 1));

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch { /* noop */ }
  }
</script>

<div class={T.card + ' overflow-hidden'}>
  <!-- Header -->
  <div class="flex items-center justify-between px-2.5 py-1.5 {T.cardHeader}">
    <div class="flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-zinc-500"></span>
      <span class="text-[10px] font-mono lowercase text-zinc-200 tracking-wider font-semibold">{lang}</span>
    </div>
    <button
      type="button"
      onclick={copy}
      class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#3f3f46] hover:bg-[#52525b] text-zinc-100 border border-[#52525b] transition-colors"
    >
      {copied ? 'Copied ✓' : 'Copy'}
    </button>
  </div>

  <!-- Code -->
  <div class="flex overflow-x-auto {T.bgInner}">
    <div class="select-none text-right pr-2.5 pl-2.5 py-2 text-zinc-500 border-r border-[#3f3f46] shrink-0 font-mono text-[11px] leading-5">
      {#each lineNumbers as n (n)}
        <div>{n}</div>
      {/each}
    </div>
    <!-- eslint-disable-next-line svelte/no-at-html-tags -- sanitized above -->
    <pre class="pl-3 pr-4 py-2 text-[12px] leading-5 font-mono overflow-x-visible"><code>{@html highlighted}</code></pre>
  </div>
</div>