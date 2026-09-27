<script lang="ts">
  import ResizableLayout from '$lib/components/layout/ResizableLayout.svelte';
  import WorkspaceExplorer from '$lib/components/explorer/WorkspaceExplorer.svelte';
  import Chat from '$lib/components/chat/Chat.svelte';
  import ActiveCanvas from '$lib/components/canvas/ActiveCanvas.svelte';
</script>

<svelte:head>
  <title>Agent Workspace | 3-Panel Diff Canvas</title>
</svelte:head>

<ResizableLayout>
  {#snippet panel1()}
    <WorkspaceExplorer />
  {/snippet}

  {#snippet panel2()}
    <Chat />
  {/snippet}

  {#snippet panel3()}
    <ActiveCanvas />
  {/snippet}
</ResizableLayout>