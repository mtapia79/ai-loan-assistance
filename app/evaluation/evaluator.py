"""
Evaluation – LLM Response Quality Evaluator

Provides heuristic and LLM-based evaluation of loan decisions.
Metrics assessed:
  • Faithfulness  – does the explanation align with the provided evidence?
  • Relevance     – does the explanation address the loan application?
  • Coherence     – is the explanation logically consistent?
  • Overall       – weighted composite score

In a production environment this would use RAGAS or a dedicated eval LLM.
For demo purposes a fast heuristic evaluator is used (no extra API cost).
"""

import re
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass

from app.observability.logging import get_logger
from app.schemas.loan import EvaluationResult

logger = get_logger(__name__)


# ── Heuristic Evaluators ──────────────────────────────────────────────────────

_FINANCIAL_TERMS = frozenset([
    "dti", "debt-to-income", "credit score", "fico", "income", "debt",
    "payment history", "ltv", "loan-to-value", "down payment", "monthly",
    "annual", "collateral", "policy", "guideline", "approval", "rejection",
])

_COHERENCE_PATTERNS = [
    re.compile(r"\bbecause\b", re.I),
    re.compile(r"\bdue to\b", re.I),
    re.compile(r"\btherefore\b", re.I),
    re.compile(r"\bas a result\b", re.I),
    re.compile(r"\bconsequently\b", re.I),
    re.compile(r"\bsince\b", re.I),
    re.compile(r"\bgiven that\b", re.I),
]

_NUMERIC_PATTERN = re.compile(r"\d+\.?\d*%?")


def _score_faithfulness(explanation: str, agent_findings: dict) -> float:
    """
    Score how faithfully the explanation reflects the agent findings.

    Checks that key numeric values mentioned in findings appear in explanation.
    """
    score = 0.5  # base score

    # Check DTI is mentioned if present
    credit = agent_findings.get("credit_findings", {})
    dti = credit.get("dti_ratio")
    if dti is not None:
        dti_str = str(round(dti, 1))
        if dti_str in explanation or f"{int(dti)}%" in explanation:
            score += 0.2
        else:
            score -= 0.1

    # Check credit score is mentioned if present
    cs = credit.get("credit_score")
    if cs is not None and str(cs) in explanation:
        score += 0.15

    # Check recommendation aligns with tone
    decision = agent_findings.get("decision", {})
    recommendation = decision.get("recommendation", "")
    if recommendation == "APPROVE" and any(
        w in explanation.lower() for w in ["approve", "qualif", "eligible", "meets"]
    ):
        score += 0.15
    elif recommendation == "REJECT" and any(
        w in explanation.lower() for w in ["reject", "declin", "exceed", "fail", "below"]
    ):
        score += 0.15
    elif recommendation == "MANUAL_REVIEW" and any(
        w in explanation.lower() for w in ["manual", "review", "underwriter", "borderline"]
    ):
        score += 0.15

    return min(1.0, max(0.0, score))


def _score_relevance(explanation: str) -> float:
    """Score how relevant the explanation is to loan underwriting."""
    explanation_lower = explanation.lower()
    matched = sum(1 for term in _FINANCIAL_TERMS if term in explanation_lower)
    ratio = matched / len(_FINANCIAL_TERMS)
    # Scale: ≥5 matched terms → 1.0
    return min(1.0, ratio * (len(_FINANCIAL_TERMS) / 5))


def _score_coherence(explanation: str) -> float:
    """Score logical coherence using causal language patterns and structure."""
    # Check for causal language
    causal_matches = sum(1 for p in _COHERENCE_PATTERNS if p.search(explanation))
    causal_score = min(1.0, causal_matches / 2)

    # Check for numeric evidence
    numbers = _NUMERIC_PATTERN.findall(explanation)
    numeric_score = min(1.0, len(numbers) / 3)

    # Minimum length check
    length_score = min(1.0, len(explanation) / 200)

    return (causal_score * 0.4 + numeric_score * 0.3 + length_score * 0.3)


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate_decision(
    application_id: str,
    decision: dict,
    agent_findings: dict,
) -> EvaluationResult:
    """
    Evaluate the quality of a loan decision.

    Args:
        application_id: UUID string of the loan application.
        decision: The decision dict from the decision agent.
        agent_findings: Full result from process_loan_application.

    Returns:
        EvaluationResult with scores and any quality flags.
    """
    explanation = decision.get("explanation", "")
    flags: list[str] = []

    # Run scorers
    faithfulness = _score_faithfulness(explanation, agent_findings)
    relevance = _score_relevance(explanation)
    coherence = _score_coherence(explanation)

    # Weighted overall
    overall = (faithfulness * 0.4) + (relevance * 0.35) + (coherence * 0.25)

    # Flag low scores
    if faithfulness < 0.5:
        flags.append("LOW_FAITHFULNESS")
    if relevance < 0.4:
        flags.append("LOW_RELEVANCE")
    if coherence < 0.4:
        flags.append("LOW_COHERENCE")
    if overall < 0.5:
        flags.append("OVERALL_QUALITY_BELOW_THRESHOLD")
    if not explanation or len(explanation) < 50:
        flags.append("EXPLANATION_TOO_BRIEF")

    result = EvaluationResult(
        application_id=uuid.UUID(application_id),
        faithfulness_score=round(faithfulness, 3),
        relevance_score=round(relevance, 3),
        coherence_score=round(coherence, 3),
        overall_score=round(overall, 3),
        flags=flags,
        evaluated_at=datetime.now(tz=timezone.utc),
    )

    logger.info(
        "evaluation_complete",
        application_id=application_id,
        overall=result.overall_score,
        flags=flags,
    )
    return result
