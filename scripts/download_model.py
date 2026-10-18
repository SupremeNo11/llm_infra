"""下载 Qwen3-0.6B 模型权重到本地 models/ 目录。

用法:
    uv run python scripts/download_model.py

国内网络可先设置镜像:
    export HF_ENDPOINT=https://hf-mirror.com
"""

from pathlib import Path

from huggingface_hub import snapshot_download

MODEL_ID = "Qwen/Qwen3-0.6B"
TARGET_DIR = Path(__file__).resolve().parent.parent / "models" / "Qwen3-0.6B"


def main() -> None:
    snapshot_download(
        repo_id=MODEL_ID,
        local_dir=str(TARGET_DIR),
    )
    print(f"模型已下载至 {TARGET_DIR}")


if __name__ == "__main__":
    main()
