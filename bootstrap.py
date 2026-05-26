"""
PulseFeed Bootstrap
-------------------
Single entry point for all platforms. Run this to start PulseFeed.

    python bootstrap.py          # auto-detects everything
    python bootstrap.py --reset  # wipe model cache and re-download

What this script does
─────────────────────
1. Verify Python 3.11+
2. Detect available RAM + GPU (Metal / CUDA / CPU)
3. Install Python dependencies via uv (or pip as fallback)
4. Install the GPU-optimised llama-cpp-python wheel if applicable
5. Build the React frontend if dist/ is missing
6. Start uvicorn on port 8000
7. Open http://localhost:8000 in the default browser
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent
BACKEND_DIR = ROOT / "pulsefeed" / "backend"
FRONTEND_DIR = ROOT / "pulsefeed" / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
MODELS_DIR = Path.home() / ".pulsefeed" / "models"
CONFIG_FILE = Path.home() / ".pulsefeed" / "config.json"
DEPS_MARKER = Path.home() / ".pulsefeed" / ".deps_ok"

PORT = 8000
HEALTH_URL = f"http://localhost:{PORT}/health"

# ── Colour helpers (no third-party deps) ─────────────────────────────────────

_WIN = platform.system() == "Windows"

def _c(code: str, text: str) -> str:
    if _WIN and not os.environ.get("WT_SESSION"):  # not Windows Terminal
        return text
    return f"\033[{code}m{text}\033[0m"

def ok(msg: str)   -> None: print(_c("32", f"  [✓] {msg}"))
def info(msg: str) -> None: print(_c("36", f"  [→] {msg}"))
def warn(msg: str) -> None: print(_c("33", f"  [!] {msg}"))
def err(msg: str)  -> None: print(_c("31", f"  [✗] {msg}"))
def hdr(msg: str)  -> None: print(_c("1",  f"\n{msg}"))


# ── Step 1 — Python version ───────────────────────────────────────────────────

def check_python() -> None:
    hdr("Checking system requirements")
    if sys.version_info < (3, 11):
        err(f"Python 3.11+ required — found {sys.version_info.major}.{sys.version_info.minor}")
        err("Download from https://python.org/downloads")
        sys.exit(1)
    ok(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")


# ── Step 2 — Hardware detection ───────────────────────────────────────────────

def detect_hardware() -> dict:
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        ram_gb = 4.0  # safe default if psutil not yet installed

    system = platform.system()
    machine = platform.machine()
    gpu = "cpu"

    if system == "Darwin" and machine == "arm64":
        gpu = "metal"
        ok(f"Apple Silicon detected — Metal GPU acceleration enabled")
    elif system == "Windows":
        try:
            r = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                gpu = "cuda"
                ok(f"NVIDIA GPU detected: {r.stdout.strip().splitlines()[0]}")
        except Exception:
            pass

    if gpu == "cpu":
        info(f"Running on CPU (no GPU acceleration found)")

    ok(f"RAM: {ram_gb:.1f} GB available")
    return {"ram_gb": ram_gb, "gpu": gpu, "system": system}


# ── Step 3 — Python dependencies ─────────────────────────────────────────────

def install_deps(hw: dict, force: bool = False) -> None:
    hdr("Installing dependencies")

    if DEPS_MARKER.exists() and not force:
        ok("Dependencies already installed")
        _ensure_llama_cpp(hw, force=False)
        return

    # Prefer uv, fall back to pip
    uv = shutil.which("uv")
    if uv:
        info("Installing via uv…")
        subprocess.run(
            [uv, "pip", "install", "--python", sys.executable,
             "-r", str(BACKEND_DIR / "pyproject.toml"), "--all-extras"],
            cwd=str(BACKEND_DIR), check=True,
        )
    else:
        info("uv not found — installing via pip…")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", str(BACKEND_DIR)],
            check=True,
        )

    _ensure_llama_cpp(hw, force=True)
    DEPS_MARKER.parent.mkdir(parents=True, exist_ok=True)
    DEPS_MARKER.touch()
    ok("Dependencies installed")


def _ensure_llama_cpp(hw: dict, force: bool) -> None:
    """Install the GPU-optimised llama-cpp-python wheel."""
    gpu = hw["gpu"]

    # Check if a GPU-capable version is already installed
    if not force:
        try:
            import llama_cpp  # noqa: F401
            if gpu == "cpu":
                ok("llama-cpp-python ready (CPU)")
                return
            # For GPU builds, check if the wheel matches
            if gpu == "metal" and platform.machine() == "arm64":
                ok("llama-cpp-python ready (Metal)")
                return
            if gpu == "cuda":
                ok("llama-cpp-python ready (CUDA)")
                return
        except ImportError:
            pass

    if gpu == "metal":
        info("Installing llama-cpp-python with Metal support…")
        _pip_install_llama("metal")
    elif gpu == "cuda":
        info("Installing llama-cpp-python with CUDA support…")
        _pip_install_llama("cu121")
    else:
        info("Installing llama-cpp-python (CPU)…")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade",
             "llama-cpp-python>=0.3.0"],
            check=True,
        )


def _pip_install_llama(variant: str) -> None:
    index = f"https://abetlen.github.io/llama-cpp-python/whl/{variant}"
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade",
         "--extra-index-url", index, "llama-cpp-python>=0.3.0"],
    )
    if result.returncode != 0:
        warn(f"GPU wheel unavailable for {variant} — falling back to CPU")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade",
             "llama-cpp-python>=0.3.0"],
            check=True,
        )


# ── Step 4 — Frontend build ───────────────────────────────────────────────────

def build_frontend() -> None:
    hdr("Checking frontend")
    if DIST_DIR.exists() and any(DIST_DIR.iterdir()):
        ok("Frontend already built")
        return

    npm = shutil.which("npm")
    if not npm:
        warn("npm not found — frontend will not be served. Install Node.js from https://nodejs.org")
        return

    info("Installing npm packages…")
    subprocess.run([npm, "install"], cwd=str(FRONTEND_DIR), check=True)
    info("Building React app…")
    subprocess.run([npm, "run", "build"], cwd=str(FRONTEND_DIR), check=True)
    ok("Frontend built")


# ── Step 5 — Model cache reset ────────────────────────────────────────────────

def reset_model_cache() -> None:
    if MODELS_DIR.exists():
        shutil.rmtree(MODELS_DIR)
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    ok("Model cache cleared — will re-download on next start")


# ── Step 6 — Start server ─────────────────────────────────────────────────────

def start_server() -> subprocess.Popen:  # type: ignore[type-arg]
    hdr("Starting PulseFeed")
    info(f"Server starting on http://localhost:{PORT}")

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app",
         "--host", "0.0.0.0", "--port", str(PORT), "--log-level", "warning"],
        cwd=str(BACKEND_DIR),
        env=env,
    )
    return proc


def wait_for_server(timeout: int = 30) -> bool:
    """Poll /health until the server responds or timeout."""
    import urllib.request
    import urllib.error

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(HEALTH_URL, timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="PulseFeed launcher")
    parser.add_argument("--reset", action="store_true", help="Clear model cache and re-download")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    print(_c("1;35", "\n  ██████╗ ██╗   ██╗██╗     ███████╗███████╗███████╗███████╗██████╗ "))
    print(_c("1;35",   "  ██╔══██╗██║   ██║██║     ██╔════╝██╔════╝██╔════╝██╔════╝██╔══██╗"))
    print(_c("1;35",   "  ██████╔╝██║   ██║██║     ███████╗█████╗  █████╗  █████╗  ██║  ██║"))
    print(_c("1;35",   "  ██╔═══╝ ██║   ██║██║     ╚════██║██╔══╝  ██╔══╝  ██╔══╝  ██║  ██║"))
    print(_c("1;35",   "  ██║     ╚██████╔╝███████╗███████║███████╗███████╗███████╗██████╔╝"))
    print(_c("1;35",   "  ╚═╝      ╚═════╝ ╚══════╝╚══════╝╚══════╝╚══════╝╚══════╝╚═════╝ "))
    print()

    if args.reset:
        reset_model_cache()

    check_python()
    hw = detect_hardware()
    install_deps(hw, force=args.reset)
    build_frontend()

    proc = start_server()

    ok("Waiting for server…")
    if not wait_for_server(timeout=30):
        err("Server did not start within 30 seconds. Check logs above.")
        proc.terminate()
        sys.exit(1)

    ok(f"PulseFeed is running at http://localhost:{PORT}")
    print()
    info("The AI model is downloading/loading in the background.")
    info("Your browser will open now — the app is ready to use.")
    info("Press Ctrl+C to stop PulseFeed.")
    print()

    if not args.no_browser:
        webbrowser.open(f"http://localhost:{PORT}")

    try:
        proc.wait()
    except KeyboardInterrupt:
        print()
        info("Shutting down PulseFeed…")
        proc.terminate()
        proc.wait()
        ok("Goodbye.")


if __name__ == "__main__":
    main()
