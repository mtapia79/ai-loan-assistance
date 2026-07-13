"""
Schemas – Loan Application Request / Response Models

All public API contracts are defined here with strict validation.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator

# ── Request Models ────────────────────────────────────────────────────────────

class LoanApplicationRequest(BaseModel):
    """Incoming loan application from the loan officer UI or API client."""

    applicant_name: str = Field(..., min_length=2, max_length=255, examples=["Jane Doe"])
    applicant_email: EmailStr = Field(..., examples=["jane.doe@example.com"])

    annual_income: float = Field(..., gt=0, description="Annual gross income in USD")
    monthly_debt: float = Field(..., ge=0, description="Total monthly debt payments in USD")
    requested_amount: float = Field(..., gt=0, description="Loan amount requested in USD")
    loan_purpose: str = Field(
        ...,
        min_length=2,
        max_length=100,
        examples=["home_purchase", "auto", "personal", "business"],
    )
    credit_score: int | None = Field(
        default=None, ge=300, le=850, description="FICO score if available"
    )

    @field_validator("annual_income", "monthly_debt", "requested_amount")
    @classmethod
    def round_currency(cls, v: float) -> float:
        return round(v, 2)

    @field_validator("loan_purpose")
    @classmethod
    def normalize_purpose(cls, v: str) -> str:
        return v.lower().strip()

    model_config = {
        "json_schema_extra": {
            "example": {
                "applicant_name": "Jane Doe",
                "applicant_email": "jane.doe@example.com",
                "annual_income": 95000.00,
                "monthly_debt": 1200.00,
                "requested_amount": 350000.00,
                "loan_purpose": "home_purchase",
                "credit_score": 740,
            }
        }
    }


# ── Response Models ───────────────────────────────────────────────────────────

class AgentStep(BaseModel):
    """Single agent reasoning step for explainability."""

    agent: str
    finding: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    details: dict[str, Any] | None = None


class LoanDecisionResponse(BaseModel):
    """Full loan decision with explainable AI reasoning trace."""

    application_id: uuid.UUID
    recommendation: str = Field(..., pattern="^(APPROVE|REJECT|MANUAL_REVIEW)$")
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    explanation: str = Field(..., description="Human-readable decision explanation")

    # Explainability breakdown
    debt_to_income_ratio: float = Field(..., description="DTI ratio (lower is better)")
    agent_steps: list[AgentStep] = Field(
        default_factory=list, description="Step-by-step agent reasoning"
    )

    # Metadata
    processing_time_ms: int
    model_used: str
    created_at: datetime

    model_config = {"from_attributes": True}


class LoanApplicationResponse(BaseModel):
    """Minimal response immediately after submission (async processing)."""

    application_id: uuid.UUID
    status: str
    message: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Health Check ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    env: str
    checks: dict[str, str]


# ── Evaluation ────────────────────────────────────────────────────────────────

class EvaluationResult(BaseModel):
    """LLM quality evaluation result for a single decision."""

    application_id: uuid.UUID
    faithfulness_score: float = Field(..., ge=0.0, le=1.0)
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    coherence_score: float = Field(..., ge=0.0, le=1.0)
    overall_score: float = Field(..., ge=0.0, le=1.0)
    flags: list[str] = Field(default_factory=list)
    evaluated_at: datetime
