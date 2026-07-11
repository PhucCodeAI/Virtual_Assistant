<script lang="ts">
  import type { ChatService } from "$lib/state/chat.svelte";

  let { chat }: { chat: ChatService } = $props();
  let fileInput: HTMLInputElement;
  let textareaElement: HTMLTextAreaElement = $state();

  // Thuật toán Reactive Auto-Resize chuẩn mực của Svelte 5
  $effect(() => {
    const _ = chat.currentInput; // Đăng ký reactivity với rune $state bên trong service
    if (textareaElement) {
      // Reset chiều cao về auto để đo lường chính xác khi xóa chữ
      textareaElement.style.height = "auto";
      const maxHeight = window.innerHeight * 0.4; // Giới hạn tối đa 40% chiều cao màn hình (40vh)
      const scrollHeight = textareaElement.scrollHeight;

      // Gán chiều cao mới động
      textareaElement.style.height =
        (scrollHeight > maxHeight ? maxHeight : scrollHeight) + "px";
    }
  });
</script>

<div
  class="mx-4 bg-gray-900/60 backdrop-blur-xl p-2 rounded-2xl border border-cyan-500/30 focus-within:border-cyan-400 focus-within:shadow-[0_0_20px_rgba(6,182,212,0.15)] transition-all flex flex-col gap-2"
>
  {#if chat.selectedImage}
    <div class="relative inline-block w-20 h-20 mb-1 ml-2 mt-2">
      <img
        src={chat.selectedImage}
        alt="Preview"
        class="w-full h-full object-cover rounded-xl border border-cyan-500/50"
      />
      <button
        onclick={() => (chat.selectedImage = null)}
        class="absolute -top-2 -right-2 bg-red-900/80 border border-red-500 hover:bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs transition-colors"
        >✕</button
      >
    </div>
  {/if}

  <div class="flex gap-2 items-end">
    <input
      type="file"
      accept="image/*"
      bind:this={fileInput}
      onchange={(e) => chat.processImageFile(e.target.files?.[0] || null)}
      class="hidden"
    />
    <button
      onclick={() => fileInput.click()}
      class="p-3 text-cyan-600 hover:text-cyan-300 transition-colors rounded-xl hover:bg-cyan-900/30"
    >
      <svg
        class="w-6 h-6"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        stroke-width="1.5"
        ><path
          stroke-linecap="round"
          stroke-linejoin="round"
          d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13"
        /></svg
      >
    </button>

    <!-- Gắn bind:this và loại bỏ class rows tĩnh để JS tự tính toán -->
    <textarea
      bind:this={textareaElement}
      bind:value={chat.currentInput}
      onkeydown={chat.handleKeydown}
      onpaste={chat.handlePaste}
      disabled={chat.isLoading}
      class="flex-1 bg-transparent py-3 px-2 max-h-[40vh] overflow-y-auto custom-scrollbar resize-none focus:outline-none text-cyan-50 placeholder-cyan-700/50 font-sans"
      placeholder="Hãy ra lệnh cho tôi làm bất cứ điều gì..."
    ></textarea>

    <button
      onclick={() => chat.sendMessage()}
      disabled={chat.isLoading ||
        (!chat.currentInput.trim() && !chat.selectedImage)}
      class="bg-cyan-600/20 border border-cyan-500 text-cyan-400 hover:bg-cyan-500 hover:text-gray-900 hover:shadow-[0_0_15px_rgba(6,182,212,0.8)] px-6 py-2.5 rounded-xl font-mono uppercase text-sm disabled:opacity-30 disabled:cursor-not-allowed transition-all h-fit mb-1 mr-1"
    >
      Gửi
    </button>
  </div>
</div>
