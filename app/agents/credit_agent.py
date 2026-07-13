"""
Agents – Credit Analysis Agent

Retrieves and interprets the credit report for an applicant.
"""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.mcp.tools import calculate_dti, get_credit_report
from app.observability.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a Credit Analysis Agent for a financial institution.
Your job is to evaluate an applicant's creditworthiness objectively.

You have access to:
- get_credit_report: Fetch the applicant's credit profile
- calculate_dti: Compute debt-to-income ratio

Analyse the credit data and provide:
1. FICO score assessment
2. DTI ratio analysis
3. Payment history evaluation
4. Risk tier classification
5. Confidence score (0.0–1.0)

Be factual and cite specific numbers. Do NOT reference any protected characteristics.
Respond in structured JSON matching:
{
  "credit_score": int,
  "risk_tier": "EXCELLENT|GOOD|FAIR|POOR",
  "dti_ratio": float,
  "dti_risk_level": "LOW|MODERATE|ELEVATED|HIGH|CRITICAL",
  "payment_history_summary": str,
  "key_findings": [str],
  "confidence": float,
  "preliminary_recommendation": "APPROVE|REJECT|MANUAL_REVIEW"
}
"""


async def run_credit_agent(
    applicant_email: str,
    annual_income: float,
    monthly_debt: float,
    credit_score: int | None,
    llm: ChatOpenAI,
) -> dict:
    """
    Execute the credit analysis agent.

    Args:
        applicant_email: Applicant identifier.
        annual_income: Annual gross income.
        monthly_debt: Total monthly debt obligations.
        credit_score: Known FICO score (may be None).
        llm: Configured ChatOpenAI instance.

    Returns:
        Structured credit analysis result dict.
    """
    import json

    logger.info("credit_agent_start", email=applicant_email)

    # Invoke tools directly (in a full MCP setup these would be remote calls)
    credit_report = await get_credit_report.ainvoke(
        {"applicant_email": applicant_email, "credit_score": credit_score}
    )
    dti_result = calculate_dti.invoke(
        {"annual_income": annual_income, "monthly_debt": monthly_debt}
    )

    user_content = f"""
Applicant: {applicant_email}
Credit Report: {json.dumps(credit_report, indent=2)}
DTI Analysis: {json.dumps(dti_result, indent=2)}

Please provide your credit analysis assessment.
"""

    llm_with_json = llm.bind(response_format={"type": "json_object"})
    response = await llm_with_json.ainvoke(
        [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
    )

    try:
        result = json.loads(response.content)
    except json.JSONDecodeError:
        result = {
            "credit_score": credit_report.get("fico_score", 0),
            "risk_tier": credit_report.get("risk_tier", "FAIR"),
            "dti_ratio": dti_result.get("dti_ratio", 0),
            "dti_risk_level": dti_result.get("risk_level", "ELEVATED"),
            "payment_history_summary": credit_report.get("payment_history", ""),
            "key_findings": ["Structured parsing failed; using raw credit data"],
            "confidence": 0.5,
            "preliminary_recommendation": "MANUAL_REVIEW",
        }

    # Merge raw tool data for downstream agents
    result["_raw_credit"] = credit_report
    result["_raw_dti"] = dti_result

    logger.info(
        "credit_agent_complete",
        risk_tier=result.get("risk_tier"),
        preliminary=result.get("preliminary_recommendation"),
    )
    return result
