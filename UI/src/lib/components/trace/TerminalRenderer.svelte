<script lang="ts">
  import { T } from './theme';

  let { content }: { content: string } = $props();

  let copied = $state(false);

  function lineClass(line: string): string {
    if (line.includes('PASSED') || /\bOK\b/.test(line)) return 'text-emerald-300';
    if (line.includes('FAIL') || line.includes('Error') || line.includes('Traceback')) {
      return 'text-rose-300';
    }
    if (line.includes('WARN') || line.includes('Warning')) return 'text-amber-300';
    return 'text-zinc-100';
  }

  const lines = $derived(content.split('\n'));

  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch { /* noop */ }
  }
</script>

<div class={T.card + ' overflow-hidden'}>
  <div class="flex items-center justify-between px-2.5 py-1 {T.cardHeader}">
    <span class="text-[10px] font-mono uppercase tracking-wider text-zinc-300 font-semibold">output</span>
    <button
      type="button"
      onclick={copy}
      class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#3f3f46] hover:bg-[#52525b] text-zinc-100 border border-[#52525b] transition-colors"
    >
      {copied ? 'Copied ✓' : 'Copy'}
    </button>
  </div>
  <div class="p-3 font-mono text-[11.5px] leading-relaxed max-h-96 overflow-y-auto {T.bgTerminal}">
    {#each lines as line, i (i)}
      <div class="{lineClass(line)} whitespace-pre-wrap break-words">{line || ' '}</div>
    {/each}
  </div>
</div>