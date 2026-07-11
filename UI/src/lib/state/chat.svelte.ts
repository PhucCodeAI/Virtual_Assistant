import { API_BASE_URL } from './config';
import type { Message, APIMessage } from './types';
import { MetricsService } from './metrics.svelte';
import { CodebaseService } from './codebase.svelte';

export class ChatService {
    // 1. KHỞI TẠO CÁC MODULE CON
    private monitor = new MetricsService();
    private codebase = new CodebaseService();

    // 2. STATE CỦA RIÊNG CHAT
    messages = $state<Message[]>([]);
    currentInput = $state<string>("");
    isLoading = $state<boolean>(false);
    selectedImage = $state<string | null>(null);
    mode = $state<string>("chat");
    temperature = $state<number>(0.5);
    topP = $state<number>(0.9);
    systemPrompt = $state("Bạn là Trợ lý ảo cá nhân chuyên nghiệp. Tuân thủ nghiêm ngặt các quy tắc phản hồi sau:\n1. Đi thẳng vào vấn đề, trả lời ngắn gọn, súc tích và dễ hiểu. Tuyệt đối không giải thích dông dài.\n2. Luôn trình bày bằng định dạng Markdown (tiêu đề, danh sách, bảng biểu, khối code) để tối ưu hóa trải nghiệm đọc.\n3. Không bịa đặt thông tin. Nếu thiếu dữ liệu hoặc không chắc chắn, hãy thẳng thắn trả lời: 'Xin lỗi, tôi không biết.'");

    // 3. FACADE PATTERN: PROXY GETTER/SETTER CHO UI (Giữ nguyên cấu trúc gọi từ UI)
    // - Proxy Metrics
    get metrics() { return this.monitor.hardware; }
    get datasetStats() { return this.monitor.dataset; }
    fetchMetrics = () => this.monitor.fetch(this.isLoading);

    // - Proxy Codebase
    get codebasePath() { return this.codebase.path; }
    set codebasePath(v) { this.codebase.path = v; }
    get extensionsInput() { return this.codebase.extensionsInput; }
    set extensionsInput(v) { this.codebase.extensionsInput = v; }
    get codeTree() { return this.codebase.tree; }
    get isScanning() { return this.codebase.isScanning; }

    scanCodebase = () => this.codebase.scan();
    toggleCollapse = (p: string) => this.codebase.toggleCollapse(p);
    isCollapsed = (p: string) => this.codebase.isCollapsed(p);
    toggleIgnore = (p: string, t: 'file'|'folder') => this.codebase.toggleIgnore(p, t);
    isIgnored = (p: string, t: 'file'|'folder') => this.codebase.isIgnored(p, t);

    get totalTokens() {
        return this.messages.reduce((sum, m) => sum + (m.context_length || 0), 0);
    }

    // 4. LOGIC CHAT CORE
    processImageFile(file: File | null): void {
        if (!file || !file.type.startsWith('image/')) return;
        const reader = new FileReader();
        reader.onload = (e) => { if (e.target?.result) this.selectedImage = e.target.result as string; };
        reader.readAsDataURL(file);
    }

    handlePaste = (e: ClipboardEvent): void => {
        const items = e.clipboardData?.items;
        if (!items) return;
        for (let item of items) {
            if (item.type.indexOf('image') !== -1) {
                e.preventDefault();
                this.processImageFile(item.getAsFile());
                break;
            }
        }
    }

    handleKeydown = (e: KeyboardEvent): void => {
        if (e.key === 'Enter') {
            if (e.ctrlKey) this.currentInput += '\n';
            else if (!e.shiftKey) { e.preventDefault(); this.sendMessage(); }
        }
    }

    handleModeChange = () => {
        if (this.mode === "chat") { this.temperature = 0.5; this.topP = 0.9; } 
        else { this.temperature = 0.1; this.topP = 0.2; }
    };

    async sendMessage(): Promise<void> { 
        if (!this.currentInput.trim() && !this.selectedImage) return; 
        
        if (this.mode !== "chat" && this.systemPrompt) {
            this.systemPrompt = ""; 
        }
        
        const userText = this.currentInput; 
        const userImg = this.selectedImage; 
        const sysPrompt = this.systemPrompt; 
        
        // ĐÃ VÁ LỖI CHÍ MẠNG: Không push system prompt vào mảng messages gốc của UI nữa
        this.messages.push({ role: 'user', content: userText, image: userImg }); 
        
        // 1. Ánh xạ mảng UI sang cấu trúc API
        const mappedMessages: APIMessage[] = this.messages.map(msg => { 
            if (msg.role === 'assistant') return { role: 'assistant', content: msg.content }; 
            if (msg.role === 'system') return { role: 'system', content: msg.content }; 
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

        // 2. INJECT SYSTEM PROMPT VÀO ĐẦU MẢNG ĐỂ GỬI ĐI (LUÔN LÀ INDEX 0) [3]
        const apiMessages: APIMessage[] = [];
        if (sysPrompt && this.mode === 'chat') {
            apiMessages.push({ role: 'system', content: sysPrompt });
        }
        apiMessages.push(...mappedMessages); // Nối tiếp lịch sử hội thoại sạch

        this.currentInput = ""; 
        this.selectedImage = null; 
        this.isLoading = true; 
        
        this.messages.push({ 
            role: 'assistant', 
            content: '', 
            db_id: null, 
            status: 'pending', 
            isEditing: false, 
            editContent: '' 
        }); 
        
        const aiIndex = this.messages.length - 1; 

        try {
            const URL = `${API_BASE_URL}/v1/${this.mode === 'chat' ? 'chat' : `agent/${this.mode}`}`;
            const payload: any = { 
                messages: apiMessages,
                temperature: this.temperature, 
                top_p: this.topP 
            };

            if (this.mode === 'coding') {
                payload.coding_context = this.codebase.path || null;
                payload.step = "start";
            }

            const response = await fetch(URL, { 
                method: 'POST', 
                headers: { 'Content-Type': 'application/json' }, 
                body: JSON.stringify(payload) 
            }); 
            
            if (this.mode === 'chat' && response.body) {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = ""; 

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    buffer += decoder.decode(value, { stream: true });
                    const lines = buffer.split('\n');
                    buffer = lines.pop() || "";

                    for (const line of lines) {
                        if (line.trim() === "") continue;
                        if (line.startsWith("data: ")) {
                            const jsonStr = line.replace("data: ", "").trim();
                            if (jsonStr === "[DONE]") continue;
                            
                            try {
                                const data = JSON.parse(jsonStr);
                                if (data.type === "text") {
                                    this.messages[aiIndex].content += data.content;
                                } else if (data.type === "metadata") {
                                    this.monitor.hardware.throughput = data.metrics.throughput_tps;
                                    this.messages[aiIndex].context_length = data.metrics.context_length;
                                    this.messages[aiIndex].elapsed_time_sec = data.metrics.elapsed_time_sec;
                                    this.messages[aiIndex].generated_tokens = data.metrics.generated_tokens;

                                    const elapsed = data.metrics.elapsed_time_sec;
                                    const genTokens = data.metrics.generated_tokens;
                                    const currentSpeed = elapsed > 0 ? (genTokens / elapsed) : 0;
                                    const oldThroughput = this.monitor.hardware.throughput;
                                    const newThroughput = oldThroughput === 0 ? currentSpeed : (oldThroughput + currentSpeed) / 2;
                                    this.monitor.hardware.throughput = Math.round(newThroughput * 100) / 100;
                                }
                            } catch (e) {
                                console.error("Lỗi Parse JSON Stream:", e);
                            }
                        }
                    }
                }
            } else if (this.mode !== 'chat' && response.ok) {
                const data = await response.json();
                
                if (this.mode === 'coding') {
                    this.messages[aiIndex].content = data.desc;
                    this.messages[aiIndex].codingPlan = data;
                } else {
                    this.messages[aiIndex].content = data.content || data.desc || JSON.stringify(data, null, 2);
                }

                if (data.metrics) {
                    this.monitor.hardware.throughput = data.metrics.throughput_tps || 0;
                    this.messages[aiIndex].context_length = data.metrics.context_length || 0;
                }
            }

            try {
                const createRes = await fetch(`${API_BASE_URL}/database/create`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt: userText, image: userImg, response: this.mode === 'coding' ? JSON.stringify(this.messages[aiIndex].codingPlan) : this.messages[aiIndex].content })
                });
                if (createRes.ok) {
                    const createData = await createRes.json();
                    this.messages[aiIndex].db_id = createData.id;
                }
            } catch (e) {
                this.messages[aiIndex].db_id = "mock-id-" + Date.now();
            }
        } catch (error) {
            this.messages[aiIndex].content = "Lỗi kết nối Backend!";
        } finally {
            this.isLoading = false;
        }
    }

    async updateDataset(index: number, action: 'approved' | 'edited' | 'discarded'): Promise<void> {
        const msg = this.messages[index];
        if (!msg.db_id) return;
        
        let payload: { status: typeof action; human_corrected: string | null } = { status: action, human_corrected: null };
        
        if (action === 'approved') {
            msg.status = 'approved';
            payload.human_corrected = msg.content;
        } else if (action === 'edited') {
            msg.status = 'edited';
            msg.content = msg.editContent ?? '';
            msg.isEditing = false;
            payload.human_corrected = msg.content;
        } else if (action === 'discarded') {
            msg.status = 'discarded';
        }
        
        await fetch(`${API_BASE_URL}/database/update/${msg.db_id}`, {
            method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload)
        });
    }
}