<script lang="ts">
  import { T } from './theme';

  let {
    messages,
  }: {
    messages: { role: string; content: string }[];
  } = $props();

  function roleClass(role: string): string {
    const r = role.toLowerCase();
    if (r === 'system') return 'bg-violet-500/20 border-violet-400/50 text-violet-200';
    if (r === 'user') return 'bg-sky-500/20 border-sky-400/50 text-sky-200';
    if (r === 'assistant') return 'bg-emerald-500/20 border-emerald-400/50 text-emerald-200';
    if (r === 'tool') return 'bg-amber-500/20 border-amber-400/50 text-amber-200';
    return 'bg-zinc-500/20 border-zinc-400/50 text-zinc-200';
  }
</script>

<div class="{T.card} overflow-hidden">
  <div class="divide-y divide-[#3f3f46]">
    {#each messages as msg, i (i)}
      <div class="grid grid-cols-[80px_1fr] gap-3 p-3">
        <div class="shrink-0">
          <span
            class="inline-block px-1.5 py-0.5 rounded border text-[10px] font-mono font-bold uppercase tracking-wide {roleClass(msg.role)}"
          >
            {msg.role}
          </span>
        </div>
        <div class={T.contentText + ' min-w-0'}>
          {msg.content}
        </div>
      </div>
    {/each}
  </div>
</div>