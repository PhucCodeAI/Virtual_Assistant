// src/lib/state/metrics.svelte.ts
import { API_BASE_URL } from './config';
import type { Metrics, DatasetStats } from './types';

export class MetricsService {
    hardware = $state<Metrics>({ cpu: 0, ram: 0, gpu_vram: 0, throughput: 0 });
    dataset = $state<DatasetStats>({ sft: 0, dpo: 0 });

    async fetch(isChatLoading: boolean) {
        try {
            const res = await fetch(`${API_BASE_URL}/v1/metrics`);
            if (!res.ok) return;
            const data = await res.json();
            
            this.hardware.cpu = data.cpu;
            this.hardware.ram = data.ram;
            this.hardware.gpu_vram = data.gpu_vram;
            
            // ĐÃ XOÁ DÒNG GHI ĐÈ THROUGHPUT TỪ API ĐỂ GIỮ NGUYÊN GIÁ TRỊ MEAN TRUNG BÌNH TỰ TÍNH
            
            if (data.dataset_stats) {
                this.dataset.sft = data.dataset_stats.sft;
                this.dataset.dpo = data.dataset_stats.dpo;
            }
        } catch (error) {
            console.error("Monitor Error:", error);
        }
    }
}