"""
Model Manager — selects, downloads, and locates the GGUF model file.

Models are stored in ~/.pulsefeed/models/ so they persist across app updates.
Download progress is exposed via a module-level state dict that the
/system/model-progress endpoint streams to the frontend.
"""
from __future__ import annotations

import json
import logging
import platform
import urllib.request
from pathlib import Path
from typing import Any

import psutil

logger = logging.getLogger(__name__)

# ── Model catalogue ───────────────────────────────────────────────────────────
# All URLs point to quantised GGUF files on HuggingFace.
# Q4_K_M is the best quality/speed/size tradeoff for CPU + Metal + CUDA.

_MODELS: dict[str, dict[str, Any]] = {
    "tiny": {
        "name": "Qwen2.5-1.5B-Instruct-Q4_K_M",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "url": (
            "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF"
            "/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
        ),
        "size_gb": 1.0,
        "min_ram_gb": 2.0,
        "n_ctx": 4096,
    },
    "small": {
        "name": "Llama-3.2-3B-Instruct-Q4_K_M",
        "filename": "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "url": (
            "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF"
            "/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf"
        ),
        "size_gb": 2.0,
        "min_ram_gb": 4.0,
        "n_ctx": 2048,
    },
    "medium": {
        "name": "Llama-3.1-8B-Instruct-Q4_K_M",
        "filename": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        "url": (
            "https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF"
            "/resolve/main/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"
        ),
        "size_gb": 4.7,
        "min_ram_gb": 8.0,
        "n_ctx": 2048,
    },
}

# ── Download progress state ────────────────────────────────────────────────────
# Read by routes/system.py to stream progress to the frontend.

state: dict[str, Any] = {
    "status": "idle",         # idle | checking | downloading | loading | ready | error
    "model_name": "",
    "model_tier": "",
    "progress": 0.0,          # 0.0 – 1.0 during download
    "downloaded_bytes": 0,
    "total_bytes": 0,
    "gpu_type": "cpu",
    "ram_gb": 0.0,
    "error": None,
}

# ── Helpers ───────────────────────────────────────────────────────────────────

_MODELS_DIR = Path.home() / ".pulsefeed" / "models"
_CONFIG_FILE = Path.home() / ".pulsefeed" / "config.json"


def _available_ram_gb() -> float:
    return psutil.virtual_memory().available / (1024 ** 3)


def _detect_gpu() -> str:
    """Return 'metal', 'cuda', or 'cpu'."""
    system = platform.system()
    if system == "Darwin" and platform.machine() == "arm64":
        return "metal"
    if system == "Windows":
        try:
            import subprocess
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                return "cuda"
        except Exception:
            pass
    return "cpu"


def select_tier(ram_gb: float) -> dict[str, Any]:
    if ram_gb >= _MODELS["medium"]["min_ram_gb"]:
        return _MODELS["medium"]
    if ram_gb >= _MODELS["small"]["min_ram_gb"]:
        return _MODELS["small"]
    return _MODELS["tiny"]


def _save_config(model_path: str, gpu_type: str, n_ctx: int) -> None:
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps({
        "model_path": model_path,
        "gpu_type": gpu_type,
        "n_ctx": n_ctx,
    }))


def load_config() -> dict[str, Any] | None:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text())
        except Exception:
            pass
    return None


# ── Main entry point ──────────────────────────────────────────────────────────


def prepare_model() -> dict[str, Any]:
    """
    Called once at startup (from main.py lifespan, in a thread).

    1. Detect RAM + GPU
    2. Select appropriate model tier
    3. Download model if not already present (streams progress into state{})
    4. Persist config so next launch skips download
    5. Return {"model_path": str, "gpu_type": str, "n_ctx": int}

    Set PULSEFEED_NO_LLM=1 to skip model download entirely (testing / CI).
    """
    import os
    if os.environ.get("PULSEFEED_NO_LLM"):
        state["status"] = "disabled"
        state["model_name"] = "none (PULSEFEED_NO_LLM set)"
        return {"model_path": "", "gpu_type": "cpu", "n_ctx": 2048}

    state["status"] = "checking"

    ram_gb = _available_ram_gb()
    gpu_type = _detect_gpu()
    tier = select_tier(ram_gb)

    state["ram_gb"] = round(ram_gb, 1)
    state["gpu_type"] = gpu_type
    state["model_name"] = tier["name"]
    state["model_tier"] = next(k for k, v in _MODELS.items() if v is tier)

    logger.info(
        "System: ram=%.1f GB gpu=%s → model tier=%s (%s)",
        ram_gb, gpu_type, state["model_tier"], tier["name"],
    )

    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model_path = _MODELS_DIR / tier["filename"]

    if not model_path.exists():
        _download(tier["url"], model_path, tier["name"])
    else:
        logger.info("Model already present: %s", model_path)
        state["status"] = "loading"

    config = {"model_path": str(model_path), "gpu_type": gpu_type, "n_ctx": tier["n_ctx"]}
    _save_config(**config)
    return config


def _download(url: str, dest: Path, name: str) -> None:
    """Stream-download with progress tracking into state{}."""
    state["status"] = "downloading"
    state["progress"] = 0.0
    state["downloaded_bytes"] = 0
    state["total_bytes"] = 0

    logger.info("Downloading %s → %s", name, dest)

    tmp = dest.with_suffix(".part")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PulseFeed/3.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            state["total_bytes"] = total
            chunk = 1024 * 256  # 256 KB chunks
            downloaded = 0
            with open(tmp, "wb") as f:
                while True:
                    data = resp.read(chunk)
                    if not data:
                        break
                    f.write(data)
                    downloaded += len(data)
                    state["downloaded_bytes"] = downloaded
                    state["progress"] = (downloaded / total) if total else 0.0
        tmp.rename(dest)
        state["progress"] = 1.0
        logger.info("Download complete: %s", dest)
    except Exception as exc:
        if tmp.exists():
            tmp.unlink()
        state["status"] = "error"
        state["error"] = str(exc)
        logger.error("Model download failed: %s", exc)
        raise
