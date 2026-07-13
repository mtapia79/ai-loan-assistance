"""
Unit Tests – MCP Tools

Tests the tool functions directly (no LLM required).
"""

import pytest

from app.mcp.tools import calculate_dti, extract_document_data, flag_for_compliance


class TestCalculateDTI:
    """Tests for the DTI calculator tool."""

    def test_low_dti(self):
        result = calculate_dti.invoke(
            {"annual_income": 120000.0, "monthly_debt": 500.0}
        )
        assert result["dti_ratio"] == pytest.approx(5.0, rel=0.01)
        assert result["risk_level"] == "LOW"

    def test_moderate_dti(self):
        result = calculate_dti.invoke(
            {"annual_income": 60000.0, "monthly_debt": 1500.0}
        )
        # monthly_income = 5000, dti = 30%
        assert result["dti_ratio"] == pytest.approx(30.0, rel=0.01)
        assert result["risk_level"] == "MODERATE"

    def test_elevated_dti_at_limit(self):
        result = calculate_dti.invoke(
            {"annual_income": 60000.0, "monthly_debt": 2000.0}
        )
        # monthly_income = 5000, dti = 40%
        assert result["dti_ratio"] == pytest.approx(40.0, rel=0.01)
        assert result["risk_level"] == "ELEVATED"

    def test_critical_dti(self):
        result = calculate_dti.invoke(
            {"annual_income": 24000.0, "monthly_debt": 2000.0}
        )
        # monthly_income = 2000, dti = 100%
        assert result["dti_ratio"] == pytest.approx(100.0, rel=0.01)
        assert result["risk_level"] == "CRITICAL"

    def test_zero_income_handled(self):
        result = calculate_dti.invoke(
            {"annual_income": 0.0, "monthly_debt": 1000.0}
        )
        # Should not raise ZeroDivisionError
        assert result["dti_ratio"] == 100.0
        assert result["risk_level"] == "CRITICAL"

    def test_zero_debt(self):
        result = calculate_dti.invoke(
            {"annual_income": 100000.0, "monthly_debt": 0.0}
        )
        assert result["dti_ratio"] == 0.0
        assert result["risk_level"] == "LOW"

    def test_monthly_income_in_result(self):
        result = calculate_dti.invoke(
            {"annual_income": 120000.0, "monthly_debt": 1000.0}
        )
        assert result["monthly_income"] == pytest.approx(10000.0, rel=0.01)


class TestExtractDocumentData:
    """Tests for the document extraction tool."""

    def test_extract_income_from_w2(self):
        text = "Total Income: $95,000 for the tax year. Monthly Payment: $1,200."
        result = extract_document_data.invoke({"document_text": text})
        assert result["income_found"] is True
        assert result["extracted_income"] == pytest.approx(95000.0, rel=0.01)

    def test_no_data_in_empty_text(self):
        result = extract_document_data.invoke({"document_text": ""})
        assert result["income_found"] is False
        assert result["extraction_confidence"] < 0.5

    def test_flags_incomplete_documentation(self):
        result = extract_document_data.invoke({"document_text": "Some text without numbers."})
        assert "incomplete_documentation" in result["flags"]


class TestFlagForCompliance:
    """Tests for the compliance checker tool."""

    def test_clean_approval_passes(self):
        result = flag_for_compliance.invoke(
            {
                "recommendation": "APPROVE",
                "reasoning": (
                    "Applicant has strong credit score of 740, DTI of 15%, "
                    "and meets all income requirements."
                ),
                "loan_purpose": "home_purchase",
            }
        )
        assert result["compliant"] is True
        assert result["flags"] == []
        assert result["override_recommendation"] is False

    def test_protected_class_reference_flagged(self):
        result = flag_for_compliance.invoke(
            {
                "recommendation": "REJECT",
                "reasoning": (
                    "Applicant's race and national origin were considered."
                ),
                "loan_purpose": "personal",
            }
        )
        assert result["compliant"] is False
        assert result["override_recommendation"] is True
        assert any("ECOA_VIOLATION" in f for f in result["flags"])

    def test_reject_without_creditworthiness_basis_flagged(self):
        result = flag_for_compliance.invoke(
            {
                "recommendation": "REJECT",
                "reasoning": "We don't like this applicant.",
                "loan_purpose": "personal",
            }
        )
        assert result["compliant"] is False
        assert any("ADVERSE_ACTION" in f for f in result["flags"])

    def test_adverse_action_flag_on_reject(self):
        result = flag_for_compliance.invoke(
            {
                "recommendation": "REJECT",
                "reasoning": "DTI of 55% exceeds maximum guideline of 43%.",
                "loan_purpose": "personal",
            }
        )
        assert result["adverse_action_required"] is True

    def test_adverse_action_not_required_for_approve(self):
        result = flag_for_compliance.invoke(
            {
                "recommendation": "APPROVE",
                "reasoning": "All criteria met.",
                "loan_purpose": "home_purchase",
            }
        )
        assert result["adverse_action_required"] is False
