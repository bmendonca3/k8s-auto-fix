from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

SYSTEM_PROMPT = "Output ONLY a valid RFC6902 JSON Patch array. No prose."
DEFAULT_ENDPOINT_PATH = "/v1/chat/completions"


@dataclass
class ClientOptions:
    endpoint: str
    model: str
    api_key_env: Optional[str]
    timeout_seconds: float
    retries: int
    organization: Optional[str] = None
    seed: Optional[int] = None


class ModelClient:
    """OpenAI-compatible chat completions client with retries and backoff."""

    def __init__(self, options: ClientOptions) -> None:
        self.endpoint = self._normalise_endpoint(options.endpoint)
        self.model = options.model
        self.api_key_env = options.api_key_env
        self.organization = options.organization
        self.timeout = options.timeout_seconds
        self.retries = max(0, int(options.retries))
        seed = options.seed
        self._rng = random.Random(seed) if seed is not None else random.Random()

    def request_patch(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        headers = self._build_headers()
        attempt = 0
        last_error: Optional[Exception] = None

        while attempt <= self.retries:
            try:
                with httpx.Client(timeout=self.timeout, headers=headers) as client:
                    response = client.post(self.endpoint, json=payload)
                    response.raise_for_status()
                data = response.json()
                return self._extract_content(data)
            except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                last_error = exc
                if attempt >= self.retries:
                    raise
                time.sleep(self._backoff_seconds(attempt))
                attempt += 1

        # Should not reach here but raises last error if it does
        if last_error:
            raise last_error
        raise RuntimeError("Model request failed without raising error")

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        api_key = None
        if self.api_key_env:
            api_key = os.getenv(self.api_key_env)
            if not api_key:
                raise RuntimeError(f"Environment variable {self.api_key_env} not set")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
        return headers

    def _backoff_seconds(self, attempt: int) -> float:
        base = 0.5 * (2 ** attempt)
        jitter = self._rng.uniform(0, base)
        return base + jitter

    @staticmethod
    def _extract_content(data: Dict[str, Any]) -> str:
        choices = data.get("choices")
        if not choices:
            raise RuntimeError("Model response missing 'choices'")
        first = choices[0]
        if not isinstance(first, dict):
            raise RuntimeError("Model response malformed: choice not an object")
        message = first.get("message")
        if not isinstance(message, dict) or "content" not in message:
            raise RuntimeError("Model response missing 'message.content'")
        content = message["content"]
        if not isinstance(content, str):
            raise RuntimeError("Model message content must be string")
        return content

    @staticmethod
    def _normalise_endpoint(url: str) -> str:
        if not url:
            raise ValueError("Model endpoint is required")
        url = url.rstrip("/")
        if url.endswith(DEFAULT_ENDPOINT_PATH):
            return url
        if url.startswith("http"):
            return f"{url}{DEFAULT_ENDPOINT_PATH}"
        raise ValueError("Model endpoint must start with http or https")

    @classmethod
    def from_env(
        cls,
        endpoint: Optional[str] = None,
        model: Optional[str] = None,
        api_key_env: Optional[str] = None,
        timeout_seconds: float = 30.0,
        retries: int = 0,
        organization: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> "ModelClient":
        options = ClientOptions(
            endpoint=endpoint or os.getenv("PROPOSER_MODEL_URL", "http://localhost:8000"),
            model=model or os.getenv("PROPOSER_MODEL_NAME", "proposer-model"),
            api_key_env=api_key_env or os.getenv("PROPOSER_API_KEY_ENV"),
            timeout_seconds=timeout_seconds,
            retries=retries,
            organization=organization or os.getenv("PROPOSER_ORGANIZATION"),
            seed=seed,
        )
        return cls(options)
