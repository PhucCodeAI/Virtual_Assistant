import psutil
import pynvml
import logging
from repositories.database import DataBase
from dtos.metrics import MetricsResponse

try:
    pynvml.nvmlInit()
    HAS_GPU = True
except pynvml.NVMLError:
    HAS_GPU = False
    logging.warning("Không tìm thấy GPU NVIDIA hoặc chưa cài Driver!")

class HardwareMonitor:
    @staticmethod
    def get_metrics(db_instance: DataBase) -> MetricsResponse:
        """
        Lấy thông số CPU, RAM và VRAM hiện tại.
        Trả về MetricsResponse
        """
        # 1. CPU Usage (%)
        # interval=None để lấy tức thời (non-blocking), không làm chậm API
        cpu_usage = psutil.cpu_percent(interval=None) 
        
        # 2. RAM Usage (GB)
        ram_info = psutil.virtual_memory()
        ram_used_gb = round(ram_info.used / (1024 ** 3), 1)
        
        # 3. GPU VRAM Usage (GB)
        gpu_vram_gb = 0.0
        if HAS_GPU:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0) # Lấy GPU đầu tiên (GTX 1660S)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                gpu_vram_gb = round(mem_info.used / (1024 ** 3), 1)
            except pynvml.NVMLError as e:
                logging.error(f"Lỗi đọc VRAM: {e}")

        return MetricsResponse(
            cpu=cpu_usage,
            ram=ram_used_gb,
            gpu_vram=gpu_vram_gb,
            throughput=0,
            dataset_stats=db_instance.get_stats()
        )
    
if __name__ == "__main__":
    db = DataBase()
    print(HardwareMonitor.get_metrics(db))