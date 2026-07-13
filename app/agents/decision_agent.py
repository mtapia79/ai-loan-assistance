"""
Agents – Decision Agent

Synthesises all agent findings into a final explainable recommendation.
Also runs the compliance check before finalising.
"""

import json
from typing import Any, cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from app.mcp.tools import flag_for_compliance
from app.observability.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """\
You are the Chief Underwriting Decision Agent for a financial institution.
You synthesise findings from specialist agents to produce a final loan recommendation.

CRITICAL RULES:
1. Base decisions ONLY on creditworthiness factors (income, debt, credit history, collateral).
2. NEVER reference race, color, religion, sex, national origin, age, or any protected class.
3. Always provide a clear, specific explanation citing numerical evidence.
4. If any finding triggers manual review, recommend MANUAL_REVIEW unless approval evidence is overwhelming.

You will receive findings from:
- Credit Agent: FICO score, DTI, payment history
- Document Agent: Income/debt verification, document quality
- Policy Agent: Compliance with lending policies

Produce a final decision in structured JSON:
{
  "recommendation": "APPROVE|REJECT|MANUAL_REVIEW",
  "confidence_score": float (0.0–1.0),
  "explanation": str (2–4 sentences, human-readable),
  "key_factors_for": [str],
  "key_factors_against": [str],
  "conditions": [str],
  "next_steps": [str]
}
"""


async def run_decision_agent(
    application_summary: dict,
    credit_findings: dict,
    document_findings: dict,
    policy_findings: dict,
    llm: ChatOpenAI,
) -> dict:
    """
    Execute the final decision agent.

    Args:
        application_summary: Core application data.
        credit_findings: Output from the credit agent.
        document_findings: Output from the document agent.
        policy_findings: Output from the policy agent.
        llm: Configured ChatOpenAI instance.

    Returns:
        Final decision dict with recommendation, explanation, and reasoning.
    """
    logger.info("decision_agent_start")

    user_content = f"""
APPLICATION
===========
{json.dumps(application_summary, indent=2)}

CREDIT AGENT FINDINGS
=====================
{json.dumps({k: v for k, v in credit_findings.items() if not k.startswith('_')}, indent=2)}

DOCUMENT AGENT FINDINGS
=======================
{json.dumps({k: v for k, v in document_findings.items() if not k.startswith('_')}, indent=2)}

POLICY AGENT FINDINGS
=====================
{json.dumps(policy_findings, indent=2)}

Please synthesise these findings and produce the final loan decision.
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
            "recommendation": "MANUAL_REVIEW",
            "confidence_score": 0.3,
            "explanation": "Decision synthesis encountered an error. Manual review required.",
            "key_factors_for": [],
            "key_factors_against": ["system_error"],
            "conditions": [],
            "next_steps": ["Manual underwriter review required"],
        }

    # Run compliance gate
    compliance = cast(
        dict[str, Any],
        cast(BaseTool, flag_for_compliance).invoke(
            {
                "recommendation": result.get("recommendation", "MANUAL_REVIEW"),
                "reasoning": result.get("explanation", ""),
                "loan_purpose": application_summary.get("loan_purpose", ""),
            }
        ),
    )

    if compliance.get("override_recommendation"):
        logger.warning(
            "compliance_override",
            flags=compliance.get("flags"),
            original=result.get("recommendation"),
        )
        result["recommendation"] = "MANUAL_REVIEW"
        result["confidence_score"] = min(result.get("confidence_score", 0.5), 0.5)
        result["key_factors_against"] = result.get("key_factors_against", []) + compliance.get(
            "flags", []
        )
        result["next_steps"] = ["ESCALATED_TO_COMPLIANCE"] + result.get("next_steps", [])

    result["_compliance"] = compliance
    logger.info(
        "decision_agent_complete",
        recommendation=result.get("recommendation"),
        confidence=result.get("confidence_score"),
    )
    return result
