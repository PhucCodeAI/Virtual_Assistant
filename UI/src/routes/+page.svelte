<script lang="ts">
  import { ChatService } from "$lib/state/chat.svelte";
  import LeftPanel from "$lib/components/layout/LeftPanel.svelte";
  import RightPanel from "$lib/components/layout/RightPanel.svelte";
  import ChatTerminal from "$lib/components/chat/ChatTerminal.svelte";

  // Khởi tạo Global State
  const chat = new ChatService();

  // Polling Metrics
  $effect(() => {
    const interval = setInterval(() => chat.fetchMetrics(), 500);
    return () => clearInterval(interval);
  });
</script>

<div class="flex h-screen w-full sci-fi-bg text-gray-200 font-sans overflow-hidden">
  <LeftPanel {chat} />
  <ChatTerminal {chat} />
  <RightPanel {chat} />
</div>

<style>
  /* GLOBAL SCI-FI CSS */
  :global(.custom-scrollbar::-webkit-scrollbar) { width: 4px; }
  :global(.custom-scrollbar::-webkit-scrollbar-track) { background: transparent; }
  :global(.custom-scrollbar::-webkit-scrollbar-thumb) { background: rgba(6, 182, 212, 0.3); border-radius: 10px; }
  :global(.custom-scrollbar::-webkit-scrollbar-thumb:hover) { background: rgba(6, 182, 212, 0.8); }

  .sci-fi-bg {
    background-color: #030712;
    background-image:
      radial-gradient(circle at 50% 0%, rgba(14, 165, 233, 0.15), transparent 50%),
      radial-gradient(circle at 50% 100%, rgba(168, 85, 247, 0.1), transparent 50%),
      linear-gradient(to right, rgba(6, 182, 212, 0.03) 1px, transparent 1px),
      linear-gradient(to bottom, rgba(6, 182, 212, 0.03) 1px, transparent 1px);
    background-size: 100% 100%, 100% 100%, 30px 30px, 30px 30px;
  }

  :global(.glass-panel) {
    background: rgba(17, 24, 39, 0.6);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border: 1px solid rgba(6, 182, 212, 0.2);
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5), inset 0 0 20px rgba(6, 182, 212, 0.05);
  }

  :global(.neon-text-cyan) { text-shadow: 0 0 8px rgba(34, 211, 238, 0.6); }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
  }
  :global(.animate-fade-in) { animation: fadeIn 0.4s ease-out forwards; }
</style>