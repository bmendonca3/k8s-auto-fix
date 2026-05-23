from __future__ import annotations

from typing import Any

import httpx
import pytest

from src.proposer.model_client import ClientOptions, ModelClient


class FakeResponse:
    def __init__(self, payload: dict[str, Any], error: Exception | None = None) -> None:
        self._payload = payload
        self._error = error

    def raise_for_status(self) -> None:
        if self._error:
            raise self._error

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeHttpClient:
    calls: list[dict[str, Any]] = []
    responses: list[FakeResponse] = []

    def __init__(self, *, timeout: float, headers: dict[str, str]) -> None:
        self.timeout = timeout
        self.headers = headers

    def __enter__(self) -> "FakeHttpClient":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None

    def post(self, endpoint: str, json: dict[str, Any]) -> FakeResponse:
        self.calls.append({"endpoint": endpoint, "json": json, "headers": self.headers, "timeout": self.timeout})
        return self.responses.pop(0)


def _client(*, retries: int = 0) -> ModelClient:
    return ModelClient(
        ClientOptions(
            endpoint="https://api.x.ai",
            model="grok-4.3",
            api_key_env="XAI_API_KEY_TEST",
            timeout_seconds=12,
            retries=retries,
            organization="org-test",
            seed=1,
        )
    )


def _success_response(content: str = "[]") -> FakeResponse:
    return FakeResponse(
        {
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
        }
    )


def test_headers_payload_and_openai_compatible_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY_TEST", "test-key")
    monkeypatch.setattr(httpx, "Client", FakeHttpClient)
    FakeHttpClient.calls = []
    FakeHttpClient.responses = [_success_response('[{"op":"add","path":"/metadata/labels/a","value":"b"}]')]

    result = _client().request_patch("make a patch")

    assert result["content"].startswith("[")
    assert result["usage"]["total_tokens"] == 14
    call = FakeHttpClient.calls[0]
    assert call["endpoint"] == "https://api.x.ai/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer test-key"
    assert call["headers"]["OpenAI-Organization"] == "org-test"
    assert call["json"]["model"] == "grok-4.3"
    assert call["json"]["messages"][0]["role"] == "system"


def test_retries_after_http_status_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY_TEST", "test-key")
    monkeypatch.setattr(httpx, "Client", FakeHttpClient)
    monkeypatch.setattr("src.proposer.model_client.time.sleep", lambda _seconds: None)
    request = httpx.Request("POST", "https://api.x.ai/v1/chat/completions")
    response = httpx.Response(429, request=request)
    error = httpx.HTTPStatusError("rate limited", request=request, response=response)
    FakeHttpClient.calls = []
    FakeHttpClient.responses = [FakeResponse({}, error), _success_response()]

    result = _client(retries=1).request_patch("make a patch")

    assert result["content"] == "[]"
    assert len(FakeHttpClient.calls) == 2


def test_malformed_response_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XAI_API_KEY_TEST", "test-key")
    monkeypatch.setattr(httpx, "Client", FakeHttpClient)
    FakeHttpClient.calls = []
    FakeHttpClient.responses = [FakeResponse({"choices": []})]

    with pytest.raises(RuntimeError, match="missing 'choices'"):
        _client().request_patch("make a patch")


def test_missing_api_key_fails_before_http_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XAI_API_KEY_TEST", raising=False)
    monkeypatch.setattr(httpx, "Client", FakeHttpClient)
    FakeHttpClient.calls = []

    with pytest.raises(RuntimeError, match="XAI_API_KEY_TEST"):
        _client().request_patch("make a patch")

    assert FakeHttpClient.calls == []
