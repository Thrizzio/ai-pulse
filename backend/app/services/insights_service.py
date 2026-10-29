"""Generates actionable, privacy-safe department insights for organization administrators.

Adheres strictly to privacy rules:
- Operates ONLY on approved aggregate department metrics and risk categories that passed k-anonymity (k >= 5).
- Never reads, requests, transmits, or exposes raw free-text answers, employee names, emails, or IDs.
- Validates all output against a strict schema and priority whitelist.
- Provides a deterministic rule-based fallback when the LLM is unconfigured, times out, or fails validation.
"""
import json
import logging
import re
import httpx

from ..config import AI_MODE, LLM_API_KEY, LLM_API_URL, LLM_MODEL

logger = logging.getLogger(__name__)

ALLOWED_FLAGS = {
    "customer_data_shared",
    "confidential_data_shared",
    "unreviewed_output",
    "policy_unaware",
}

VALID_PRIORITIES = {"high", "medium", "low"}

SYSTEM_PROMPT = """You are an enterprise AI governance and risk advisor.
Analyze the provided department-level aggregate risk counts and maturity scores.
For each department with risks or low maturity, provide practical organizational recommendations.
Rules:
1. Do not invent or assume any individual employee data.
2. Only reference the departments and risks provided in the input.
3. Every insight must contain:
   - department: exact department name from input
   - observed_pattern: concise summary of the aggregate pattern (max 200 chars)
   - recommended_action: concrete, feasible organizational step (max 200 chars)
   - reason: why the action resolves the risk (max 200 chars)
   - priority: "high", "medium", or "low"
Return JSON ONLY: {"insights": [{"department": ..., "observed_pattern": ..., "recommended_action": ..., "reason": ..., "priority": ...}]}"""


def generate_rule_based_insights(visible_departments: list[dict]) -> list[dict]:
    """Generates deterministic, highly practical recommendations directly from aggregate patterns."""
    insights = []

    for d in visible_departments:
        if d.get("suppressed"):
            continue
        dept_name = d.get("department", "Unknown Department")
        risk_counts = d.get("risk_counts", {})
        avg_score = d.get("average_score")
        level = d.get("level", "Not assessed")

        has_dept_risk = False

        if risk_counts.get("customer_data_shared"):
            count = risk_counts["customer_data_shared"]
            has_dept_risk = True
            insights.append({
                "department": dept_name,
                "observed_pattern": f"Customer data shared with external AI tools without clear data boundaries ({count} occurrences).",
                "recommended_action": "Deploy enterprise-managed AI accounts with zero data retention and implement client data masking guidelines.",
                "reason": "Protects client confidentiality, prevents regulatory breaches (GDPR/SOC2), and reduces third-party data leakage risks.",
                "priority": "high",
            })

        if risk_counts.get("confidential_data_shared"):
            count = risk_counts["confidential_data_shared"]
            has_dept_risk = True
            insights.append({
                "department": dept_name,
                "observed_pattern": f"Internal confidential or proprietary records entered into AI models ({count} occurrences).",
                "recommended_action": "Enforce data classification guidelines and mandate approved local or private models for sensitive internal documentation.",
                "reason": "Ensures trade secrets, financial records, and proprietary intellectual property stay within organizational boundaries.",
                "priority": "high",
            })

        if risk_counts.get("unreviewed_output"):
            count = risk_counts["unreviewed_output"]
            has_dept_risk = True
            insights.append({
                "department": dept_name,
                "observed_pattern": f"AI-generated deliverables incorporated into workflow without structured human verification ({count} occurrences).",
                "recommended_action": "Implement a documented peer-review checklist and designate technical owners to verify AI-generated work products.",
                "reason": "Mitigates hallucinations, subtle logic bugs, and quality degradation in deliverables before release.",
                "priority": "medium",
            })

        if risk_counts.get("policy_unaware"):
            count = risk_counts["policy_unaware"]
            has_dept_risk = True
            insights.append({
                "department": dept_name,
                "observed_pattern": f"Ambiguity or lack of familiarity with organizational AI acceptable-use policies ({count} occurrences).",
                "recommended_action": "Distribute an official AI usage cheat-sheet and conduct a mandatory 30-minute policy walkthrough session.",
                "reason": "Establishes clear boundaries on permitted versus prohibited use cases and eliminates shadow AI adoption.",
                "priority": "medium",
            })

        # Maturity-level recommendation for departments with low adoption or basic scores
        if not has_dept_risk and avg_score is not None and avg_score < 3.0:
            insights.append({
                "department": dept_name,
                "observed_pattern": f"{dept_name} displays early-stage AI exploration with an average score of {avg_score} ({level}).",
                "recommended_action": "Establish guided departmental pilots on 2-3 standard tasks paired with experienced practitioners.",
                "reason": "Builds safe foundational proficiency and demonstrates immediate productivity value without security risks.",
                "priority": "low",
            })
        elif not has_dept_risk:
            score_text = f"an average score of {avg_score} ({level})" if avg_score is not None else "healthy diagnostic participation"
            insights.append({
                "department": dept_name,
                "observed_pattern": f"{dept_name} demonstrates solid AI maturity with {score_text} and zero identified risk flags.",
                "recommended_action": "Document current departmental workflows as organizational benchmarks and establish peer mentoring.",
                "reason": "Scales effective AI adoption patterns across other departments while sustaining high security and review standards.",
                "priority": "low",
            })

    return insights


def generate_insights(visible_departments: list[dict]) -> dict:
    """Generates actionable insights. Reverts safely to deterministic rules on LLM failure."""
    visible_departments = [d for d in visible_departments if not d.get("suppressed")]
    if not visible_departments:
        return {"insights": [], "source": "rules"}

    if AI_MODE != "live" or not LLM_API_KEY or not LLM_API_URL:
        source_label = "mock" if AI_MODE == "mock" else "rules"
        return {
            "insights": generate_rule_based_insights(visible_departments),
            "source": source_label,
        }

    # Format minimal, privacy-safe aggregate payload
    safe_payload = [
        {
            "department": d.get("department"),
            "headcount": d.get("employees"),
            "completed_respondents": d.get("responded"),
            "average_score": d.get("average_score"),
            "maturity_level": d.get("level"),
            "observed_risks": {
                k: v for k, v in d.get("risk_counts", {}).items() if k in ALLOWED_FLAGS
            },
        }
        for d in visible_departments
    ]

    valid_dept_names = {d.get("department") for d in visible_departments}

    try:
        r = httpx.post(
            LLM_API_URL,
            headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            json={
                "model": LLM_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(safe_payload)},
                ],
            },
            timeout=25.0,
        )
        r.raise_for_status()
        raw = r.json()["choices"][0]["message"]["content"].strip()

        # Clean code fences
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

        data = json.loads(raw)
        items = data.get("insights", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])

        validated = []
        for it in items:
            if not isinstance(it, dict):
                continue
            dept = it.get("department")
            if dept not in valid_dept_names:
                continue
            pattern = str(it.get("observed_pattern") or "").strip()[:500]
            action = str(it.get("recommended_action") or "").strip()[:500]
            reason = str(it.get("reason") or "").strip()[:500]
            priority = str(it.get("priority") or "").lower().strip()
            if priority not in VALID_PRIORITIES:
                continue

            if pattern and action and reason:
                validated.append({
                    "department": dept,
                    "observed_pattern": pattern,
                    "recommended_action": action,
                    "reason": reason,
                    "priority": priority,
                })

        if validated:
            return {"insights": validated, "source": "ai"}

        # If LLM returned empty or unparseable items, fallback to rules
        return {
            "insights": generate_rule_based_insights(visible_departments),
            "source": "rules",
        }

    except Exception as e:
        logger.warning("LLM insights generation failed or timed out: %s. Using deterministic rules.", e)
        return {
            "insights": generate_rule_based_insights(visible_departments),
            "source": "rules",
        }


def generate_other_teams_insights(target_dept: dict) -> dict:
    """Generates privacy-safe actionable recommendations for the 'Other teams' aggregate.

    Applies strict privacy safeguards:
    - Never receives individual department names, employee IDs, raw answers, or individual scores.
    - When completed respondents < 5: suppresses rare risk patterns (count < 2, or all risks if < 2 respondents).
    - When data is insufficient or risks are suppressed: provides a clear general organizational governance recommendation.
    """
    dept_name = "Other teams"
    responded = target_dept.get("responded") or 0
    headcount = target_dept.get("employees") or 0
    avg_score = target_dept.get("average_score")
    level = target_dept.get("level") or "Not assessed"

    # Get combined risk flags from internal field or risk_counts
    raw_risks = target_dept.get("_other_flag_counts") or target_dept.get("risk_counts") or {}

    # Privacy filtering: suppress rare risks if fewer than 5 respondents
    safe_risks = {}
    if responded >= 5:
        # At k >= 5, all aggregate risks are permitted
        safe_risks = {k: v for k, v in raw_risks.items() if k in ALLOWED_FLAGS and v > 0}
    elif responded >= 2:
        # When 2 <= responded < 5: suppress rare patterns (count < 2) to prevent individual re-identification
        safe_risks = {k: v for k, v in raw_risks.items() if k in ALLOWED_FLAGS and v >= 2}
    else:
        # When responded < 2: all specific risks are suppressed
        safe_risks = {}

    # If insufficient privacy-safe risk data exists
    if not safe_risks:
        return {
            "insights": [
                {
                    "department": dept_name,
                    "observed_pattern": "Diagnostic participation in combined small teams is sparse (< 5 respondents) with no shared aggregate risk patterns meeting privacy thresholds.",
                    "recommended_action": "Establish general organizational AI acceptable-use guidelines and provide standard baseline training across small teams.",
                    "reason": "Provides proactive governance and literacy across smaller operational units without risking individual identification.",
                    "priority": "low",
                }
            ],
            "source": "rules",
        }

    # If safe risks exist, generate insights (rules or AI)
    safe_dept_record = {
        "department": dept_name,
        "employees": headcount,
        "responded": responded,
        "average_score": avg_score,
        "level": level,
        "risk_counts": safe_risks,
    }

    if AI_MODE != "live" or not LLM_API_KEY or not LLM_API_URL:
        source_label = "mock" if AI_MODE == "mock" else "rules"
        return {
            "insights": generate_rule_based_insights([safe_dept_record]),
            "source": source_label,
        }

    return generate_insights([safe_dept_record])
