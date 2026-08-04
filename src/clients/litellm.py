from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import os
import time
from typing import Any, cast

from dotenv import load_dotenv
from litellm import ModelResponse, completion

from src.clients.vlm import VlmRequest, VlmResponse
from src.config import VlmConfig
from src.traces import JsonValue


class LiteLlmClient:
    """Invoke multimodal chat models through LiteLLM's provider adapters."""

    def __init__(self, config: VlmConfig) -> None:
        self.config = config
        load_dotenv()
        self.api_key = os.environ.get(config.api_key_env)
        if not self.api_key:
            raise ValueError(
                f"Set {config.api_key_env} in the environment or .env"
            )

    def complete(self, request: VlmRequest) -> VlmResponse:
        content: list[dict[str, Any]] = [
            {"type": "text", "text": request.prompt}
        ]
        image_manifest: list[JsonValue] = []
        for image in request.images:
            encoded = base64.b64encode(image.data).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image.media_type};base64,{encoded}"
                    },
                }
            )
            image_manifest.append(
                {
                    "role": image.role,
                    "media_type": image.media_type,
                    "bytes": len(image.data),
                    "sha256": hashlib.sha256(image.data).hexdigest(),
                }
            )

        parameters: dict[str, Any] = deepcopy(self.config.parameters)
        _apply_reasoning_config(parameters, self.config)
        if request.response_schema is not None:
            if "response_format" in parameters:
                raise ValueError(
                    "VLM response format cannot come from both request and config"
                )
            parameters["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "vlm_response",
                    "strict": True,
                    "schema": request.response_schema,
                },
            }

        api_base = (
            os.environ.get(self.config.api_base_env)
            if self.config.api_base_env is not None
            else None
        ) or self.config.api_base
        print(f"[vlm] request started: model={self.config.model}")
        started = time.monotonic()
        try:
            response = cast(
                ModelResponse,
                completion(
                    model=self.config.model,
                    messages=[{"role": "user", "content": content}],
                    api_key=self.api_key,
                    api_base=api_base,
                    timeout=self.config.timeout_seconds,
                    **parameters,
                ),
            )
        except Exception:
            print(
                f"[vlm] request failed: model={self.config.model} "
                f"elapsed={time.monotonic() - started:.1f}s"
            )
            raise

        choice = response.choices[0]
        message = choice.message
        model = str(response.model or self.config.model)
        finish_reason = str(choice.finish_reason or "unspecified")
        if not isinstance(message.content, str) or not message.content.strip():
            print(
                f"[vlm] response invalid: model={model} "
                f"finish_reason={finish_reason} "
                f"elapsed={time.monotonic() - started:.1f}s"
            )
            if not isinstance(message.content, str):
                raise ValueError("VLM response content must be text")
            raise ValueError(
                "VLM response content is empty: "
                f"model={model}, finish_reason={finish_reason}"
            )
        if finish_reason == "length":
            print(
                f"[vlm] response incomplete: model={model} "
                f"chars={len(message.content)} "
                f"elapsed={time.monotonic() - started:.1f}s"
            )
            raise ValueError(
                "VLM response reached its output token limit: "
                f"model={model}, chars={len(message.content)}"
            )
        raw = cast(JsonValue, response.model_dump(mode="json"))
        print(
            f"[vlm] request finished: model={model} "
            f"finish_reason={finish_reason} chars={len(message.content)} "
            f"elapsed={time.monotonic() - started:.1f}s"
        )
        request_manifest: dict[str, JsonValue] = {
            "transport": "litellm.completion",
            "model": self.config.model,
            "api_base": api_base,
            "api_key_env": self.config.api_key_env,
            "timeout_seconds": self.config.timeout_seconds,
            "parameters": cast(JsonValue, parameters),
            "images": image_manifest,
        }
        return VlmResponse(
            text=message.content,
            model=model,
            raw=raw,
            request=request_manifest,
        )


def _apply_reasoning_config(
    parameters: dict[str, Any], config: VlmConfig
) -> None:
    reasoning = config.reasoning
    _reject_native_reasoning_parameters(parameters)
    if reasoning.mode == "default":
        return

    provider, _, model = config.model.partition("/")
    if not model:
        raise ValueError(
            "VLM model must include its LiteLLM provider prefix"
        )

    if provider == "dashscope":
        extra_body = parameters.setdefault("extra_body", {})
        if not isinstance(extra_body, dict):
            raise ValueError("VLM extra_body parameter must be an object")
        extra_body["enable_thinking"] = reasoning.mode == "enabled"
        if reasoning.effort is not None:
            if model == "qwen3.8-max" and reasoning.effort not in {
                "low",
                "medium",
                "xhigh",
            }:
                raise ValueError(
                    "qwen3.8-max reasoning effort must be low, medium, or xhigh"
                )
            extra_body["reasoning_effort"] = reasoning.effort
        return

    if provider in {"moonshot", "zai"}:
        if reasoning.effort is not None:
            raise ValueError(
                f"{provider} model {model} does not support graded reasoning effort"
            )
        parameters["thinking"] = {
            "type": "enabled" if reasoning.mode == "enabled" else "disabled"
        }
        return

    if provider == "gemini":
        if reasoning.mode == "disabled":
            raise ValueError(
                f"Gemini model {model} does not support disabled reasoning"
            )
        if reasoning.effort is not None:
            parameters["reasoning_effort"] = reasoning.effort
        return

    if provider in {"openai", "anthropic"}:
        parameters["reasoning_effort"] = (
            "none" if reasoning.mode == "disabled" else reasoning.effort
        )
        if parameters["reasoning_effort"] is None:
            parameters.pop("reasoning_effort")
        return

    raise ValueError(
        f"Reasoning configuration does not support LiteLLM provider {provider!r}"
    )


def _reject_native_reasoning_parameters(parameters: dict[str, Any]) -> None:
    conflicts = {"reasoning_effort", "thinking"}.intersection(parameters)
    extra_body = parameters.get("extra_body")
    if isinstance(extra_body, dict):
        conflicts.update(
            {"enable_thinking", "reasoning_effort", "thinking_budget"}.intersection(
                extra_body
            )
        )
    if conflicts:
        names = ", ".join(sorted(conflicts))
        raise ValueError(
            f"Put reasoning controls in the reasoning config, not parameters: {names}"
        )
