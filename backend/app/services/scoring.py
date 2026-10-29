import json
import re

from . import llm

ALLOWED_FLAGS = {
    "customer_data_shared",
    "confidential_data_shared",
    "unreviewed_output",
    "policy_unaware",
}


def score_open_answer(question_text: str, answer: str) -> dict:
    raw, source = llm.score_answer(question_text, answer)

    # Strip markdown code fences if present
    clean = raw.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean)

    try:
        data = json.loads(clean)
    except Exception:
        data = {}

    # Coerce and clamp score between 1 and 5
    raw_score = data.get("score")
    try:
        score = float(raw_score)
        score = max(1.0, min(5.0, score))
    except (TypeError, ValueError):
        score = 1.0

    # Whitelist flags
    raw_flags = data.get("flags") or []
    flags = [f for f in raw_flags if f in ALLOWED_FLAGS]

    reason = str(data.get("reason") or "Evaluated response")

    return {
        "score": score,
        "reason": reason,
        "flags": flags,
        "source": source,
    }
