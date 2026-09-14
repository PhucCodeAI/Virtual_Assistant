import json

import lancedb
import pyarrow as pa
from config import configs
from services.embedding_engine import EmbeddingEngine


class VectorDB:
    """
    Embedded VectorDB using LanceDB.
    Disk-based storage, low RAM consumption, built-in search algorithms.
    """

    def __init__(self, embedding: EmbeddingEngine) -> None:
        """
        Initialize the VectorDB connection and table using configurations.

        -Input: None
        -Output: None
        """
        self.db = lancedb.connect(configs.vectordb.vector_db_path)
        self.embedding = embedding

        self.table_name = "agent_knowledge"
        self.table = self._init_table()

    def _init_table(self) -> lancedb.Table:
        """
        Initialize the database table if it does not exist, defining a clear schema.

        -Input: None
        -Output: lancedb.Table (The LanceDB table object for CRUD operations)
        """
        if self.table_name in self.db.table_names():
            return self.db.open_table(self.table_name)

        schema = pa.schema(
            [
                pa.field("vector", pa.list_(pa.float32(), configs.embedding.dim)),
                pa.field("text_content", pa.string()),
                pa.field("json_payload", pa.string()),
            ]
        )
        return self.db.create_table(self.table_name, schema=schema)

    def add_record(self, text: list[str], json_payload: list[dict]) -> None:
        """
        Encode texts into vectors and batch insert them into the disk.
        Automatically rebuilds the Full-Text Search (FTS) index for keyword queries.

        -Input: text (list[str], List of text strings to be embedded and stored)
        -Input: json_payload (list[dict], List of metadata dictionaries corresponding to the texts)
        -Output: None
        """
        vectors = self.embedding.get_embeddings(text)

        data = []
        for i in range(len(text)):
            data.append(
                {
                    "vector": vectors[i],
                    "text_content": text[i],
                    "json_payload": json.dumps(json_payload[i], ensure_ascii=False),
                }
            )

        self.table.add(data)

        self.table.create_fts_index("text_content", replace=True)
        print(
            f"[LanceDB] Batch saved {len(text)} records to disk and updated FTS index."
        )

    def search(
        self, query: str, top_k: int = 3, search_type: str = "vector"
    ) -> list[dict]:
        """
        Search the database using vector similarity, keyword (FTS), or hybrid search.

        -Input: query (str, The search query string)
        -Input: top_k (int, Number of top results to return. Default is 3)
        -Input: search_type (str, Type of search: 'vector', 'keyword', or 'hybrid'. Default is 'vector')
        -Output: list[dict] (List of dictionaries containing score, text, and metadata)
        """
        if search_type not in ["vector", "keyword", "hybrid"]:
            raise ValueError("search_type must be 'vector', 'keyword', or 'hybrid'")

        if search_type == "vector":
            query_vec = self.embedding.get_embeddings([query])
            results = (
                self.table.search(query_vec, query_type="vector").limit(top_k).to_list()
            )

        elif search_type == "keyword":
            results = self.table.search(query, query_type="fts").limit(top_k).to_list()

        elif search_type == "hybrid":
            query_vec = self.embedding.get_embeddings([query])
            results = (
                self.table.search(query, query_type="hybrid")
                .vector(query_vec)
                .limit(top_k)
                .to_list()
            )

        formatted_results = []
        for res in results:
            if "score" in res:
                score = res["score"]
            else:
                score = 1.0 - res.get("_distance", 0.0)

            formatted_results.append(
                {
                    "score": score,
                    "text": res["text_content"],
                    "data": json.loads(res["json_payload"]),
                }
            )

        return formatted_results


if __name__ == "__main__":
    embedding = EmbeddingEngine()
    vdb = VectorDB(embedding)
    vdb.add_record(["Đố bạn biết tôi là ai?"], [{"source": "fun"}])
    results = vdb.search("trợ lý ảo")
    print(results)
