"""Wraps a JSON generator with the disk cache; each run label keeps its own cached answers."""

import json

from gemini_api.client import GeneratedJson
from gemini_api.response_cache import DiskResponseCache, request_cache_key


class CachedJsonGenerator:
    def __init__(self, inner, cache: DiskResponseCache, prompt_version: str, run_label: str):
        self._inner = inner
        self._cache = cache
        self._prompt_version = prompt_version
        self._run_label = run_label
        self.cache_hits = 0
        self.model = inner.model

    def generate_json(self, system_instruction: str, user_text: str, response_schema: dict):
        key = request_cache_key(
            self.model,
            self._prompt_version,
            self._run_label,
            system_instruction,
            user_text,
            json.dumps(response_schema, sort_keys=True),
        )
        stored = self._cache.get(key)
        if stored is not None:
            self.cache_hits += 1
            return GeneratedJson(stored["text"], stored["model"], stored["usage"], from_cache=True)
        generated = self._inner.generate_json(system_instruction, user_text, response_schema)
        self._cache.put(
            key, {"text": generated.text, "model": generated.model, "usage": generated.usage}
        )
        return generated
