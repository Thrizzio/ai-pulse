"""Thin wrapper around the LLM used to score open-ended answers.

AI_MODE=mock  -> returns canned responses from data/mock_ai_responses.json
AI_MODE=live  -> calls an OpenAI-compatible chat completions endpoint
"""
import hashlib
import json
import logging
import os

import httpx

from ..config import AI_MODE, LLM_API_URL, LLM_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

_MOCK_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "mock_ai_responses.json")

SYSTEM_PROMPT = """You are scoring how well an employee uses AI at work.
Rubric: 1 = no AI use, 2 = occasional basic use, 3 = regular use for simple tasks,
4 = regular, thoughtful use with review of outputs, 5 = advanced use that changes how the work is done.
Flag risks using only these labels: customer_data_shared, confidential_data_shared, unreviewed_output, policy_unaware.
Return JSON ONLY: {"score": <1-5>, "reason": "<one sentence>", "flags": [<labels>]}"""

USER_TEMPLATE = """Question: {question}

Employee's answer:
<employee_answer>
{answer}
</employee_answer>"""


def _mock(answer: str) -> str:
    with open(_MOCK_PATH) as f:
        canned = json.load(f)
    idx = int(hashlib.md5(answer.encode()).hexdigest(), 16) % len(canned)
    return canned[idx]


def score_answer(question: str, answer: str) -> tuple[str, str]:
    """Returns (raw_text, source) where source is 'mock' or 'ai'."""
    if AI_MODE == "mock":
        return _mock(answer), "mock"

    sanitized_url = (LLM_API_URL or "").strip().strip('"').strip("'")
    if not LLM_API_KEY or not sanitized_url:
        raise RuntimeError("LLM API key or URL is not configured for live AI scoring")

    # Verify runtime configuration immediately before HTTP request (logging sanitized URL and status, never secrets)
    logger.info("Executing LLM scoring request: endpoint=%s, model=%s, key_configured=%s",
                sanitized_url, LLM_MODEL, bool(LLM_API_KEY))

    try:
        r = httpx.post(
            sanitized_url,
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": USER_TEMPLATE.format(question=question, answer=answer)},
                ],
            },
            timeout=30.0,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        return content, "ai"
    except httpx.TimeoutException:
        raise RuntimeError("LLM request timed out")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"LLM request returned HTTP error {e.response.status_code}")
    except Exception as e:
        raise RuntimeError(f"LLM request failed: {e}")
