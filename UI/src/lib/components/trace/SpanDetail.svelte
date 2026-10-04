<script lang="ts">
  import type { SpanDTO } from '$lib/state/types';
  import SmartValue from './SmartValue.svelte';
  import JsonBlock from './JsonBlock.svelte';
  import { spanTypeView, spanStatusView, formatDuration } from './trace_format';

  let { span }: { span: SpanDTO } = $props();

  const tv = $derived(spanTypeView(span.span_type));
  const sv = $derived(spanStatusView(span.status));

  const hasMetadata = $derived(
    typeof span.metadata === 'object' &&
      span.metadata !== null &&
      Object.keys(span.metadata).length > 0,
  );
</script>

<div class="p-3 space-y-3">
  <!-- Header -->
  <div class="flex items-center gap-2.5 pb-2.5 border-b border-[#3f3f46]">
    <span class="text-xl {tv.colorClass} shrink-0">{tv.icon}</span>
    <div class="flex-1 min-w-0">
      <div class="text-[13px] font-semibold text-zinc-50 truncate">{span.name}</div>
      <div class="text-[11px] font-mono text-zinc-400 flex items-center gap-1.5 flex-wrap mt-0.5">
        <span class="text-zinc-300">{tv.label}</span>
        <span class="text-zinc-600">·</span>
        <span class="text-zinc-300">{formatDuration(span.duration_ms)}</span>
        <span class="text-zinc-600">·</span>
        <span class={sv.badgeClass.split(' ').pop() + ' font-semibold'}>{sv.label}</span>
        <span class="text-zinc-600">·</span>
        <span class="truncate max-w-[200px] text-zinc-500" title={span.span_id}>{span.span_id}</span>
      </div>
    </div>
  </div>

  <!-- Input -->
  <SmartValue label="input" value={span.input_data} />

  <!-- Output -->
  <SmartValue label="output" value={span.output_data} />

  <!-- Metadata — JSON trực tiếp -->
  {#if hasMetadata}
    <div class="space-y-1.5">
      <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-300 font-semibold">
        metadata
      </div>
      <JsonBlock data={span.metadata} />
    </div>
  {/if}
</div>