"""
Unit Tests – Guardrails Validators

Tests input validation, output validation, and document PII redaction.
No database or LLM required.
"""

from app.guardrails.validators import (
    GuardrailSeverity,
    sanitise_document_text,
    validate_decision_output,
    validate_loan_input,
)


class TestValidateLoanInput:
    """Tests for input guardrail validator."""

    def test_valid_input_passes(self):
        result = validate_loan_input(
            applicant_name="Jane Doe",
            annual_income=95000.0,
            monthly_debt=1200.0,
            requested_amount=350000.0,
            loan_purpose="home_purchase",
        )
        assert result.passed is True
        assert result.violations == []

    def test_empty_name_fails(self):
        result = validate_loan_input(
            applicant_name="J",
            annual_income=95000.0,
            monthly_debt=1200.0,
            requested_amount=350000.0,
            loan_purpose="home_purchase",
        )
        assert result.passed is False
        codes = [v.code for v in result.violations]
        assert "NAME_TOO_SHORT" in codes

    def test_ssn_in_name_field_is_critical(self):
        result = validate_loan_input(
            applicant_name="Jane 123-45-6789 Doe",
            annual_income=95000.0,
            monthly_debt=1200.0,
            requested_amount=350000.0,
            loan_purpose="home_purchase",
        )
        assert result.passed is False
        critical = [v for v in result.violations if v.severity == GuardrailSeverity.CRITICAL]
        assert len(critical) > 0
        assert critical[0].code == "PII_SSN_IN_NAME"

    def test_zero_income_fails(self):
        result = validate_loan_input(
            applicant_name="Jane Doe",
            annual_income=0.0,
            monthly_debt=0.0,
            requested_amount=100000.0,
            loan_purpose="home_purchase",
        )
        assert result.passed is False
        codes = [v.code for v in result.violations]
        assert "INCOME_NON_POSITIVE" in codes

    def test_negative_debt_fails(self):
        result = validate_loan_input(
            applicant_name="Jane Doe",
            annual_income=95000.0,
            monthly_debt=-500.0,
            requested_amount=100000.0,
            loan_purpose="home_purchase",
        )
        assert result.passed is False
        codes = [v.code for v in result.violations]
        assert "DEBT_NEGATIVE" in codes

    def test_extreme_debt_ratio_warns(self):
        result = validate_loan_input(
            applicant_name="Jane Doe",
            annual_income=12000.0,  # $1,000/month
            monthly_debt=5000.0,  # 5x monthly income
            requested_amount=100000.0,
            loan_purpose="home_purchase",
        )
        warning = [v for v in result.violations if v.code == "DEBT_EXCEEDS_INCOME_2X"]
        assert len(warning) > 0
        assert warning[0].severity == GuardrailSeverity.WARNING
        # Warning does not block submission
        assert result.passed is True

    def test_invalid_loan_purpose_warns(self):
        result = validate_loan_input(
            applicant_name="Jane Doe",
            annual_income=95000.0,
            monthly_debt=1200.0,
            requested_amount=100000.0,
            loan_purpose="casino_gambling",
        )
        codes = [v.code for v in result.violations]
        assert "INVALID_LOAN_PURPOSE" in codes

    def test_multiple_violations_collected(self):
        result = validate_loan_input(
            applicant_name="J",  # too short
            annual_income=-1000.0,  # negative
            monthly_debt=-500.0,  # negative
            requested_amount=0.0,  # zero
            loan_purpose="home_purchase",
        )
        assert result.passed is False
        assert len(result.violations) >= 3


class TestValidateDecisionOutput:
    """Tests for decision output guardrail validator."""

    def test_valid_approve_decision_passes(self):
        decision = {
            "recommendation": "APPROVE",
            "confidence_score": 0.85,
            "explanation": (
                "The applicant has a strong FICO score of 740 and a DTI of 15.2%, "
                "well within conventional guidelines."
            ),
        }
        result = validate_decision_output(decision)
        assert result.passed is True

    def test_valid_reject_decision_passes(self):
        decision = {
            "recommendation": "REJECT",
            "confidence_score": 0.90,
            "explanation": (
                "The applicant's DTI of 58% significantly exceeds the maximum 43% "
                "threshold for conventional loans. Credit score of 550 is below minimum."
            ),
        }
        result = validate_decision_output(decision)
        assert result.passed is True

    def test_valid_manual_review_passes(self):
        decision = {
            "recommendation": "MANUAL_REVIEW",
            "confidence_score": 0.60,
            "explanation": "Borderline DTI of 44% requires manual underwriter review.",
        }
        result = validate_decision_output(decision)
        assert result.passed is True

    def test_missing_recommendation_fails(self):
        decision = {
            "confidence_score": 0.85,
            "explanation": "Some explanation here.",
        }
        result = validate_decision_output(decision)
        assert result.passed is False
        codes = [v.code for v in result.violations]
        assert "MISSING_FIELD" in codes

    def test_invalid_recommendation_value_fails(self):
        decision = {
            "recommendation": "MAYBE",
            "confidence_score": 0.5,
            "explanation": "Some explanation here.",
        }
        result = validate_decision_output(decision)
        assert result.passed is False
        codes = [v.code for v in result.violations]
        assert "INVALID_RECOMMENDATION" in codes

    def test_confidence_out_of_range_fails(self):
        decision = {
            "recommendation": "APPROVE",
            "confidence_score": 1.5,  # > 1.0
            "explanation": "Some explanation here.",
        }
        result = validate_decision_output(decision)
        assert result.passed is False
        codes = [v.code for v in result.violations]
        assert "INVALID_CONFIDENCE" in codes

    def test_protected_class_reference_is_critical(self):
        decision = {
            "recommendation": "REJECT",
            "confidence_score": 0.9,
            "explanation": (
                "The applicant's race and national origin were considered in this decision."
            ),
        }
        result = validate_decision_output(decision)
        assert result.passed is False
        critical = [v for v in result.violations if v.severity == GuardrailSeverity.CRITICAL]
        assert len(critical) > 0

    def test_short_explanation_warns(self):
        decision = {
            "recommendation": "APPROVE",
            "confidence_score": 0.8,
            "explanation": "Good.",
        }
        result = validate_decision_output(decision)
        codes = [v.code for v in result.violations]
        assert "EXPLANATION_TOO_SHORT" in codes


class TestSanitiseDocumentText:
    """Tests for PII redaction in document text."""

    def test_ssn_redacted(self):
        text = "Applicant SSN: 123-45-6789 on file."
        sanitised, notices = sanitise_document_text(text)
        assert "123-45-6789" not in sanitised
        assert "[REDACTED_SSN]" in sanitised
        assert any("SSN" in n for n in notices)

    def test_clean_text_unchanged(self):
        text = "Annual income: $95,000. Monthly debt: $1,200."
        sanitised, notices = sanitise_document_text(text)
        assert sanitised == text
        assert notices == []

    def test_multiple_pii_types_redacted(self):
        text = "SSN: 987-65-4321. Passport: AB1234567."
        sanitised, notices = sanitise_document_text(text)
        assert "987-65-4321" not in sanitised
        assert len(notices) >= 1
