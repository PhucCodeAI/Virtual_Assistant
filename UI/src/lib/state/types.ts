export interface CodeNode { 
    name: string; 
    path: string; 
    type: 'file' | 'folder'; 
    children?: CodeNode[]; 
} 

export interface CodingPlan {
    desc: string;
    steps: { step: number; action: string; target: string; }[];
}

export interface Message { 
    systemPrompt?: string; 
    role: 'user' | 'assistant' | 'system'; 
    content: string; 
    image?: string | null; 
    db_id?: string | number | null; 
    status?: 'pending' | 'approved' | 'edited' | 'discarded'; 
    isEditing?: boolean; 
    editContent?: string; 
    mode?: 'chat' | 'coding' | 'research' | 'analysis'; 
    codingPlan?: CodingPlan; 
    context_length?: number; 
    elapsed_time_sec?: number;
    generated_tokens?: number;
}

export interface APIMessage { 
    role: 'user' | 'assistant' | 'system'; 
    content: string | Array<{ type: 'image_url' | 'text'; image_url?: { url: string }; text?: string }>; 
} 

export interface Metrics { 
    cpu: number; 
    ram: number; 
    gpu_vram: number; 
    throughput: number; 
} 

export interface DatasetStats { 
    sft: number; 
    dpo: number; 
}