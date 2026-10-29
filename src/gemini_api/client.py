"""Gemini generateContent client for schema-constrained JSON; the API key never leaves headers."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx

from gemini_api.request_pacer import RequestPacer

GENERATE_CONTENT_URL = (  # hardcode-ok: endpoint público documentado da API do Gemini
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)
RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
BACKOFF_SECONDS = (5, 15, 45, 90)
REQUEST_TIMEOUT_SECONDS = 90


class GeminiApiError(RuntimeError):
    """Stable error code only; request headers and prompts are never put in the message."""


class DailyQuotaExhaustedError(GeminiApiError):
    """The free-tier daily quota is gone; resume after the Pacific-time midnight reset."""


@dataclass(frozen=True)
class GeneratedJson:
    text: str
    model: str
    usage: dict = field(default_factory=dict)
    from_cache: bool = False


class GeminiJsonClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        pacer: RequestPacer,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self._api_key = api_key
        self.model = model
        self._pacer = pacer
        self._http = http_client or httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS)
        self._sleep = sleep

    def generate_json(self, system_instruction: str, user_text: str, response_schema: dict):
        body = {
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseJsonSchema": response_schema,
            },
        }
        payload = self._post_with_retry(body)
        return GeneratedJson(_candidate_text(payload), self.model, payload.get("usageMetadata", {}))

    def _post_with_retry(self, body: dict) -> dict:
        for delay in (*BACKOFF_SECONDS, None):
            self._pacer.wait_turn()
            response = self._send(body)
            if response is not None and response.status_code == 200:
                return response.json()
            self._raise_if_final(response, delay)
            self._sleep(delay)
        raise GeminiApiError("GEMINI_RETRIES_EXHAUSTED")

    def _send(self, body: dict) -> httpx.Response | None:
        url = GENERATE_CONTENT_URL.format(model=self.model)
        try:
            return self._http.post(url, headers={"x-goog-api-key": self._api_key}, json=body)
        except httpx.TimeoutException:
            return None

    def _raise_if_final(self, response: httpx.Response | None, delay: float | None) -> None:
        if response is not None and response.status_code == 429 and _is_daily_quota(response):
            raise DailyQuotaExhaustedError("GEMINI_DAILY_QUOTA_EXHAUSTED")
        retryable = response is None or response.status_code in RETRYABLE_STATUS_CODES
        if not retryable:
            raise GeminiApiError(f"GEMINI_HTTP_{response.status_code}")
        if delay is None:
            raise GeminiApiError("GEMINI_RETRIES_EXHAUSTED")


def _is_daily_quota(response: httpx.Response) -> bool:
    return "PerDay" in response.text


def _candidate_text(payload: dict) -> str:
    try:
        candidate = payload["candidates"][0]
        if candidate.get("finishReason") not in (None, "STOP"):
            raise GeminiApiError(f"GEMINI_FINISH_{candidate['finishReason']}")
        return candidate["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as error:
        raise GeminiApiError("GEMINI_RESPONSE_MALFORMED") from error
