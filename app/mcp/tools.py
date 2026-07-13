"""
MCP – Tool Definitions

Defines the tool schema that each agent can call via the Model Context
Protocol (MCP).  In a real deployment these tools would be served by a
dedicated MCP server; here they are implemented as async Python functions
and registered as LangChain tools for use within LangGraph.

Tools exposed:
  • get_credit_report   – retrieve mock credit profile
  • calculate_dti       – compute debt-to-income ratio
  • retrieve_policies   – semantic search against pgvector policy store
  • extract_document    – parse financial document text
  • flag_for_compliance – run fair-lending compliance checks
"""

from langchain_core.tools import tool

from app.observability.logging import get_logger

logger = get_logger(__name__)


# ── Credit Report Tool ────────────────────────────────────────────────────────


@tool
async def get_credit_report(applicant_email: str, credit_score: int | None = None) -> dict:
    """
    Retrieve a credit report for the given applicant.

    In production this would call a credit bureau API (Equifax, Experian, TransUnion).
    For demo purposes a structured mock report is returned based on the FICO score.

    Args:
        applicant_email: The applicant's email (used as identifier).
        credit_score: Known FICO score (optional; bureau would provide this).

    Returns:
        Structured credit report dict.
    """
    score = credit_score or 700  # default to average if not provided

    if score >= 740:
        risk_tier = "EXCELLENT"
        derogatory_marks = 0
        payment_history = "Perfect – no lates in 7 years"
    elif score >= 670:
        risk_tier = "GOOD"
        derogatory_marks = 1
        payment_history = "1 late payment (30 days) in past 36 months"
    elif score >= 580:
        risk_tier = "FAIR"
        derogatory_marks = 3
        payment_history = "Multiple lates; 1 collection account"
    else:
        risk_tier = "POOR"
        derogatory_marks = 5
        payment_history = "Significant derogatory history; possible collections"

    report = {
        "applicant_email": applicant_email,
        "fico_score": score,
        "risk_tier": risk_tier,
        "derogatory_marks": derogatory_marks,
        "payment_history": payment_history,
        "open_accounts": 8,
        "credit_utilization_pct": max(0, min(100, 110 - score // 7)),
        "oldest_account_years": max(1, (score - 500) // 30),
        "hard_inquiries_12m": max(0, 5 - score // 150),
        "bankruptcy": score < 520,
        "foreclosure": score < 500,
    }

    logger.info("credit_report_fetched", email=applicant_email, risk_tier=risk_tier)
    return report


# ── DTI Calculator Tool ───────────────────────────────────────────────────────


@tool
def calculate_dti(annual_income: float, monthly_debt: float) -> dict:
    """
    Calculate the debt-to-income ratio and provide a risk classification.

    Args:
        annual_income: Gross annual income in USD.
        monthly_debt: Total monthly debt obligations in USD.

    Returns:
        Dict with dti_ratio, monthly_income, risk_level, and policy_note.
    """
    monthly_income = annual_income / 12
    dti_ratio = (monthly_debt / monthly_income) * 100 if monthly_income > 0 else 100.0

    if dti_ratio <= 28:
        risk_level = "LOW"
        policy_note = "DTI well within guidelines. Strong qualification."
    elif dti_ratio <= 36:
        risk_level = "MODERATE"
        policy_note = "DTI within acceptable range. Standard underwriting."
    elif dti_ratio <= 43:
        risk_level = "ELEVATED"
        policy_note = "DTI at upper conventional limit. Compensating factors needed."
    elif dti_ratio <= 50:
        risk_level = "HIGH"
        policy_note = "DTI exceeds conventional limit. Manual review required."
    else:
        risk_level = "CRITICAL"
        policy_note = "DTI exceeds maximum allowable threshold. Likely decline."

    result = {
        "monthly_income": round(monthly_income, 2),
        "monthly_debt": round(monthly_debt, 2),
        "dti_ratio": round(dti_ratio, 2),
        "risk_level": risk_level,
        "policy_note": policy_note,
        "front_end_ratio": round(
            (monthly_debt * 0.6 / monthly_income) * 100 if monthly_income > 0 else 100.0, 2
        ),
    }

    logger.info("dti_calculated", dti=dti_ratio, risk=risk_level)
    return result


# ── Policy Retrieval Tool ─────────────────────────────────────────────────────


@tool
async def retrieve_policies(query: str, db_session=None) -> str:
    """
    Perform semantic search against the lending policy knowledge base.

    Args:
        query: Natural language query about lending policy.
        db_session: SQLAlchemy async session (injected by agent).

    Returns:
        Formatted string of the most relevant policy excerpts.
    """
    if db_session is None:
        return (
            "Policy retrieval requires a database session. "
            "Falling back to general lending guidelines: "
            "Standard DTI limit is 43% for conventional loans. "
            "Minimum credit score 620 for conventional, 580 for FHA."
        )

    from app.rag.retriever import PolicyRetriever

    retriever = PolicyRetriever(session=db_session)
    chunks = await retriever.retrieve(query)
    return retriever.format_context(chunks)


# ── Document Extraction Tool ──────────────────────────────────────────────────


@tool
def extract_document_data(document_text: str) -> dict:
    """
    Extract structured financial data from raw document text.

    In production this would use a document AI model (e.g., AWS Textract).
    For demo purposes, key financial indicators are pattern-matched.

    Args:
        document_text: Raw text content of the uploaded financial document.

    Returns:
        Dict of extracted financial indicators.
    """
    import re

    # Simple extraction patterns (production would use NLP/OCR models)
    income_match = re.search(
        r"(?:gross income|total income|annual income)[:\s]+\$?([\d,]+)", document_text, re.I
    )
    debt_match = re.search(
        r"(?:total debt|monthly payment|debt obligations)[:\s]+\$?([\d,]+)",
        document_text,
        re.I,
    )
    assets_match = re.search(
        r"(?:total assets|cash and savings)[:\s]+\$?([\d,]+)", document_text, re.I
    )

    extracted = {
        "document_type": "financial_statement",
        "income_found": income_match is not None,
        "extracted_income": (
            float(income_match.group(1).replace(",", "")) if income_match else None
        ),
        "debt_found": debt_match is not None,
        "extracted_monthly_debt": (
            float(debt_match.group(1).replace(",", "")) if debt_match else None
        ),
        "assets_found": assets_match is not None,
        "extracted_assets": (
            float(assets_match.group(1).replace(",", "")) if assets_match else None
        ),
        "extraction_confidence": 0.85 if income_match else 0.40,
        "flags": [] if income_match and debt_match else ["incomplete_documentation"],
    }

    logger.info("document_extracted", confidence=extracted["extraction_confidence"])
    return extracted


# ── Compliance Checker Tool ───────────────────────────────────────────────────


@tool
def flag_for_compliance(
    recommendation: str,
    reasoning: str,
    loan_purpose: str,
) -> dict:
    """
    Run a fair-lending compliance check on the proposed recommendation.

    Checks for potential ECOA/FHA violations and bias indicators.

    Args:
        recommendation: Proposed decision (APPROVE / REJECT / MANUAL_REVIEW).
        reasoning: The textual reasoning provided by the decision agent.
        loan_purpose: The stated purpose of the loan.

    Returns:
        Compliance result dict with flags and override instructions.
    """
    flags: list[str] = []
    override = False

    # Protected characteristic leak detection
    protected_terms = [
        "race",
        "color",
        "religion",
        "national origin",
        "sex",
        "gender",
        "marital status",
        "age",
        "disability",
        "children",
        "familial status",
        "public assistance",
        "neighborhood",
        "zip code",
    ]
    reasoning_lower = reasoning.lower()
    for term in protected_terms:
        if term in reasoning_lower:
            flags.append(f"ECOA_VIOLATION: reasoning references '{term}'")
            override = True

    # Disparate impact heuristic (simplified)
    if recommendation == "REJECT" and not any(
        kw in reasoning_lower
        for kw in ["dti", "credit score", "income", "debt", "payment history", "ltv"]
    ):
        flags.append("ADVERSE_ACTION: rejection lacks documented creditworthiness basis")

    result = {
        "compliant": len(flags) == 0,
        "flags": flags,
        "override_recommendation": override,
        "suggested_action": ("ESCALATE_TO_COMPLIANCE" if override else "PROCEED"),
        "adverse_action_required": recommendation == "REJECT",
    }

    logger.info(
        "compliance_check_complete",
        compliant=result["compliant"],
        flag_count=len(flags),
    )
    return result


# ── Tool Registry ─────────────────────────────────────────────────────────────

ALL_TOOLS = [
    get_credit_report,
    calculate_dti,
    retrieve_policies,
    extract_document_data,
    flag_for_compliance,
]
