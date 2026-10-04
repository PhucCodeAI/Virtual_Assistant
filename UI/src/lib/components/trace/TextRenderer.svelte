<script lang="ts">
  import { T } from './theme';

  let {
    content,
    label = '',
    showLabel = false,
  }: {
    content: string;
    label?: string;
    showLabel?: boolean;
  } = $props();

  let copied = $state(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(content);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch { /* noop */ }
  }
</script>

<div class="space-y-1.5">
  {#if showLabel && label}
    <div class={T.headerLabel}>{label}</div>
  {/if}

  <div class="relative {T.card}">
    <button
      type="button"
      onclick={copy}
      class="absolute top-2 right-2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#27272a] hover:bg-[#3f3f46] text-zinc-200 border border-[#52525b] transition-colors z-10"
    >
      {copied ? 'Copied ✓' : 'Copy'}
    </button>

    <div class="p-3 pr-20 {T.contentText}">
      {content}
    </div>
  </div>
</div>