"""
LLM Engine — thin singleton wrapper around llama-cpp-python.

Thread-safe: a threading.Lock ensures only one inference runs at a time,
which is required because llama-cpp-python's Llama object is not re-entrant.

Usage
-----
    engine = LLMEngine.get()
    text = engine.chat([
        {"role": "system", "content": "You are helpful."},
        {"role": "user",   "content": "Summarise this..."},
    ], max_tokens=200)
"""
from __future__ import annotations

import logging
import re
import threading
from typing import Any

logger = logging.getLogger(__name__)

_NOT_READY_MSG = "LLM not loaded — call LLMEngine.get().load() first"


class LLMEngine:
    _instance: LLMEngine | None = None
    _model: Any = None          # llama_cpp.Llama, imported lazily
    _lock = threading.Lock()
    _ready = threading.Event()  # set() when model is loaded
    _error: str | None = None

    # ── Singleton ─────────────────────────────────────────────────────────────

    @classmethod
    def get(cls) -> LLMEngine:
        if cls._instance is None:
            cls._instance = LLMEngine()
        return cls._instance

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load(self, model_path: str, gpu_type: str, n_ctx: int = 2048) -> None:
        """
        Load the GGUF model into memory.  Call once from main.py lifespan
        in a background thread so the server starts instantly.

        gpu_type: 'metal' | 'cuda' | 'cpu'
        Pass empty model_path to run in disabled mode (PULSEFEED_NO_LLM).
        """
        if not model_path:
            logger.info("No model path — LLM disabled (PULSEFEED_NO_LLM)")
            self._ready.set()
            return

        try:
            from llama_cpp import Llama  # imported here so missing wheel gives clear error
        except ImportError as exc:
            self._error = f"llama-cpp-python not installed: {exc}"
            logger.error(self._error)
            return

        n_gpu_layers = -1 if gpu_type in ("metal", "cuda") else 0

        logger.info(
            "Loading model %s | gpu=%s n_gpu_layers=%d n_ctx=%d",
            model_path, gpu_type, n_gpu_layers, n_ctx,
        )
        try:
            self._model = Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_gpu_layers=n_gpu_layers,
                verbose=False,
            )
            self._ready.set()
            logger.info("Model loaded and ready")
        except Exception as exc:
            self._error = str(exc)
            logger.error("Model load failed: %s", exc)

    def is_ready(self) -> bool:
        return self._ready.is_set()

    def get_error(self) -> str | None:
        return self._error

    # ── Inference ─────────────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 256,
        temperature: float = 0.1,
        stop: list[str] | None = None,
    ) -> str:
        """
        Blocking chat completion.  Thread-safe via _lock.
        Returns empty string on any error — callers must handle gracefully.
        """
        if not self.is_ready():
            logger.warning("chat() called before model ready")
            return ""
        try:
            with self._lock:
                result = self._model.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stop=stop or [],
                )
            return result["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.error("Inference error: %s", exc)
            return ""

    # ── Convenience helpers ───────────────────────────────────────────────────

    def score_relevance(self, title: str, snippet: str, occupation: str, interests: list[str]) -> int:
        """Return integer 1-10 relevance score. Returns 5 on parse failure."""
        interests_str = ", ".join(interests[:5]) if interests else occupation
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a content relevance scorer. "
                    "Respond with only a single integer from 1 to 10. No other text."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User profile: {occupation} — interested in {interests_str}\n\n"
                    f"Article: {title}\n{snippet[:300]}\n\n"
                    "Relevance score (1-10):"
                ),
            },
        ]
        raw = self.chat(messages, max_tokens=4, temperature=0.0)
        match = re.search(r"\d+", raw)
        if match:
            return min(10, max(1, int(match.group())))
        return 5

    def summarize(self, title: str, snippet: str, occupation: str, interests: list[str]) -> str:
        """Return a 2-sentence personalized summary. Falls back to snippet on failure."""
        interests_str = ", ".join(interests[:3]) if interests else occupation
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a concise news summarizer. "
                    "Write exactly 2 sentences tailored to the user's background. "
                    "No bullet points. No headers."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User: {occupation}, interested in {interests_str}\n\n"
                    f"Article title: {title}\n"
                    f"Content: {snippet[:800]}\n\n"
                    "Write a 2-sentence personalized summary:"
                ),
            },
        ]
        result = self.chat(messages, max_tokens=120, temperature=0.3)
        return result if result else snippet[:300]

    def generate_brief(self, name: str, items: list[dict[str, str]]) -> str:
        """Return a 2-sentence daily brief for the user based on today's top articles."""
        titles = "\n".join(f"- {it['title']}" for it in items[:5])
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a friendly personal news assistant. "
                    "Write exactly 2 sentences as a daily brief. Be conversational."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Write a daily brief for {name} based on these top stories:\n{titles}"
                ),
            },
        ]
        return self.chat(messages, max_tokens=100, temperature=0.4)
