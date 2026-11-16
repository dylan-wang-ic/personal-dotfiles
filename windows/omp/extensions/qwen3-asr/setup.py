"""One-time install of the Qwen3-ASR worker's environment. Safe to re-run.

Creates ~/.omp/qwen3-asr/venv, installs PyTorch (CUDA build when an NVIDIA GPU is present) and the
qwen-asr package, then downloads the model weights into the Hugging Face cache (about 6 GB in all).
The omp extension (index.ts) offers to run this when the environment is missing.
"""
import os
import shutil
import subprocess
import sys

ROOT = os.path.join(os.path.expanduser("~"), ".omp", "qwen3-asr")
VENV = os.path.join(ROOT, "venv")
PYTHON = os.path.join(VENV, "Scripts", "python.exe")
MODEL = "Qwen/Qwen3-ASR-0.6B"
QWEN_ASR = "qwen-asr==0.0.6"  # the version this was built and tested against
CUDA_INDEX = "https://download.pytorch.org/whl/cu128"


def run(*cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.check_call(list(cmd))


def main():
    if sys.version_info < (3, 10):
        sys.exit("Python 3.10 or newer is required")
    os.makedirs(ROOT, exist_ok=True)
    if not os.path.exists(PYTHON):
        run(sys.executable, "-m", "venv", VENV)
    run(PYTHON, "-m", "pip", "install", "--upgrade", "pip")
    torch = ["torch", "--index-url", CUDA_INDEX] if shutil.which("nvidia-smi") else ["torch"]
    run(PYTHON, "-m", "pip", "install", *torch)
    run(PYTHON, "-m", "pip", "install", QWEN_ASR)
    run(PYTHON, "-c", f"from huggingface_hub import snapshot_download; print(snapshot_download('{MODEL}'))")
    run(PYTHON, "-c", "import torch, qwen_asr; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())")
    print("Qwen3-ASR environment is ready.", flush=True)


if __name__ == "__main__":
    main()
