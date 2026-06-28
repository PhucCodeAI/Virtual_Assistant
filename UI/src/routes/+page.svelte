<script>
    import { onMount } from 'svelte';

    let messages = $state([]);
    let currentInput = $state("");
    let isLoading = $state(false);
    let selectedImage = $state(null);
    let fileInput; 

    let metrics = $state({ cpu: 0, ram: 0, gpu_vram: 0, throughput: 0 });
    // NEW: State cho Dataset Flywheel
    let datasetStats = $state({ sft: 0, dpo: 0 });

    onMount(() => {
        const interval = setInterval(async () => {
            try {
                const res = await fetch('http://localhost:8000/v1/metrics');
                if (res.ok) {
                    const data = await res.json();
                    metrics.cpu = data.cpu;
                    metrics.ram = data.ram;
                    metrics.gpu_vram = data.gpu_vram;
                    if (!isLoading) metrics.throughput = data.throughput;
                    
                    if (data.dataset_stats) {
                        datasetStats.sft = data.dataset_stats.sft;
                        datasetStats.dpo = data.dataset_stats.dpo;
                    }
                }
            } catch (error) {
                console.error("Monitor Error:", error);
            }
        }, 1000);

        return () => clearInterval(interval);
    });

    function processImageFile(file) {
        if (file && file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => selectedImage = e.target.result;
            reader.readAsDataURL(file);
        }
    }

    function handlePaste(e) {
        const items = e.clipboardData?.items;
        if (!items) return;
        for (let item of items) {
            if (item.type.indexOf('image') !== -1) {
                e.preventDefault();
                processImageFile(item.getAsFile());
                break;
            }
        }
    }

    function handleKeydown(e) {
        if (e.key === 'Enter') {
            if (e.ctrlKey) currentInput += '\n';
            else if (!e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        }
    }

    async function sendMessage() {
        if (!currentInput.trim() && !selectedImage) return;

        const userText = currentInput;
        const userImg = selectedImage;

        messages.push({ role: 'user', content: userText, image: userImg });
        
        let apiMessages = messages.map(msg => {
            if (msg.role === 'assistant') return { role: 'assistant', content: msg.content };
            if (msg.role === 'user' && msg.image) {
                return {
                    role: 'user',
                    content: [
                        { type: "image_url", image_url: { url: msg.image } },
                        { type: "text", text: msg.content || "Phân tích ảnh này." }
                    ]
                };
            }
            return { role: 'user', content: msg.content };
        });

        currentInput = "";
        selectedImage = null; 
        isLoading = true;
        
        // NEW: Thêm các trường quản lý trạng thái cho AI message
        messages.push({ 
            role: 'assistant', 
            content: '', 
            db_id: null, 
            status: 'pending', // pending, approved, edited, discarded
            isEditing: false,
            editContent: ''
        });
        let aiIndex = messages.length - 1;

        try {
            const response = await fetch('http://localhost:8000/v1/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ messages: apiMessages })
            });
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                messages[aiIndex].content += decoder.decode(value, { stream: true });
            }

            try {
                const createRes = await fetch('http://localhost:8000/database/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prompt: userText,
                        image: userImg,
                        response: messages[aiIndex].content
                    })
                });
                if (createRes.ok) {
                    const createData = await createRes.json();
                    messages[aiIndex].db_id = createData.id;
                } else {
                    throw new Error("Backend not ready");
                }
            } catch (e) {
                console.warn("Backend chưa chạy, dùng Mock ID để test UI");
                messages[aiIndex].db_id = "mock-id-" + Date.now();
            }

        } catch (error) {
            messages[aiIndex].content = "Lỗi kết nối Backend!";
        } finally {
            isLoading = false;
        }
    }

    async function updateDataset(index, action) {
        const msg = messages[index];
        if (!msg.db_id) return;

        // Test in console
        console.log("==> TIẾP NHẬN LỆNH CẬP NHẬT UI <==");
        console.log("DB ID thực tế gửi đi:", msg.db_id);
        console.log("Hành động:", action);

        if (!msg.db_id) {
            console.error("LỖI: Không thể cập nhật vì db_id đang bị NULL/UNDEFINED!");
            return;
        }

        let payload = { status: action, human_corrected: null };

        if (action === 'approved') {
            msg.status = 'approved';
            payload.human_corrected = msg.content; // SFT
        } else if (action === 'edited') {
            msg.status = 'edited';
            msg.content = msg.editContent; // Cập nhật UI
            msg.isEditing = false;
            payload.human_corrected = msg.content; // DPO
        } else if (action === 'discarded') {
            msg.status = 'discarded';
        }

        // Gọi API PUT cập nhật DB
        await fetch(`http://localhost:8000/database/update/${msg.db_id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    }
</script>

<div class="flex h-screen w-full bg-gray-950 text-gray-200 font-sans overflow-hidden">

    <!-- CỘT TRÁI (Giữ nguyên) -->
    <div class="w-1/5 bg-gray-900 border-r border-gray-800 p-4 flex flex-col">
        <h2 class="text-lg font-bold text-blue-400 mb-4 uppercase tracking-wider text-sm">Agent Status</h2>
        <div class="space-y-2 text-sm">
            <div class="p-2 bg-gray-800 rounded border border-gray-700 flex justify-between">
                <span>Core Engine:</span><span class="text-green-400">Qwen 3.5 2B</span>
            </div>
            <div class="p-2 bg-gray-800 rounded border border-gray-700 flex justify-between">
                <span>Active Tool:</span><span class="text-yellow-400">Idle</span>
            </div>
        </div>
    </div>

    <!-- CỘT GIỮA: Chat Interface -->
    <div class="flex-1 flex flex-col p-4 relative">
        <div class="flex-1 overflow-y-auto mb-4 space-y-4 pr-2">
            {#if messages.length === 0}
            <div class="flex h-full items-center justify-center text-gray-500">
                Hệ thống Agentic Local đã sẵn sàng. Hãy nhập yêu cầu...
            </div>
            {/if}
            
            {#each messages as msg, index}
            <div class="flex flex-col {msg.role === 'user' ? 'items-end' : 'items-start'}">
                <div class="p-4 rounded-xl max-w-[85%] shadow-md {msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-gray-800 border border-gray-700 text-gray-100'}">
                    {#if msg.image}
                    <img src={msg.image} alt="User upload" class="max-w-full h-auto rounded-lg mb-2 border border-gray-400/30" />
                    {/if}
                    
                    <!-- NEW: Chế độ Edit cho AI -->
                    {#if msg.role === 'assistant' && msg.isEditing}
                        <textarea 
                            bind:value={msg.editContent} 
                            class="w-full bg-gray-900 text-gray-100 p-2 rounded border border-blue-500 focus:outline-none min-h-[100px]"
                        ></textarea>
                        <div class="flex gap-2 mt-2 justify-end">
                            <button onclick={() => msg.isEditing = false} class="text-xs px-3 py-1 bg-gray-600 rounded hover:bg-gray-500">Hủy</button>
                            <button onclick={() => updateDataset(index, 'edited')} class="text-xs px-3 py-1 bg-blue-600 rounded hover:bg-blue-500 font-bold">Lưu DPO</button>
                        </div>
                    {:else}
                        <div class="whitespace-pre-wrap">{msg.content}</div>
                    {/if}
                </div>

                <!-- NEW: Action Bar cho AI Message (Chỉ hiện khi đã có db_id và chưa edit) -->
                {#if msg.role === 'assistant' && msg.db_id && !msg.isEditing}
                    <div class="flex gap-2 mt-1 ml-2 text-xs">
                        {#if msg.status === 'pending'}
                            <button onclick={() => updateDataset(index, 'approved')} class="text-green-400 hover:text-green-300 flex items-center gap-1">
                                <span>✅</span> Approve (SFT)
                            </button>
                            <button onclick={() => { msg.isEditing = true; msg.editContent = msg.content; }} class="text-blue-400 hover:text-blue-300 flex items-center gap-1">
                                <span>✏️</span> Edit (DPO)
                            </button>
                            <button onclick={() => updateDataset(index, 'discarded')} class="text-red-400 hover:text-red-300 flex items-center gap-1">
                                <span>🗑️</span> Discard
                            </button>
                        {:else if msg.status === 'approved'}
                            <span class="text-green-500 font-bold">✓ Đã lưu SFT</span>
                        {:else if msg.status === 'edited'}
                            <span class="text-blue-500 font-bold">✓ Đã lưu DPO</span>
                        {:else if msg.status === 'discarded'}
                            <span class="text-red-500">✗ Đã bỏ qua</span>
                        {/if}
                    </div>
                {/if}
            </div>
            {/each}
        </div>

        <!-- Khu vực nhập liệu (Giữ nguyên) -->
        <div class="flex flex-col gap-2 mt-auto bg-gray-800 p-3 rounded-xl border border-gray-700 focus-within:border-blue-500 transition-colors">
            {#if selectedImage}
            <div class="relative inline-block w-24 h-24 mb-2">
                <img src={selectedImage} alt="Preview" class="w-full h-full object-cover rounded-lg border border-gray-600" />
                <button onclick={()=> selectedImage = null} class="absolute -top-2 -right-2 bg-red-500 text-white rounded-full w-6 h-6 flex items-center justify-center text-xs font-bold hover:bg-red-600">✕</button>
            </div>
            {/if}

            <div class="flex gap-2 items-end">
                <input type="file" accept="image/*" bind:this={fileInput} onchange={(e)=> processImageFile(e.target.files[0])} class="hidden" />
                <button onclick={()=> fileInput.click()} class="p-3 text-gray-400 hover:text-blue-400 transition-colors rounded-lg hover:bg-gray-700" title="Đính kèm ảnh">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="w-6 h-6">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M18.375 12.739l-7.693 7.693a4.5 4.5 0 01-6.364-6.364l10.94-10.94A3 3 0 1119.5 7.372L8.552 18.32m.009-.01l-.01.01m5.699-9.941l-7.81 7.81a1.5 1.5 0 002.112 2.13" />
                    </svg>
                </button>
                <textarea bind:value={currentInput} onkeydown={handleKeydown} onpaste={handlePaste} disabled={isLoading} rows="2" class="flex-1 bg-transparent p-2 resize-none focus:outline-none text-gray-200" placeholder="Nhập yêu cầu (Ctrl+V để dán ảnh, Ctrl+Enter để xuống dòng)..."></textarea>
                <button onclick={sendMessage} disabled={isLoading} class="bg-blue-600 px-6 py-3 rounded-lg font-bold hover:bg-blue-500 disabled:opacity-50 transition-colors h-fit">Gửi</button>
            </div>
        </div>
    </div>

    <!-- CỘT PHẢI: System Monitor & Dataset Stats -->
    <div class="w-1/4 bg-gray-900 border-l border-gray-800 p-4 flex flex-col gap-6">
        <h2 class="text-lg font-bold text-red-400 uppercase tracking-wider text-sm">System Monitor</h2>
        <div>
            <div class="flex justify-between text-sm mb-1"><span>CPU (i5-12400F)</span><span>{metrics.cpu}%</span></div>
            <div class="w-full bg-gray-700 rounded-full h-2.5"><div class="bg-blue-500 h-2.5 rounded-full transition-all duration-500" style="width: {metrics.cpu}%"></div></div>
        </div>
        <div>
            <div class="flex justify-between text-sm mb-1"><span>RAM (32GB)</span><span>{metrics.ram} GB</span></div>
            <div class="w-full bg-gray-700 rounded-full h-2.5"><div class="bg-green-500 h-2.5 rounded-full transition-all duration-500" style="width: {(metrics.ram / 32) * 100}%"></div></div>
        </div>
        <div>
            <div class="flex justify-between text-sm mb-1"><span>VRAM (GTX 1660S)</span><span class="{metrics.gpu_vram > 5.5 ? 'text-red-500 font-bold' : ''}">{metrics.gpu_vram} / 6.0 GB</span></div>
            <div class="w-full bg-gray-700 rounded-full h-2.5"><div class="{metrics.gpu_vram > 5.5 ? 'bg-red-500' : 'bg-purple-500'} h-2.5 rounded-full transition-all duration-500" style="width: {(metrics.gpu_vram / 6) * 100}%"></div></div>
        </div>
        <div class="p-4 bg-gray-800 rounded-lg border border-gray-700 text-center">
            <div class="text-gray-400 text-xs uppercase mb-1">Throughput</div>
            <div class="text-3xl font-mono font-bold {metrics.throughput > 0 ? 'text-green-400' : 'text-gray-500'}">{metrics.throughput} <span class="text-sm">t/s</span></div>
        </div>

        <!-- NEW: Dataset Flywheel Stats -->
        <h2 class="text-lg font-bold text-purple-400 uppercase tracking-wider text-sm mt-4">Data Flywheel</h2>
        <div class="flex flex-col gap-3">
            <div class="p-3 bg-gray-800 rounded-lg border border-green-500/30 flex justify-between items-center">
                <span class="text-sm text-gray-300">SFT Samples (Approved)</span>
                <span class="text-xl font-bold text-green-400">{datasetStats.sft}</span>
            </div>
            <div class="p-3 bg-gray-800 rounded-lg border border-blue-500/30 flex justify-between items-center">
                <span class="text-sm text-gray-300">DPO Samples (Edited)</span>
                <span class="text-xl font-bold text-blue-400">{datasetStats.dpo}</span>
            </div>
        </div>
    </div>
</div>