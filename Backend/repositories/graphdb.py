import gzip
import os
import pickle

import networkx as nx
from config import configs


class GraphDB:
    """Hệ thống quản lý bộ nhớ đồ thị tri thức của Agent (Repository Layer)"""

    def __init__(self, llm=None, embedding=None) -> None:
        """Khởi tạo thực thể và cấu hình lưu trữ đồ thị"""
        self.storage_path: str = configs.graphdb.graph_db_path
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        self.graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self._load_memory()

        self.llm = llm
        self.embedding = embedding

    def _load_memory(self) -> None:
        """Nạp đồ thị từ file nhị phân nén gzip vào RAM."""
        if os.path.exists(self.storage_path):
            try:
                # FIX LỖI 2: Mở trực tiếp file path qua gzip.open
                with gzip.open(self.storage_path, "rb") as f:
                    self.graph = pickle.load(f)
            except Exception as e:
                print(f"[GraphDB] Lỗi load memory: {e}. Tạo đồ thị mới.")
                self.graph = nx.MultiDiGraph()

    def save_memory(self) -> None:
        """Nén và đóng băng đồ thị từ RAM xuống ổ cứng (Public method)."""
        # FIX LỖI 2: Mở trực tiếp file path qua gzip.open
        with gzip.open(self.storage_path, "wb") as f:
            pickle.dump(self.graph, f)

    def update_edge_status(
        self, source: str, target: str, relation: str, status: str
    ) -> bool:
        """
        FIX LỖI 1: Hàm bị thiếu mà GraphEngine đang gọi.
        Cập nhật trạng thái của một relation cụ thể giữa source và target trong MultiDiGraph.
        """
        if not self.graph.has_edge(source, target):
            return False

        edge_data_dict = self.graph.get_edge_data(source, target)
        updated = False

        if isinstance(edge_data_dict, dict):
            for key, data in edge_data_dict.items():
                if isinstance(data, dict) and data.get("relation") == relation:
                    data["status"] = status
                    updated = True

        return updated

    def add_node(self, name: str, description: str, embedding: list[float]) -> bool:
        """Thêm node mới vào đồ thị nếu chưa tồn tại."""
        if name not in self.graph:
            self.graph.add_node(name, description=description, embedding=embedding)
            return True
        return False

    def add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        lifespan_type: str,
        updated_at: str,
    ) -> bool:
        """Thêm edge mới vào đồ thị."""
        edge_attrs = {
            "relation": relation,
            "lifespan_type": lifespan_type,
            "updated_at": updated_at,
        }
        if lifespan_type == "short":
            edge_attrs["status"] = "active"

        self.graph.add_edge(source, target, **edge_attrs)
        return True

    def archive_resolved_edges(self) -> int:
        """Hàm dọn dẹp RAM ngầm: Chuyển các quan hệ 'resolved' thành 'archived'."""
        archive_count = 0

        for u, v, key, data in self.graph.edges(keys=True, data=True):
            if (
                isinstance(data, dict)
                and data.get("lifespan_type") == "short"
                and data.get("status") == "resolved"
            ):
                self.graph[u][v][key]["status"] = "archived"
                archive_count += 1

        if archive_count > 0:
            self.save_memory()

        return archive_count
