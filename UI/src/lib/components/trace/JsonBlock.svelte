<script lang="ts">
  import { T } from './theme';

  let { data }: { data: unknown } = $props();

  let expanded = $state(false);
  let copied = $state(false);

  const pretty = $derived(JSON.stringify(data, null, 2) ?? 'null');
  const isLarge = $derived(pretty.length > 5000);
  const visible = $derived(
    isLarge && !expanded
      ? pretty.slice(0, 5000) + '\n... (đã rút gọn, bấm Show more)'
      : pretty,
  );

  async function copy() {
    try {
      await navigator.clipboard.writeText(pretty);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch { /* noop */ }
  }
</script>

<div class={T.card + ' overflow-hidden'}>
  <div class="flex items-center justify-between px-2.5 py-1 {T.cardHeader}">
    <span class="text-[10px] font-mono text-zinc-400">
      {pretty.length.toLocaleString()} ký tự
    </span>
    <div class="flex items-center gap-1.5">
      {#if isLarge}
        <button
          type="button"
          onclick={() => (expanded = !expanded)}
          class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#3f3f46] hover:bg-[#52525b] text-zinc-100 border border-[#52525b] transition-colors"
        >
          {expanded ? 'Show less' : 'Show more'}
        </button>
      {/if}
      <button
        type="button"
        onclick={copy}
        class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#3f3f46] hover:bg-[#52525b] text-zinc-100 border border-[#52525b] transition-colors"
      >
        {copied ? 'Copied ✓' : 'Copy'}
      </button>
    </div>
  </div>
  <pre class="p-2.5 text-[11.5px] font-mono text-zinc-100 whitespace-pre-wrap break-words max-h-96 overflow-y-auto {T.bgInner}">{visible}</pre>
</div>