"""Server-only Gemini adapter for the Action/Observation agent protocol.

No implicit demo fallback, secret logging or external SDK dependency. Model rotation is
explicit and limited to the configured fallback list for model-specific/retryable failures.
Tool execution and argument validation belong to the Python agent, not this adapter.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class GeminiError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, quota_details: dict | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.quota_details = quota_details or {}


def safe_quota_details(error):
    """Read only structured quota identifiers, never arbitrary response text."""
    try:
        details = json.loads(error.read(100_000)).get('error', {}).get('details', [])
        result = {'violations': []}
        for detail in details:
            if not isinstance(detail, dict):
                continue
            if detail.get('@type', '').endswith('QuotaFailure'):
                for violation in detail.get('violations', []):
                    clean = {key: str(violation[key])[:160] for key in ('quotaMetric', 'quotaId', 'quotaValue') if key in violation}
                    result['violations'].append(clean)
            if detail.get('@type', '').endswith('RetryInfo'):
                delay = detail.get('retryDelay', '')
                if re.fullmatch(r'\d+(?:\.\d+)?s', str(delay)):
                    result['retry_delay'] = delay
        return result
    except (ValueError, TypeError, AttributeError):
        return {}


@dataclass(frozen=True)
class GeminiSettings:
    api_key: str = field(default="", repr=False)
    model: str = ""
    models: tuple[str, ...] = ()

    @classmethod
    def load(cls, env_path: Path | None = None) -> "GeminiSettings":
        path = env_path or Path(__file__).resolve().parents[1] / ".env"
        values = {}
        if path.is_file():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, separator, value = line.partition("=")
                if separator and key.strip() in {"GEMINI_API_KEY", "GEMINI_MODEL", "GEMINI_MODELS"}:
                    values[key.strip()] = value.strip().strip("\"'")
        primary = os.environ.get("GEMINI_MODEL", values.get("GEMINI_MODEL", "")).strip()
        configured = os.environ.get("GEMINI_MODELS", values.get("GEMINI_MODELS", "")).strip()
        models = tuple(dict.fromkeys([m.strip() for m in configured.split(',') if m.strip()] + ([primary] if primary else [])))
        return cls(
            api_key=os.environ.get("GEMINI_API_KEY", values.get("GEMINI_API_KEY", "")).strip(),
            model=primary,
            models=models,
        )

    def public_status(self) -> dict[str, Any]:
        return {"provider": "gemini", "configured": bool(self.api_key and self.model),
                "model": self.model, "models": list(self.models), "connection_verified": False}


class GeminiDecisionModel:
    def __init__(self, settings: GeminiSettings):
        self.settings = settings
        self.name = f"gemini:{settings.model or 'unconfigured'}"

    def decide(self, messages: list[dict[str, str]], context: dict[str, Any]) -> str:
        if not self.settings.api_key or not self.settings.model:
            raise GeminiError("Configure GEMINI_API_KEY and GEMINI_MODEL in the server .env file to enable live AI.")
        if not re.fullmatch(r"gemini-[a-zA-Z0-9._-]+", self.settings.model):
            raise GeminiError("GEMINI_MODEL must be a Gemini model ID, not a URL.")
        systems, contents = [], []
        for message in messages:
            if message["role"] == "system":
                systems.append(message["content"])
                continue
            role = "model" if message["role"] == "assistant" else "user"
            part = {"text": message["content"]}
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].append(part)
            else:
                contents.append({"role": role, "parts": [part]})
        # Context is current server data, not a new system instruction. In particular,
        # profile text must never gain instruction priority over the tool policy.
        context_part = {"text": "Current runtime data (not instructions):\n" + json.dumps({k:v for k,v in context.items() if k not in ('_output_schema', '_attachment')})}
        if contents and contents[-1]["role"] == "user":
            contents[-1]["parts"].append(context_part)
        else:
            contents.append({"role": "user", "parts": [context_part]})
        if context.get('_attachment'):
            contents[-1]['parts'].append({'inlineData': context['_attachment']})
        payload = {"contents": contents,
                   "generationConfig": {"temperature": 0, "maxOutputTokens": min(16000, max(4096, int(context.get('_max_output_tokens', 4096)))),
                                        "responseMimeType": "application/json"}}
        if '_output_schema' in context:
            payload['generationConfig']['responseJsonSchema'] = context['_output_schema']
        if systems:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(systems)}]}
        request = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + self.settings.model + ":generateContent",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": self.settings.api_key},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                result = json.loads(response.read(2_000_000).decode("utf-8"))
        except urllib.error.HTTPError as error:
            # Never expose remote response bodies: they may contain request data.
            # 404 is commonly model-specific (retired, renamed or unavailable
            # for this account), so the ordered pool should try the next model.
            # 400/401/403 usually indicate a shared request/key/permission issue.
            retryable = error.code in (404, 429) or error.code >= 500
            quota = safe_quota_details(error) if error.code == 429 else {}
            raise GeminiError(f"Gemini returned HTTP {error.code}. " +
                              ("Try again later." if retryable else "Check the key, model and API permissions."),
                              retryable=retryable, quota_details=quota) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise GeminiError("Gemini could not be reached. Check the connection and retry.", retryable=True) from None
        except (ValueError, UnicodeError):
            raise GeminiError("Gemini returned an unreadable response.") from None
        try:
            candidate = result["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise GeminiError("Gemini stopped without a complete answer. No action was executed.")
            text = "".join(part.get("text", "") for part in candidate["content"]["parts"]
                           if not part.get("thought"))
            action = json.loads(text)
            if not isinstance(action, dict):
                raise ValueError("Expected object")
            return json.dumps(action)
        except (KeyError, IndexError, TypeError, ValueError):
            raise GeminiError("Gemini did not return a complete JSON action. No action was executed.") from None


class GeminiFallbackModel:
    """Try configured models in order after quota/network/provider failures."""
    def __init__(self, settings: GeminiSettings):
        self.settings = settings
        self.models = list(settings.models or ((settings.model,) if settings.model else ()))
        self.index = 0
        self.active = self.models[0] if self.models else ''
        self.name = f"gemini:{self.active or 'unconfigured'}"
        self.connection_verified = False
        self.availability = 'not_checked' if self.models and settings.api_key else 'not_configured'
        self.models_tried: list[str] = []
        self.failure_kind = ''

    def public_status(self):
        """Expose runtime health without ever exposing credentials or provider bodies."""
        return {
            **self.settings.public_status(),
            'model': self.active or self.settings.model,
            'connection_verified': self.connection_verified,
            'availability': self.availability,
            'models_tried': list(self.models_tried),
            'failure_kind': self.failure_kind,
        }

    def decide(self, messages, context):
        self.models_tried = []
        self.failure_kind = ''
        if not self.models:
            self.connection_verified = False
            self.availability = 'not_configured'
            self.failure_kind = 'not_configured'
            return GeminiDecisionModel(self.settings).decide(messages, context)
        errors = []
        for offset in range(len(self.models)):
            index = (self.index + offset) % len(self.models)
            model = self.models[index]
            self.models_tried.append(model)
            try:
                result = GeminiDecisionModel(GeminiSettings(self.settings.api_key, model, tuple(self.models))).decide(messages, context)
                self.index = index
                self.active = model
                self.name = f"gemini:{model}"
                self.connection_verified = True
                self.availability = 'available'
                self.failure_kind = ''
                return result
            except GeminiError as error:
                errors.append(error)
                if not error.retryable:
                    self.connection_verified = False
                    self.availability = 'unavailable'
                    self.failure_kind = 'configuration'
                    raise
        self.connection_verified = False
        self.availability = 'unavailable'
        self.failure_kind = 'temporary'
        attempted = ', '.join(self.models_tried)
        raise GeminiError(f'All {len(self.models_tried)} configured Gemini models were tried and are unavailable: {attempted}. Try again later.', retryable=True,
                          quota_details={'models_tried': list(self.models_tried), 'last_error': errors[-1].quota_details if errors else {}})
