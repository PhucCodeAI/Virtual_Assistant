<script lang="ts">
  import { T } from './theme';

  let { parts }: { parts: string[] } = $props();

  let copied = $state(false);

  function shellQuote(arg: string): string {
    if (/^[A-Za-z0-9_\-./=:@]+$/.test(arg)) return arg;
    return `'${arg.replace(/'/g, "'\\''")}'`;
  }

  const rendered = $derived(parts.map(shellQuote).join(' '));

  async function copy() {
    try {
      await navigator.clipboard.writeText(rendered);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch { /* noop */ }
  }
</script>

<div class={T.card + ' overflow-hidden'}>
  <div class="flex items-center gap-2 px-3 py-2.5">
    <span class="text-sky-300 font-mono text-[12px] font-bold shrink-0 select-none">$</span>
    <code class="flex-1 font-mono text-[12px] text-sky-200 whitespace-pre-wrap break-all min-w-0">
      {rendered}
    </code>
    <button
      type="button"
      onclick={copy}
      class="shrink-0 text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#3f3f46] hover:bg-[#52525b] text-zinc-100 border border-[#52525b] transition-colors"
    >
      {copied ? 'Copied ✓' : 'Copy'}
    </button>
  </div>
</div>