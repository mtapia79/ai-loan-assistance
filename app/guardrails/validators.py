"""
Guardrails – Input / Output Validation

Provides three layers of protection:
1. Input sanitisation  – detect PII leakage in free-text fields
2. Output validation   – ensure LLM responses meet structural requirements
3. Bias detection      – flag any protected-class references in reasoning

These run synchronously to avoid adding async complexity to the hot path.
"""

import re
from dataclasses import dataclass, field
from enum import Enum


class GuardrailSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class GuardrailViolation:
    code: str
    message: str
    severity: GuardrailSeverity
    field: str | None = None


@dataclass
class GuardrailResult:
    passed: bool
    violations: list[GuardrailViolation] = field(default_factory=list)

    def add(self, violation: GuardrailViolation) -> None:
        self.violations.append(violation)
        if violation.severity in (GuardrailSeverity.ERROR, GuardrailSeverity.CRITICAL):
            self.passed = False

    @property
    def has_errors(self) -> bool:
        return any(
            v.severity in (GuardrailSeverity.ERROR, GuardrailSeverity.CRITICAL)
            for v in self.violations
        )


# ── PII Patterns ─────────────────────────────────────────────────────────────

_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CREDIT_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,16}\b")
_PASSPORT_RE = re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")

_PROTECTED_CLASS_TERMS = frozenset([
    "race", "ethnicity", "color", "religion", "national origin",
    "sex", "gender", "marital status", "familial status",
    "disability", "age", "source of income", "public assistance",
])


# ── Input Validator ───────────────────────────────────────────────────────────

def validate_loan_input(
    applicant_name: str,
    annual_income: float,
    monthly_debt: float,
    requested_amount: float,
    loan_purpose: str,
) -> GuardrailResult:
    """
    Validate loan application input for PII leakage, range violations,
    and potential policy violations.

    Returns a GuardrailResult; if .passed is False the request should be
    rejected before reaching the agents.
    """
    result = GuardrailResult(passed=True)

    # ── Name sanity ───────────────────────────────────────────────
    if len(applicant_name.strip()) < 2:
        result.add(GuardrailViolation(
            code="NAME_TOO_SHORT",
            message="Applicant name is too short.",
            severity=GuardrailSeverity.ERROR,
            field="applicant_name",
        ))

    # Detect SSN in name field
    if _SSN_RE.search(applicant_name):
        result.add(GuardrailViolation(
            code="PII_SSN_IN_NAME",
            message="SSN pattern detected in applicant name field.",
            severity=GuardrailSeverity.CRITICAL,
            field="applicant_name",
        ))

    # ── Financial range validation ────────────────────────────────
    if annual_income <= 0:
        result.add(GuardrailViolation(
            code="INCOME_NON_POSITIVE",
            message="Annual income must be positive.",
            severity=GuardrailSeverity.ERROR,
            field="annual_income",
        ))

    if monthly_debt < 0:
        result.add(GuardrailViolation(
            code="DEBT_NEGATIVE",
            message="Monthly debt cannot be negative.",
            severity=GuardrailSeverity.ERROR,
            field="monthly_debt",
        ))

    if requested_amount <= 0:
        result.add(GuardrailViolation(
            code="AMOUNT_NON_POSITIVE",
            message="Requested loan amount must be positive.",
            severity=GuardrailSeverity.ERROR,
            field="requested_amount",
        ))

    # Sanity: debt cannot exceed income by extreme amount
    if annual_income > 0:
        monthly_income = annual_income / 12
        if monthly_debt > monthly_income * 2:
            result.add(GuardrailViolation(
                code="DEBT_EXCEEDS_INCOME_2X",
                message="Monthly debt exceeds 2x monthly income – verify data.",
                severity=GuardrailSeverity.WARNING,
                field="monthly_debt",
            ))

    # Loan purpose whitelist
    allowed_purposes = {
        "home_purchase", "refinance", "home_equity", "auto",
        "personal", "business", "student", "medical", "other",
    }
    if loan_purpose.lower() not in allowed_purposes:
        result.add(GuardrailViolation(
            code="INVALID_LOAN_PURPOSE",
            message=f"Loan purpose '{loan_purpose}' is not in the allowed list.",
            severity=GuardrailSeverity.WARNING,
            field="loan_purpose",
        ))

    return result


# ── Output Validator ──────────────────────────────────────────────────────────

def validate_decision_output(decision: dict) -> GuardrailResult:
    """
    Validate the decision agent's output before returning to the caller.

    Checks structural completeness and scans reasoning for bias indicators.
    """
    result = GuardrailResult(passed=True)

    # Structural checks
    required_fields = ["recommendation", "confidence_score", "explanation"]
    for f_ in required_fields:
        if f_ not in decision:
            result.add(GuardrailViolation(
                code="MISSING_FIELD",
                message=f"Decision output missing required field: {f_}",
                severity=GuardrailSeverity.ERROR,
                field=f_,
            ))

    # Recommendation must be one of the allowed values
    allowed = {"APPROVE", "REJECT", "MANUAL_REVIEW"}
    recommendation = decision.get("recommendation", "")
    if recommendation not in allowed:
        result.add(GuardrailViolation(
            code="INVALID_RECOMMENDATION",
            message=f"Recommendation '{recommendation}' is not valid.",
            severity=GuardrailSeverity.ERROR,
            field="recommendation",
        ))

    # Confidence score range
    confidence = decision.get("confidence_score", -1)
    if not (0.0 <= confidence <= 1.0):
        result.add(GuardrailViolation(
            code="INVALID_CONFIDENCE",
            message=f"Confidence score {confidence} is outside [0, 1].",
            severity=GuardrailSeverity.ERROR,
            field="confidence_score",
        ))

    # Bias scan on explanation
    explanation = decision.get("explanation", "").lower()
    for term in _PROTECTED_CLASS_TERMS:
        if term in explanation:
            result.add(GuardrailViolation(
                code="BIAS_PROTECTED_CLASS",
                message=f"Explanation references protected class term: '{term}'.",
                severity=GuardrailSeverity.CRITICAL,
                field="explanation",
            ))

    # Explanation minimum length
    if len(decision.get("explanation", "")) < 20:
        result.add(GuardrailViolation(
            code="EXPLANATION_TOO_SHORT",
            message="Decision explanation is too brief to be meaningful.",
            severity=GuardrailSeverity.WARNING,
            field="explanation",
        ))

    return result


# ── Document Content Guard ────────────────────────────────────────────────────

def sanitise_document_text(text: str) -> tuple[str, list[str]]:
    """
    Redact PII patterns from document text before sending to the LLM.

    Returns (sanitised_text, list_of_redaction_notices).
    """
    notices: list[str] = []
    sanitised = text

    if _SSN_RE.search(sanitised):
        sanitised = _SSN_RE.sub("[REDACTED_SSN]", sanitised)
        notices.append("SSN pattern redacted")

    if _CREDIT_CARD_RE.search(sanitised):
        sanitised = _CREDIT_CARD_RE.sub("[REDACTED_CC]", sanitised)
        notices.append("Credit card pattern redacted")

    if _PASSPORT_RE.search(sanitised):
        sanitised = _PASSPORT_RE.sub("[REDACTED_PASSPORT]", sanitised)
        notices.append("Passport pattern redacted")

    return sanitised, notices
