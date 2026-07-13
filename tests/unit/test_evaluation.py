"""
Unit Tests – Evaluation Framework

Tests the heuristic decision evaluator.
"""

import uuid

from app.evaluation.evaluator import evaluate_decision


class TestEvaluateDecision:
    """Tests for the loan decision evaluator."""

    def _app_id(self) -> str:
        return str(uuid.uuid4())

    def test_good_decision_scores_well(self):
        application_id = self._app_id()
        decision = {
            "recommendation": "APPROVE",
            "confidence_score": 0.85,
            "explanation": (
                "The applicant qualifies because their FICO score of 740 exceeds "
                "the minimum 620 threshold for conventional loans. Their DTI ratio "
                "of 15.2% is well within the 43% guideline, demonstrating strong "
                "debt management. Therefore, this application is approved."
            ),
        }
        agent_findings = {
            "credit_findings": {
                "credit_score": 740,
                "dti_ratio": 15.2,
                "risk_tier": "EXCELLENT",
            },
            "decision": decision,
        }
        result = evaluate_decision(application_id, decision, agent_findings)

        assert result.overall_score >= 0.5
        assert result.relevance_score >= 0.4
        assert result.coherence_score >= 0.4
        assert "LOW_RELEVANCE" not in result.flags

    def test_empty_explanation_flags(self):
        application_id = self._app_id()
        decision = {
            "recommendation": "APPROVE",
            "confidence_score": 0.8,
            "explanation": "",
        }
        result = evaluate_decision(application_id, decision, {"decision": decision})
        assert "EXPLANATION_TOO_BRIEF" in result.flags

    def test_result_has_correct_application_id(self):
        application_id = self._app_id()
        decision = {
            "recommendation": "MANUAL_REVIEW",
            "confidence_score": 0.5,
            "explanation": "Manual underwriter review required due to borderline DTI.",
        }
        result = evaluate_decision(application_id, decision, {"decision": decision})
        assert str(result.application_id) == application_id

    def test_scores_in_valid_range(self):
        application_id = self._app_id()
        decision = {
            "recommendation": "REJECT",
            "confidence_score": 0.9,
            "explanation": (
                "Rejected due to DTI ratio of 58% exceeding the 43% maximum. "
                "Credit score of 550 is below 580 minimum for FHA. Therefore declined."
            ),
        }
        result = evaluate_decision(application_id, decision, {"decision": decision})

        assert 0.0 <= result.faithfulness_score <= 1.0
        assert 0.0 <= result.relevance_score <= 1.0
        assert 0.0 <= result.coherence_score <= 1.0
        assert 0.0 <= result.overall_score <= 1.0

    def test_evaluated_at_is_set(self):
        application_id = self._app_id()
        decision = {
            "recommendation": "APPROVE",
            "confidence_score": 0.8,
            "explanation": "Good credit score and income.",
        }
        result = evaluate_decision(application_id, decision, {"decision": decision})
        assert result.evaluated_at is not None
