"""Контракт HTTP з локальною Ollama, без завантаження моделі."""
import httpx
import pytest

from parser.llm import LLMError, OllamaClient


def test_ollama_sends_schema_and_reads_content() -> None:
    schema = {'type': 'object'}
    def respond(request: httpx.Request) -> httpx.Response:
        import json
        body = json.loads(request.content)
        assert str(request.url) == 'http://127.0.0.1:11434/api/chat'
        assert body['format'] == schema
        assert body['messages'][0] == {'role': 'system', 'content': 'extract'}
        assert body['stream'] is False
        return httpx.Response(200, json={'message': {'content': '{}'}, 'prompt_eval_count': 123})
    client = OllamaClient('http://127.0.0.1:11434/', 'qwen2.5:1.5b')
    client.http.close()
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client.http = http
        assert client.complete('extract', [{'role': 'user', 'content': 'job'}], schema) == '{}'
        assert client.last_prompt_tokens == 123


@pytest.mark.parametrize('status,tokens,error', [(503, 0, 'HTTP 503'), (200, 4096, 'num_ctx')])
def test_ollama_rejects_server_error_and_full_context(status, tokens, error) -> None:
    client = OllamaClient('http://localhost:11434', 'qwen2.5:1.5b')
    client.http.close()
    def respond(request):
        return httpx.Response(status, json={'message': {'content': '{}'}, 'prompt_eval_count': tokens})
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        client.http = http
        with pytest.raises(LLMError, match=error):
            client.complete('extract', [], {})
