<script lang="ts">
  import { agentSession } from '$lib/state/agent_session.svelte';
  import type { Snippet } from 'svelte';

  let { panel1, panel2, panel3 }: {
    panel1: Snippet;
    panel2: Snippet;
    panel3: Snippet;
  } = $props();

  let containerRef: HTMLDivElement | null = $state(null);
  let draggingIndex = $state<number | null>(null);

  function startDrag(index: number, e: PointerEvent) {
    draggingIndex = index;
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: PointerEvent) {
    if (draggingIndex === null || !containerRef) return;
    const rect = containerRef.getBoundingClientRect();
    const currentX = e.clientX - rect.left;
    const totalWidth = rect.width;
    const ratio = Math.max(0.1, Math.min(0.85, currentX / totalWidth)) * 100;

    const [p1, p2, p3] = agentSession.panelSizes;

    if (draggingIndex === 0) {
      const delta = ratio - p1;
      if (p1 + delta >= 15 && p2 - delta >= 25) {
        agentSession.setPanelSizes([
          Number((p1 + delta).toFixed(2)),
          Number((p2 - delta).toFixed(2)),
          p3
        ]);
      }
    } else if (draggingIndex === 1) {
      const delta = ratio - (p1 + p2);
      if (p2 + delta >= 25 && p3 - delta >= 25) {
        agentSession.setPanelSizes([
          p1,
          Number((p2 + delta).toFixed(2)),
          Number((p3 - delta).toFixed(2))
        ]);
      }
    }
  }

  function stopDrag() {
    draggingIndex = null;
  }

  function handleKeyDown(index: number, e: KeyboardEvent) {
    const step = 2;
    const [p1, p2, p3] = agentSession.panelSizes;

    if (e.key === 'ArrowLeft') {
      e.preventDefault();
      if (index === 0 && p1 - step >= 15) {
        agentSession.setPanelSizes([p1 - step, p2 + step, p3]);
      } else if (index === 1 && p2 - step >= 25) {
        agentSession.setPanelSizes([p1, p2 - step, p3 + step]);
      }
    } else if (e.key === 'ArrowRight') {
      e.preventDefault();
      if (index === 0 && p2 - step >= 25) {
        agentSession.setPanelSizes([p1 + step, p2 - step, p3]);
      } else if (index === 1 && p3 - step >= 25) {
        agentSession.setPanelSizes([p1, p2 + step, p3 - step]);
      }
    }
  }
</script>

<svelte:window onpointermove={onPointerMove} onpointerup={stopDrag} />

<div
  bind:this={containerRef}
  class="relative flex w-screen h-screen overflow-hidden bg-[#121214] select-none text-zinc-300 font-sans"
>
  <aside
    style="width: {agentSession.panelSizes[0]}%"
    class="h-full flex flex-col border-r border-[#27272a] bg-[#141416] shrink-0 min-w-0"
  >
    {@render panel1()}
  </aside>

  <button
    type="button"
    aria-label="Resize Explorer and Chat panels"
    onpointerdown={(e) => startDrag(0, e)}
    onkeydown={(e) => handleKeyDown(0, e)}
    class="w-1 cursor-col-resize hover:bg-amber-500/80 active:bg-amber-500 transition-colors z-30 shrink-0 bg-transparent -mx-0.5 border-none p-0 focus:outline-none focus:bg-amber-500"
  ></button>

  <main
    style="width: {agentSession.panelSizes[1]}%"
    class="h-full flex flex-col border-r border-[#27272a] bg-[#18181b] shrink-0 min-w-0"
  >
    {@render panel2()}
  </main>

  <button
    type="button"
    aria-label="Resize Chat and Diff Canvas panels"
    onpointerdown={(e) => startDrag(1, e)}
    onkeydown={(e) => handleKeyDown(1, e)}
    class="w-1 cursor-col-resize hover:bg-amber-500/80 active:bg-amber-500 transition-colors z-30 shrink-0 bg-transparent -mx-0.5 border-none p-0 focus:outline-none focus:bg-amber-500"
  ></button>

  <section
    style="width: {agentSession.panelSizes[2]}%"
    class="h-full flex flex-col bg-[#121214] shrink-0 min-w-0"
  >
    {@render panel3()}
  </section>
</div>