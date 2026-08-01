import torch
import torch.nn.functional as F
from config import configs
from transformers import AutoModel, AutoTokenizer
from utils.utils import get_device


class EmbeddingEngine:
    """
    Class for auto load and manage embedding model for vectorization.
    """

    def __init__(
        self, embedding_dir: str, batch_size: int = configs.embedding.batch_size
    ) -> None:
        self.device = get_device()
        self.embedding_dir = embedding_dir
        self.batch_size = batch_size
        self.load_model()

    def load_model(self) -> None:
        """
        Load the embedding model and tokenizer.
        """
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.embedding_dir, trust_remote_code=True, local_files_only=True
        )
        self.model = AutoModel.from_pretrained(
            self.embedding_dir, trust_remote_code=True, local_files_only=True
        ).to(self.device)

        self.model.eval()

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Xử lý hàng loạt danh sách văn bản và trả về mảng danh sách các vector 768 chiều.
        Có chia nhỏ dữ liệu theo batch_size để tránh tràn bộ nhớ (OOM).
        """
        all_embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]

            inputs = self.tokenizer(
                batch_texts,
                max_length=configs.embedding.max_length,
                padding=True,
                truncation=True,
                return_tensors="pt",
            ).to(self.device)

            with torch.no_grad():
                model_output = self.model(
                    input_ids=inputs["input_ids"],
                    attention_mask=inputs["attention_mask"],
                )

            batch_embeddings = self.mean_pooling(
                model_output.last_hidden_state, inputs["attention_mask"]
            )
            batch_embeddings = F.normalize(batch_embeddings, p=2, dim=1)
            all_embeddings.append(batch_embeddings.cpu())

        return torch.cat(all_embeddings, dim=0).tolist()

    @staticmethod
    def mean_pooling(model_output, attention_mask) -> torch.Tensor:
        input_mask_expanded = (
            attention_mask.unsqueeze(-1).expand(model_output.size()).float()
        )
        sum_embeddings = torch.sum(model_output * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        return sum_embeddings / sum_mask


if __name__ == "__main__":
    test_text = "Test thử xem như nào nhé"
    print("\n--- Đang tính toán vector embedding... ---")

    embedding = EmbeddingEngine(embedding_dir="static/models/gte-multilingual-base")

    try:
        vector = torch.tensor(embedding.get_embeddings([test_text]))
        print(f"🔹 Kích cỡ vector: {vector.size()}")
    except Exception as e:
        print(f"\n❌ Thất bại do: {str(e)}")
