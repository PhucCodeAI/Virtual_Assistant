import os
import ssl

from config import configs
from huggingface_hub import hf_hub_download
from utils.logger import get_logger

log = get_logger(__name__)
ssl._create_default_https_context = ssl._create_unverified_context

def setup() -> dict[str, str]:
    """
    Tự động tải weight của LLM.
    """

    if not os.path.isfile(os.path.join(configs.setup.model_folder, configs.setup.llm_file_name)):
        log.info(f"\nStarting download for LLM model (GGUF) from '{configs.setup.llm_repo_id}'")
        try:
            llm_path = hf_hub_download(
                repo_id=configs.setup.llm_repo_id,
                filename=configs.setup.llm_file_name,
                local_dir=configs.setup.model_folder,
                local_dir_use_symlinks=False
            )
            log.info(f"Successfully downloaded LLM model to: {llm_path}")
        except Exception as e:
            log.error(f"Failed to download LLM model: {e}")

    else:
        llm_path = os.path.join(configs.setup.model_folder, configs.setup.llm_file_name)

    log.info("=== SETUP COMPLETED SUCCESSFULLY ===")

    return llm_path

if __name__ == "__main__":
    setup()
