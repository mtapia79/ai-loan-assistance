"""
Agents – Document Analysis Agent

Extracts and validates financial data from uploaded documents.
"""

import json
from typing import Any, cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from app.mcp.tools import extract_document_data
from app.observability.logging import get_logger

logger = get_logger(__name__)

_SYSTEM_PROMPT = """\
You are a Document Analysis Agent for a financial institution.
Your job is to review extracted financial document data and assess its completeness
and consistency with the stated application figures.

You will receive:
- Applicant-stated income and debt figures
- Extracted data from uploaded financial documents

Identify any discrepancies and assess document quality.
Respond in structured JSON:
{
  "documents_reviewed": int,
  "income_verified": bool,
  "income_discrepancy_pct": float,
  "debt_verified": bool,
  "debt_discrepancy_pct": float,
  "documentation_quality": "COMPLETE|PARTIAL|INSUFFICIENT",
  "flags": [str],
  "confidence": float,
  "summary": str
}
"""


async def run_document_agent(
    annual_income: float,
    monthly_debt: float,
    document_texts: list[str],
    llm: ChatOpenAI,
) -> dict:
    """
    Execute the document analysis agent.

    Args:
        annual_income: Applicant-stated annual income.
        monthly_debt: Applicant-stated monthly debt.
        document_texts: Raw text from uploaded documents.
        llm: Configured ChatOpenAI instance.

    Returns:
        Structured document analysis result dict.
    """
    logger.info("document_agent_start", doc_count=len(document_texts))

    if not document_texts:
        return {
            "documents_reviewed": 0,
            "income_verified": False,
            "income_discrepancy_pct": 0.0,
            "debt_verified": False,
            "debt_discrepancy_pct": 0.0,
            "documentation_quality": "INSUFFICIENT",
            "flags": ["no_documents_provided"],
            "confidence": 0.3,
            "summary": "No financial documents were provided for verification.",
        }

    # Extract data from each document
    extractions: list[dict[str, Any]] = []
    for doc_text in document_texts:
        extracted = cast(
            dict[str, Any],
            cast(BaseTool, extract_document_data).invoke({"document_text": doc_text}),
        )
        extractions.append(extracted)

    user_content = f"""
Stated Annual Income: ${annual_income:,.2f}
Stated Monthly Debt: ${monthly_debt:,.2f}

Document Extractions:
{json.dumps(extractions, indent=2)}

Please assess document quality and identify any discrepancies.
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
            "documents_reviewed": len(document_texts),
            "income_verified": False,
            "income_discrepancy_pct": 0.0,
            "debt_verified": False,
            "debt_discrepancy_pct": 0.0,
            "documentation_quality": "PARTIAL",
            "flags": ["parse_error"],
            "confidence": 0.4,
            "summary": "Document analysis encountered a parsing error.",
        }

    result["_raw_extractions"] = extractions
    logger.info("document_agent_complete", quality=result.get("documentation_quality"))
    return result
