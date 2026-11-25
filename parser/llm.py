"""LLM clients with structured output. The provider is selected in .env (LLM_PROVIDER).

Both clients receive the same JSON Schema and return a raw JSON string;
validation and retry live in parser/extract.py and are shared by all providers.
"""

import json
import os
from typing import Any, Protocol

import httpx
from dotenv import load_dotenv

Message = dict[str, str]  # {"role": "user"|"assistant", "content": "..."}


class LLMClient(Protocol):
    name: str

    def complete(self, system: str, messages: list[Message], schema: dict[str, Any]) -> str:
        """Returns the model's reply (expected to be JSON matching the schema)."""
        ...


class LLMError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, url: str, model: str, num_ctx: int = 8192, timeout: float = 600) -> None:
        self.name = f"ollama:{model}"
        self.url = url.rstrip("/")
        self.model = model
        self.num_ctx = num_ctx
        self.model_revision = os.getenv("OLLAMA_MODEL_REVISION", "")
        self.http = httpx.Client(timeout=timeout)
        self.last_prompt_tokens = 0

    def complete(self, system: str, messages: list[Message], schema: dict[str, Any]) -> str:
        # Conservative preflight, before Ollama can silently truncate the request.
        chars = len(system) + len(json.dumps(messages, ensure_ascii=False)) + len(json.dumps(schema))
        if chars // 3 + 1024 > self.num_ctx:
            raise LLMError("Input may exceed context; shorten the source or increase OLLAMA_NUM_CTX")
        resp = self.http.post(f"{self.url}/api/chat", json={
            "model": self.model,
            "messages": [{"role": "system", "content": system}, *messages],
            "format": schema,  # structured output: Ollama constrains generation to the JSON Schema
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
        import anthropic  # imported only when Claude is selected

        self.name = f"claude:{model}"
        self.model = model
        self.client = anthropic.Anthropic()  # key from ANTHROPIC_API_KEY in .env

    def complete(self, system: str, messages: list[Message], schema: dict[str, Any]) -> str:
        # Structured outputs (output_config.format) + a server-side fallback in case the model refuses.
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
            num_ctx=int(os.getenv("OLLAMA_NUM_CTX", "8192")),
        )
    if provider == "claude":
        return ClaudeClient(model=os.getenv("CLAUDE_MODEL", "claude-opus-5-5"))
    raise ValueError(f"Невідомий LLM_PROVIDER={provider!r} (очікується ollama або claude)")
