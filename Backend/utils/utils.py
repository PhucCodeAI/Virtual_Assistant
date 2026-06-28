import os
from utils.logger import get_logger

log = get_logger(__name__)

def _get_optimal_threads() -> int:
    """
    Docstring: Tự động tính toán số lượng threads tối ưu cho bộ thực thi llama.cpp.
    
    Thuật toán tối ưu phần cứng (Tháng 6/2026):
    - Đối với kiến trúc lai (Hybrid CPU như Intel thế hệ 12, 13, 14), việc dùng toàn bộ luồng ảo (Hyper-threading) sẽ làm giảm throughput của AI do dính vào nhân E-Core chậm.
    - Điểm ngọt hiệu năng (Sweet Spot) là bằng đúng số NHÂN THỰC (Physical P-Cores).
    - Với chíp i5-12400F (6 nhân thực, 12 luồng), hàm sẽ tự động trả về 6.
    """
    try:
        logical_cores = os.cpu_count() or 4
        
        if logical_cores > 4:
            optimal_threads = logical_cores // 2
        else:
            optimal_threads = logical_cores
            
        log.info(f"Phát hiện {logical_cores} luồng. Chọn cấu hình tối ưu: {optimal_threads} threads.")
        return optimal_threads
        
    except Exception:
        return 4