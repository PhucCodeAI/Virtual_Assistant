import torch
from typing import List
from config import configs
import torch.nn.functional as F
from utils.utils import get_device
from transformers import AutoTokenizer, AutoModel

class EmbeddingEngine:
    """
    Class for auto load and manage embedding model for vectorization.
    """
    def __init__(self, model_name: str = configs.embedding.model_name, cache_path: str = configs.embedding.cache_path, batch_size: int = configs.embedding.batch_size) -> None:
        self.device = get_device()
        self.model_name = model_name
        self.cache_path = cache_path
        self.batch_size = batch_size
        self.load_model()
    
    def load_model(self) -> None:
        """
        Load the embedding model and tokenizer.
        """     
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name, 
            cache_dir=self.cache_path,
            trust_remote_code=True
        )
        self.model = AutoModel.from_pretrained(
            self.model_name, 
            cache_dir=self.cache_path,
            trust_remote_code=True
        ).to(self.device)

        self.model.eval()


    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Xử lý hàng loạt danh sách văn bản và trả về mảng danh sách các vector 768 chiều.
        Có chia nhỏ dữ liệu theo batch_size để tránh tràn bộ nhớ (OOM).
        """
        all_embeddings = []
        
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i:i + self.batch_size]
            
            inputs = self.tokenizer(
                batch_texts, 
                max_length=configs.embedding.max_length,
                padding=True,
                truncation=True, 
                return_tensors="pt"
            ).to(self.device)

            with torch.no_grad():
                model_output = self.model(
                    input_ids=inputs['input_ids'],
                    attention_mask=inputs['attention_mask']
                )
                
            batch_embeddings = self.mean_pooling(model_output.last_hidden_state, inputs['attention_mask'])
            batch_embeddings = F.normalize(batch_embeddings, p=2, dim=1)
            all_embeddings.append(batch_embeddings.cpu())

        return torch.cat(all_embeddings, dim=0).tolist()

    @staticmethod
    def mean_pooling(model_output, attention_mask) -> torch.Tensor:
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(model_output.size()).float()
        sum_embeddings = torch.sum(model_output * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        return sum_embeddings / sum_mask
    
if __name__ == "__main__":
    test_text = "Test thử xem như nào nhé"
    print("\n--- Đang tính toán vector embedding... ---")

    embedding = EmbeddingEngine()
    
    try:
        vector = torch.tensor(embedding.get_embeddings([test_text]))
        print(f"🔹 Kích cỡ vector: {vector.size()}")
    except Exception as e:
        print(f"\n❌ Thất bại do: {str(e)}")
