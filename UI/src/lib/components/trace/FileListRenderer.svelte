<script lang="ts">
  import CodeRenderer from './CodeRenderer.svelte';
  import { T } from './theme';

  let {
    files,
  }: {
    files: Record<string, unknown>[];
  } = $props();

  const CODE_FIELDS = ['code', 'test', 'content', 'source', 'diff'] as const;

  function isString(x: unknown): x is string {
    return typeof x === 'string';
  }

  function actionMeta(action: unknown): { cls: string; icon: string; label: string } {
    const a = typeof action === 'string' ? action.toLowerCase() : '';
    if (a === 'create') return { cls: 'bg-emerald-500/20 border-emerald-400/50 text-emerald-200', icon: '+', label: 'create' };
    if (a === 'update') return { cls: 'bg-amber-500/20 border-amber-400/50 text-amber-200', icon: '~', label: 'update' };
    if (a === 'delete') return { cls: 'bg-rose-500/20 border-rose-400/50 text-rose-200', icon: '−', label: 'delete' };
    return { cls: 'bg-zinc-500/20 border-zinc-400/50 text-zinc-200', icon: '·', label: a || 'file' };
  }

  function inferLang(path: unknown): string {
    if (typeof path !== 'string') return 'plaintext';
    if (path.endsWith('.py')) return 'python';
    if (path.endsWith('.ts')) return 'typescript';
    if (path.endsWith('.js')) return 'javascript';
    if (path.endsWith('.json')) return 'json';
    if (path.endsWith('.md')) return 'markdown';
    if (path.endsWith('.svelte')) return 'svelte';
    return 'plaintext';
  }
</script>

<div class="space-y-2">
  {#each files as file, i (i)}
    {@const meta = actionMeta(file.action)}
    {@const path = typeof file.path === 'string' ? file.path : `file-${i}`}
    <div class={T.card + ' overflow-hidden'}>
      <div class="flex items-center gap-2 px-3 py-1.5 {T.cardHeader}">
        <span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-mono font-bold {meta.cls}">
          <span>{meta.icon}</span>
          <span>{meta.label}</span>
        </span>
        <span class="text-[12px] font-mono text-zinc-100 truncate flex-1" title={path}>
          {path}
        </span>
      </div>

      <div class="p-2 space-y-2 {T.bgInner}">
        {#each CODE_FIELDS as field, idx (idx)}
          {#if isString(file[field]) && file[field]}
            <div>
              {#if field !== 'code'}
                <div class="text-[10px] font-mono uppercase tracking-wider text-zinc-400 mb-1 pl-1 font-semibold">
                  {field}
                </div>
              {/if}
              <CodeRenderer code={file[field] as string} lang={inferLang(path)} />
            </div>
          {/if}
        {/each}
      </div>
    </div>
  {/each}
</div>