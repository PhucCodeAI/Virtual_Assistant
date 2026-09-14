from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
from repositories.graphdb import GraphDB


class GraphEngine:
    """Lớp xử lý logic nghiệp vụ cho hệ thống GraphRAG (Service Layer)"""

    def __init__(self, graph_repo: GraphDB, llm, embedding) -> None:
        self.graph_db = graph_repo
        self.llm = llm
        self.embedding = embedding

    def _cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        norm = np.linalg.norm(v1) * np.linalg.norm(v2)
        if norm == 0:
            return 0.0
        return float(np.dot(v1, v2) / norm)

    def _mock_llm_extract(self, text_chunk: str) -> dict:
        """Giả lập LLM phân tích văn bản thô để trích xuất cấu trúc đồ thị JSON."""
        if "Fix bug" in text_chunk or "thực hiện" in text_chunk:
            return {
                "nodes": [
                    {"name": "Python", "description": "Ngôn ngữ lập trình"},
                    {"name": "Anh Nam", "description": "Kỹ sư phần mềm"},
                    {"name": "Task hiện tại", "description": "Fix bug hệ thống"},
                ],
                "edges": [
                    {
                        "source": "Anh Nam",
                        "relation": "sử dụng",
                        "target": "Python",
                        "lifespan_type": "static",
                    },
                    {
                        "source": "Anh Nam",
                        "relation": "đang thực hiện",
                        "target": "Task hiện tại",
                        "lifespan_type": "short",
                    },
                ],
                "updates": [],
            }
        if "xong" in text_chunk or "hoàn thành" in text_chunk:
            return {
                "nodes": [],
                "edges": [],
                "updates": [
                    {
                        "source": "Anh Nam",
                        "relation": "đang thực hiện",
                        "target": "Task hiện tại",
                        "status": "resolved",
                    }
                ],
            }
        return {"nodes": [], "edges": [], "updates": []}

    def ingest_text(self, text_chunk: str) -> None:
        """Phân tích văn bản thô để thêm mới hoặc cập nhật trạng thái quan hệ vào đồ thị."""
        current_date_str = datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).strftime(
            "%Y-%m-%d"
        )

        try:
            data = self._mock_llm_extract(text_chunk)
            has_changes = False

            # 1. Cập nhật Status
            for update in data.get("updates", []):
                if self.graph_db.update_edge_status(
                    source=update["source"],
                    target=update["target"],
                    relation=update["relation"],
                    status=update["status"],
                ):
                    has_changes = True

            # 2. Thêm Nodes thông qua hàm của Repo (Không truy cập biến .graph trực tiếp)
            for node in data.get("nodes", []):
                node_name: str = node["name"]
                if node_name not in self.graph_db.graph:
                    embedding_vector = self.embedding.get_embeddings(node_name)[0]
                    if self.graph_db.add_node(
                        name=node_name,
                        description=node.get("description", ""),
                        embedding=embedding_vector,
                    ):
                        has_changes = True

            # 3. Thêm Edges thông qua hàm của Repo
            for edge in data.get("edges", []):
                if self.graph_db.add_edge(
                    source=edge["source"],
                    target=edge["target"],
                    relation=edge["relation"],
                    lifespan_type=edge["lifespan_type"],
                    updated_at=current_date_str,
                ):
                    has_changes = True

            # 4. Lưu lại nếu có thay đổi (Gọi hàm public save_memory)
            if has_changes:
                self.graph_db.save_memory()

        except Exception as e:
            print(f"[GraphEngine] Error during ingestion: {e}")

    def retrieve_context(
        self, query: str, top_k_nodes: int = 3, include_history: bool = False
    ) -> str:
        """Tìm kiếm cụm từ khóa liên quan trên đồ thị dựa trên không gian vector."""
        graph = self.graph_db.graph
        query_emb = self.embedding.get_embeddings(query)[0]
        node_scores = []

        for node_name, node_data in graph.nodes(data=True):
            if "embedding" in node_data:
                node_emb = node_data["embedding"]
                similarity = self._cosine_similarity(query_emb, node_emb)
                node_scores.append((node_name, similarity))

        node_scores.sort(key=lambda x: x[1], reverse=True)
        target_nodes = [node for node, score in node_scores[:top_k_nodes]]

        context_lines = []
        for node in target_nodes:
            context_lines.append(
                f"Entity: {node} - {graph.nodes[node].get('description', '')}"
            )

            if graph.has_node(node):
                for neighbor in graph.neighbors(node):
                    edge_data_dict = graph.get_edge_data(node, neighbor)
                    if isinstance(edge_data_dict, dict):
                        for key in edge_data_dict:
                            edge_data = edge_data_dict[key]
                            if isinstance(edge_data, dict):
                                status = edge_data.get("status", "N/A")
                                if status == "archived" and not include_history:
                                    continue

                                rel = edge_data.get("relation", "connected")
                                lifespan = edge_data.get("lifespan_type", "unknown")
                                context_lines.append(
                                    f"  -> Relation: [{node}] --({rel})--> [{neighbor}] | Type: {lifespan} | Status: {status}"
                                )

        return "\n".join(context_lines)

    async def query_agent(self, user_question: str) -> str:
        """Hàm API của tầng Service: Tự động phân tích từ khóa, bốc context và gọi LLM trả lời."""
        history_keywords = ["lịch sử", "quá khứ", "trước đây", "đã từng", "cũ"]
        is_history_query = any(
            word in user_question.lower() for word in history_keywords
        )

        context = self.retrieve_context(user_question, include_history=is_history_query)
        if not context:
            context = "No relevant knowledge graph context found."

        prompt = f"Dựa trên ngữ cảnh đồ thị tri thức sau đây hãy trả lời câu hỏi.\nNgữ cảnh:\n{context}\n\nCâu hỏi: {user_question}"
        message = [{"role": "user", "content": prompt}]

        return await self.llm.generate_non_stream(message, temperature=0.5, top_p=0.9)
