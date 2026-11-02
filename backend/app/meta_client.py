"""Shared client for Meta's Model API (OpenAI-compatible, https://dev.meta.ai/docs/overview)."""
import os
from functools import lru_cache

from openai import OpenAI

BASE_URL = "https://api.meta.ai/v1"


class MetaKeyMissing(RuntimeError):
    pass


@lru_cache
def get_client() -> OpenAI:
    key = os.getenv("META_API_KEY")
    if not key:
        raise MetaKeyMissing("META_API_KEY is not set - add it to backend/.env")
    return OpenAI(api_key=key, base_url=BASE_URL)
