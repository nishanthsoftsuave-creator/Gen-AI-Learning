"""Thin Groq wrapper, reusing the same env vars / model default as
src/rag.py (GROQ_API_KEY, GROQ_MODEL) so the agent, the workflow, and the
existing PDF Q&A app all talk to the same model."""

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq, RateLimitError

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MAX_RATE_LIMIT_RETRIES = 8


def _retry_after_seconds(error, attempt):
    """Read the Retry-After header Groq sends on 429s; fall back to
    exponential backoff if it's missing."""
    try:
        header_value = error.response.headers.get("retry-after")
        if header_value is not None:
            return float(header_value) + 0.5
    except Exception:
        pass
    return min(2 ** attempt, 30)


def chat(messages, tools=None, tool_choice=None, temperature=0.3):
    """Single Groq chat-completion call. Returns (message, usage_dict).

    Retries on 429 (tokens-per-minute rate limit) with the server-suggested
    backoff -- the account's free-tier TPM cap is low enough that a single
    multi-iteration agent run can legitimately hit it, so this is normal
    operation, not an edge case."""

    kwargs = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
    }

    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice or "auto"

    attempt = 0
    while True:
        try:
            response = _client.chat.completions.create(**kwargs)
            break
        except RateLimitError as error:
            attempt += 1
            if attempt > MAX_RATE_LIMIT_RETRIES:
                raise
            wait_seconds = _retry_after_seconds(error, attempt)
            print(f"[llm_client] rate limited, retrying in {wait_seconds:.1f}s (attempt {attempt})")
            time.sleep(wait_seconds)

    usage = response.usage
    usage_dict = {
        "input_tokens": usage.prompt_tokens,
        "output_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }

    return response.choices[0].message, usage_dict
