"""Клієнти LLM зі structured output. Провайдер обирається через .env (LLM_PROVIDER).

Обидва клієнти отримують ту саму JSON Schema і повертають сирий JSON-рядок;
валідація й retry — у parser/extract.py, спільні для всіх провайдерів.
"""

import os
from typing import Any, Protocol

import httpx
from dotenv import load_dotenv

Message = dict[str, str]  # {"role": "user"|"assistant", "content": "..."}


class LLMClient(Protocol):
    name: str

    def complete(self, system: str, messages: list[Message], schema: dict[str, Any]) -> str:
        """Повертає відповідь моделі (очікується JSON за схемою)."""
        ...


class LLMError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, url: str, model: str, num_ctx: int = 4096, timeout: float = 600) -> None:
        self.name = f"ollama:{model}"
        self.url = url.rstrip("/")
        self.model = model
        self.num_ctx = num_ctx
        self.http = httpx.Client(timeout=timeout)
        self.last_prompt_tokens = 0

    def complete(self, system: str, messages: list[Message], schema: dict[str, Any]) -> str:
        resp = self.http.post(f"{self.url}/api/chat", json={
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "format": schema,  # structured output: Ollama обмежує генерацію JSON Schema
            "stream": False,
            "keep_alive": "10m",
            "options": {"temperature": 0, "num_ctx": self.num_ctx},
        })
        if resp.status_code != 200:
            raise LLMError(f"Ollama HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        self.last_prompt_tokens = data.get("prompt_eval_count", 0)
        if self.last_prompt_tokens >= self.num_ctx:
            raise LLMError(f"prompt ({self.last_prompt_tokens} tok) не вміщається в num_ctx={self.num_ctx}")
        return data["message"]["content"]


class ClaudeClient:
    def __init__(self, model: str) -> None:
        import anthropic  # імпорт лише коли обрано Claude

        self.name = f"claude:{model}"
        self.model = model
        self.client = anthropic.Anthropic()  # ключ з ANTHROPIC_API_KEY у .env

    def complete(self, system: str, messages: list[Message], schema: dict[str, Any]) -> str:
        # Structured outputs (output_config.format) + серверний fallback на випадок відмови моделі.
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=messages,  # type: ignore[arg-type]
            output_config={"format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise LLMError("Claude відмовився обробити запит")
        if response.stop_reason == "max_tokens":
            raise LLMError("відповідь обрізана (max_tokens)")
        return next(b.text for b in response.content if b.type == "text")


def make_client() -> LLMClient:
    load_dotenv()
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider == "ollama":
        return OllamaClient(
            url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "4096")),
        )
    if provider == "claude":
        return ClaudeClient(model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5"))
    raise ValueError(f"Невідомий LLM_PROVIDER={provider!r} (очікується ollama або claude)")
