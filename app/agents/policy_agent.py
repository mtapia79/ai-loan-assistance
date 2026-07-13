"""
Agents – Policy RAG Agent

Retrieves relevant lending policies and interprets them for the application.
"""

import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.observability.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a Lending Policy Compliance Agent.
Your job is to retrieve and apply the relevant lending policies to the application.

You will receive:
- Application summary (income, debt, credit score, loan purpose, amount)
- Relevant policy excerpts from the knowledge base

Determine which policies apply and whether the application meets them.
Respond in structured JSON:
{
  "policies_applied": [str],
  "policy_compliance": "COMPLIANT|NON_COMPLIANT|BORDERLINE",
  "policy_findings": [
    {"policy": str, "status": "PASS|FAIL|BORDERLINE", "note": str}
  ],
  "manual_review_triggers": [str],
  "confidence": float,
  "summary": str
}
"""


async def run_policy_agent(
    annual_income: float,
    monthly_debt: float,
    requested_amount: float,
    credit_score: int | None,
    loan_purpose: str,
    policy_context: str,
    llm: ChatOpenAI,
) -> dict:
    """
    Execute the policy RAG agent.

    Args:
        annual_income: Annual gross income.
        monthly_debt: Monthly debt obligations.
        requested_amount: Loan amount requested.
        credit_score: FICO score.
        loan_purpose: Purpose of the loan.
        policy_context: Retrieved policy text from pgvector.
        llm: Configured ChatOpenAI instance.

    Returns:
        Structured policy compliance result dict.
    """
    logger.info("policy_agent_start", loan_purpose=loan_purpose)

    monthly_income = annual_income / 12
    dti_pct = round((monthly_debt / monthly_income) * 100, 1) if monthly_income > 0 else 100.0

    user_content = f"""
APPLICATION SUMMARY
===================
Annual Income: ${annual_income:,.2f}
Monthly Income: ${monthly_income:,.2f}
Monthly Debt: ${monthly_debt:,.2f}
DTI Ratio: {dti_pct}%
Requested Amount: ${requested_amount:,.2f}
Credit Score: {credit_score or 'Not provided'}
Loan Purpose: {loan_purpose}

RELEVANT POLICIES
=================
{policy_context}

Please apply the relevant policies and provide your compliance assessment.
"""

    llm_with_json = llm.bind(response_format={"type": "json_object"})
    response = await llm_with_json.ainvoke(
        [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_content),
        ]
    )
    response_content = (
        response.content if isinstance(response.content, str) else json.dumps(response.content)
    )

    try:
        result = json.loads(response_content)
    except json.JSONDecodeError:
        result = {
            "policies_applied": [],
            "policy_compliance": "BORDERLINE",
            "policy_findings": [],
            "manual_review_triggers": ["parse_error"],
            "confidence": 0.4,
            "summary": "Policy analysis encountered a parsing error.",
        }

    logger.info("policy_agent_complete", compliance=result.get("policy_compliance"))
    return result
