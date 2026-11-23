"""Configurable LLM adapter (httpx-based, provider-agnostic)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


@dataclass
class LLMConfig:
    provider: str = "openai"  # openai | anthropic | openai_compatible
    model: str = "gpt-4o-mini"
    api_key: str | None = None
    base_url: str | None = None
    temperature: float = 0.2
    max_tokens: int = 2000
    timeout: int = 120
    seed: int | None = None
    retries: int = 2

    @classmethod
    def from_env(cls) -> "LLMConfig":
        load_dotenv()
        seed_raw = os.getenv("LLM_SEED", "").strip()
        return cls(
            provider=os.getenv("LLM_PROVIDER", "openai"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            api_key=os.getenv("LLM_API_KEY") or None,
            base_url=os.getenv("LLM_BASE_URL") or None,
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2000")),
            timeout=int(os.getenv("LLM_TIMEOUT", "120")),
            seed=int(seed_raw) if seed_raw else None,
            retries=int(os.getenv("LLM_RETRIES", "2")),
        )

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "LLMConfig":
        cfg = cls()
        for k, v in d.items():
            if hasattr(cfg, k) and v is not None:
                setattr(cfg, k, v)
        # allow api_key from env if missing
        if not cfg.api_key:
            cfg.api_key = os.getenv("LLM_API_KEY")
        if cfg.seed == "":
            cfg.seed = None
        return cfg


@dataclass
class LLMResponse:
    text: str
    raw: dict[str, Any]
    prompt_tokens: int | None
    completion_tokens: int | None
    elapsed_seconds: float
    error: str | None = None


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config

    def complete(self, prompt: str, system: str | None = None) -> LLMResponse:
        last_err = None
        for attempt in range(self.config.retries + 1):
            try:
                return self._call(prompt, system)
            except Exception as e:
                last_err = str(e)
                time.sleep(min(2 ** attempt, 8))
        return LLMResponse(text="", raw={}, prompt_tokens=None, completion_tokens=None, elapsed_seconds=0.0, error=last_err)

    def _call(self, prompt: str, system: str | None) -> LLMResponse:
        c = self.config
        start = time.time()
        if c.provider in ("openai", "openai_compatible"):
            base = c.base_url or "https://api.openai.com/v1"
            url = base.rstrip("/") + "/chat/completions"
            headers = {"Authorization": f"Bearer {c.api_key}", "Content-Type": "application/json"}
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            body: dict[str, Any] = {
                "model": c.model,
                "messages": messages,
                "temperature": c.temperature,
                "max_tokens": c.max_tokens,
            }
            if c.seed is not None:
                body["seed"] = c.seed
            with httpx.Client(timeout=c.timeout) as client:
                r = client.post(url, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            return LLMResponse(
                text=text,
                raw=data,
                prompt_tokens=usage.get("prompt_tokens"),
                completion_tokens=usage.get("completion_tokens"),
                elapsed_seconds=time.time() - start,
            )
        if c.provider == "anthropic":
            base = c.base_url or "https://api.anthropic.com"
            url = base.rstrip("/") + "/v1/messages"
            headers = {
                "x-api-key": c.api_key or "",
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
            body = {
                "model": c.model,
                "max_tokens": c.max_tokens,
                "temperature": c.temperature,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                body["system"] = system
            with httpx.Client(timeout=c.timeout) as client:
                r = client.post(url, headers=headers, json=body)
                r.raise_for_status()
                data = r.json()
            text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            usage = data.get("usage", {})
            return LLMResponse(
                text=text,
                raw=data,
                prompt_tokens=usage.get("input_tokens"),
                completion_tokens=usage.get("output_tokens"),
                elapsed_seconds=time.time() - start,
            )
        raise ValueError(f"Unknown provider: {c.provider}")

    def config_dict(self) -> dict[str, Any]:
        d = asdict(self.config)
        d.pop("api_key", None)
        return d