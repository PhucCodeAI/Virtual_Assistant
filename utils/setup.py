import os
import ssl

from config import configs
from huggingface_hub import hf_hub_download
from loguru import logger

ssl._create_default_https_context = ssl._create_unverified_context


def setup() -> str:
    """
    Tự động tải weight của LLM.
    """

    if not os.path.isfile(
        os.path.join(configs.setup.model_folder, configs.setup.llm_file_name)
    ):
        logger.info(
            f"\nStarting download for LLM model (GGUF) from '{configs.setup.llm_repo_id}'"
        )
        try:
            llm_path = hf_hub_download(
                repo_id=configs.setup.llm_repo_id,
                filename=configs.setup.llm_file_name,
                local_dir=configs.setup.model_folder,
                local_dir_use_symlinks=False,
            )
            logger.info(f"Successfully downloaded LLM model to: {llm_path}")
        except Exception as e:
            logger.error(f"Failed to download LLM model: {e}")

    else:
        llm_path = os.path.join(configs.setup.model_folder, configs.setup.llm_file_name)

    logger.info("=== SETUP COMPLETED SUCCESSFULLY ===")

    return llm_path


if __name__ == "__main__":
    setup()
