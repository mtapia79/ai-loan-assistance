"""
API Routes – Loan Applications

Endpoints for submitting loan applications and retrieving decisions.
"""

import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import process_loan_application
from app.db.session import get_session
from app.evaluation.evaluator import evaluate_decision
from app.guardrails.validators import (
    sanitise_document_text,
    validate_decision_output,
    validate_loan_input,
)
from app.observability.logging import get_logger
from app.schemas.loan import (
    AgentStep,
    EvaluationResult,
    LoanApplicationRequest,
    LoanDecisionResponse,
)

router = APIRouter(prefix="/api/v1/loans", tags=["loans"])
logger = get_logger(__name__)


@router.post(
    "/analyze",
    response_model=LoanDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze a loan application",
    description=(
        "Submit a loan application for AI-assisted analysis. "
        "Returns an explainable recommendation: APPROVE, REJECT, or MANUAL_REVIEW. "
        "The final credit decision is always made by a human loan officer."
    ),
)
async def analyze_loan_application(
    request: LoanApplicationRequest,
    db: AsyncSession = Depends(get_session),
) -> LoanDecisionResponse:
    """
    Main endpoint: run the full multi-agent loan analysis pipeline.

    1. Validate input (guardrails)
    2. Run LangGraph orchestration (credit → document → policy → decision)
    3. Validate output (guardrails)
    4. Return structured decision with explainability
    """
    start_time = time.time()

    # ── Input Guardrails ───────────────────────────────────────────
    guard_result = validate_loan_input(
        applicant_name=request.applicant_name,
        annual_income=request.annual_income,
        monthly_debt=request.monthly_debt,
        requested_amount=request.requested_amount,
        loan_purpose=request.loan_purpose,
    )
    if guard_result.has_errors:
        violations = [f"{v.code}: {v.message}" for v in guard_result.violations]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Input validation failed", "violations": violations},
        )

    # ── Run Agent Orchestration ────────────────────────────────────
    logger.info(
        "loan_analysis_start",
        applicant=request.applicant_email,
        purpose=request.loan_purpose,
        amount=request.requested_amount,
    )

    try:
        result = await process_loan_application(
            applicant_name=request.applicant_name,
            applicant_email=request.applicant_email,
            annual_income=request.annual_income,
            monthly_debt=request.monthly_debt,
            requested_amount=request.requested_amount,
            loan_purpose=request.loan_purpose,
            credit_score=request.credit_score,
            document_texts=[],  # documents handled via separate upload endpoint
            db_session=db,
        )
    except Exception as exc:
        logger.error("orchestration_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Loan analysis failed", "error": str(exc)},
        ) from exc

    decision = result["decision"]

    # ── Output Guardrails ──────────────────────────────────────────
    output_guard = validate_decision_output(decision)
    if output_guard.has_errors:
        logger.warning(
            "output_guardrail_triggered",
            violations=[v.code for v in output_guard.violations],
        )
        # Override to MANUAL_REVIEW rather than returning a bad decision
        decision["recommendation"] = "MANUAL_REVIEW"
        decision["explanation"] = (
            decision.get("explanation", "")
            + " [Escalated to manual review by output guardrail]"
        )

    # ── Build Response ─────────────────────────────────────────────
    monthly_income = request.annual_income / 12
    dti = (request.monthly_debt / monthly_income) if monthly_income > 0 else 1.0

    credit = result.get("credit_findings", {})
    doc = result.get("document_findings", {})
    policy = result.get("policy_findings", {})

    agent_steps = [
        AgentStep(
            agent="CreditAgent",
            finding=(
                f"FICO {credit.get('credit_score', 'N/A')} | "
                f"DTI {credit.get('dti_ratio', 'N/A')}% | "
                f"Risk: {credit.get('risk_tier', 'N/A')}"
            ),
            confidence=float(credit.get("confidence", 0.5)),
            details={"preliminary": credit.get("preliminary_recommendation")},
        ),
        AgentStep(
            agent="DocumentAgent",
            finding=(
                f"Documentation quality: {doc.get('documentation_quality', 'N/A')} | "
                f"Income verified: {doc.get('income_verified', False)}"
            ),
            confidence=float(doc.get("confidence", 0.5)),
            details={"flags": doc.get("flags", [])},
        ),
        AgentStep(
            agent="PolicyAgent",
            finding=(
                f"Policy compliance: {policy.get('policy_compliance', 'N/A')} | "
                f"Manual triggers: {len(policy.get('manual_review_triggers', []))}"
            ),
            confidence=float(policy.get("confidence", 0.5)),
            details={"triggers": policy.get("manual_review_triggers", [])},
        ),
        AgentStep(
            agent="DecisionAgent",
            finding=decision.get("explanation", "")[:200],
            confidence=float(decision.get("confidence_score", 0.5)),
            details={
                "factors_for": decision.get("key_factors_for", []),
                "factors_against": decision.get("key_factors_against", []),
            },
        ),
    ]

    elapsed_ms = int((time.time() - start_time) * 1000)

    from app.config import get_settings
    settings = get_settings()

    return LoanDecisionResponse(
        application_id=uuid.UUID(result["application_id"]),
        recommendation=decision.get("recommendation", "MANUAL_REVIEW"),
        confidence_score=float(decision.get("confidence_score", 0.0)),
        explanation=decision.get("explanation", ""),
        debt_to_income_ratio=round(dti, 4),
        agent_steps=agent_steps,
        processing_time_ms=elapsed_ms,
        model_used=settings.openai_model,
        created_at=datetime.now(tz=timezone.utc),
    )


@router.post(
    "/analyze/evaluate",
    response_model=EvaluationResult,
    status_code=status.HTTP_200_OK,
    summary="Evaluate a loan decision",
    description="Run quality evaluation on a previously generated loan decision.",
)
async def evaluate_loan_decision(
    request: LoanApplicationRequest,
    db: AsyncSession = Depends(get_session),
) -> EvaluationResult:
    """
    Run the full pipeline then evaluate the decision quality.
    Useful for monitoring and A/B testing model changes.
    """
    # Re-run analysis to get the full result dict
    result = await process_loan_application(
        applicant_name=request.applicant_name,
        applicant_email=request.applicant_email,
        annual_income=request.annual_income,
        monthly_debt=request.monthly_debt,
        requested_amount=request.requested_amount,
        loan_purpose=request.loan_purpose,
        credit_score=request.credit_score,
        db_session=db,
    )

    return evaluate_decision(
        application_id=result["application_id"],
        decision=result["decision"],
        agent_findings=result,
    )
