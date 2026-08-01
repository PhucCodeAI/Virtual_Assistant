import os
import ssl
from huggingface_hub import snapshot_download, hf_hub_download

from config import configs
from utils.logger import get_logger


log = get_logger(__name__)
ssl._create_default_https_context = ssl._create_unverified_context

def setup() -> dict[str, str]:
    """
    Tải Embedding và LLM.
    """
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.join(base_dir, configs.setup.model_folder)
    embedding_dir = os.path.join(models_dir, "gte-multilingual-base")

    if not os.path.isdir(embedding_dir):
        os.makedirs(models_dir, exist_ok=True)
        log.info(f"Created target directory: {models_dir}")
        # 1. Tải Embedding Model
        log.info(f"\nStarting download for Embedding model: '{configs.setup.embedding_repo}'")
        try:
            snapshot_download(
                repo_id=configs.setup.embedding_repo,
                local_dir=embedding_dir,
                local_dir_use_symlinks=False,
                ignore_patterns=["*.msgpack", "*.h5", "*.ot"]
            )
            log.info(f"Successfully downloaded Embedding model to: {embedding_dir}")
        except Exception as e:
            log.error(f"Failed to download Embedding model: {e}")

    # 2. Tải LLM GGUF Model (Sử dụng thư viện chuyên dụng thay cho urllib)
    if not os.path.isfile(os.path.join(models_dir, configs.setup.file_name)):
        log.info(f"\nStarting download for LLM model (GGUF) from xxx")
        try:
            # Tự động bóc tách repo_id và filename từ URL cấu hình trong file config
            # Ví dụ: configs.setup.llm_url = "xxx/unsloth/Qwen3.5-2B-GGUF/resolve/main/Qwen3.5-2B-UD-Q4_K_XL.gguf"
            llm_path = hf_hub_download(
                repo_id=configs.setup.llm_repo_id,
                filename=configs.setup.file_name,
                local_dir=models_dir,
                local_dir_use_symlinks=False
            )
            log.info(f"Successfully downloaded LLM model to: {llm_path}")
        except Exception as e:
            log.error(f"Failed to download LLM model: {e}")

    else:
        llm_path = os.path.join(models_dir, configs.setup.file_name)

    log.info("=== SETUP COMPLETED SUCCESSFULLY ===")

    return embedding_dir, llm_path

if __name__ == "__main__":
    setup()
