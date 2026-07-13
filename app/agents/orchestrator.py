"""
Agents – LangGraph Multi-Agent Orchestrator

Defines the loan analysis workflow as a directed state graph:

    START
      │
      ▼
  [credit_node]  ──────────────────────────────┐
      │                                         │
      ▼                                         │  (parallel)
  [document_node]  ────────────────────────────┤
      │                                         │
      ▼                                         │
  [policy_node]  ──────────────────────────────┘
      │
      ▼
  [decision_node]
      │
      ▼
    END

Each node is an async agent that enriches the shared LoanState.
The graph is compiled once and reused per-request (thread-safe with state injection).
"""

import time
import uuid
from typing import Any, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic.v1 import SecretStr

from app.agents.credit_agent import run_credit_agent
from app.agents.decision_agent import run_decision_agent
from app.agents.document_agent import run_document_agent
from app.agents.policy_agent import run_policy_agent
from app.observability.logging import get_logger
from app.observability.telemetry import get_tracer
from app.rag.retriever import PolicyRetriever

logger = get_logger(__name__)
tracer = get_tracer(__name__)


# ── Shared Graph State ────────────────────────────────────────────────────────


class LoanState(TypedDict):
    """Mutable state passed between all nodes in the loan analysis graph."""

    # Input
    application_id: str
    applicant_name: str
    applicant_email: str
    annual_income: float
    monthly_debt: float
    requested_amount: float
    loan_purpose: str
    credit_score: int | None
    document_texts: list[str]

    # Agent outputs (populated progressively)
    credit_findings: dict[str, Any]
    document_findings: dict[str, Any]
    policy_context: str
    policy_findings: dict[str, Any]
    decision: dict[str, Any]

    # Metadata
    errors: list[str]
    processing_start_ms: float


# ── Graph Node Functions ───────────────────────────────────────────────────────


async def credit_node(state: LoanState, llm: ChatOpenAI) -> dict:
    """Node: run credit analysis."""
    with tracer.start_as_current_span("credit_agent"):
        try:
            findings = await run_credit_agent(
                applicant_email=state["applicant_email"],
                annual_income=state["annual_income"],
                monthly_debt=state["monthly_debt"],
                credit_score=state.get("credit_score"),
                llm=llm,
            )
            return {"credit_findings": findings}
        except Exception as exc:  # noqa: BLE001
            logger.error("credit_node_error", error=str(exc))
            return {
                "credit_findings": {
                    "error": str(exc),
                    "preliminary_recommendation": "MANUAL_REVIEW",
                    "confidence": 0.0,
                },
                "errors": state.get("errors", []) + [f"credit_agent: {exc}"],
            }


async def document_node(state: LoanState, llm: ChatOpenAI) -> dict:
    """Node: run document analysis."""
    with tracer.start_as_current_span("document_agent"):
        try:
            findings = await run_document_agent(
                annual_income=state["annual_income"],
                monthly_debt=state["monthly_debt"],
                document_texts=state.get("document_texts", []),
                llm=llm,
            )
            return {"document_findings": findings}
        except Exception as exc:  # noqa: BLE001
            logger.error("document_node_error", error=str(exc))
            return {
                "document_findings": {
                    "error": str(exc),
                    "documentation_quality": "INSUFFICIENT",
                    "confidence": 0.0,
                },
                "errors": state.get("errors", []) + [f"document_agent: {exc}"],
            }


async def policy_retrieval_node(state: LoanState, db_session: Any) -> dict:
    """Node: retrieve relevant policies from pgvector."""
    with tracer.start_as_current_span("policy_retrieval"):
        if db_session is None:
            return {
                "policy_context": (
                    "Standard guidelines: DTI ≤43%, credit score ≥620 for conventional. "
                    "FHA allows DTI ≤50%, score ≥580. Manual review for borderline cases."
                )
            }
        try:
            monthly_income = state["annual_income"] / 12
            dti = (state["monthly_debt"] / monthly_income) * 100
            query = (
                f"Loan application: {state['loan_purpose']} loan, "
                f"${state['requested_amount']:,.0f}, DTI {dti:.1f}%, "
                f"credit score {state.get('credit_score', 'unknown')}. "
                f"What are the applicable lending policies?"
            )
            retriever = PolicyRetriever(session=db_session)
            chunks = await retriever.retrieve(query)
            context = retriever.format_context(chunks)
            return {"policy_context": context}
        except Exception as exc:  # noqa: BLE001
            logger.error("policy_retrieval_error", error=str(exc))
            return {
                "policy_context": "Policy retrieval unavailable. Using default guidelines.",
                "errors": state.get("errors", []) + [f"policy_retrieval: {exc}"],
            }


async def policy_analysis_node(state: LoanState, llm: ChatOpenAI) -> dict:
    """Node: apply policies to the application."""
    with tracer.start_as_current_span("policy_agent"):
        try:
            findings = await run_policy_agent(
                annual_income=state["annual_income"],
                monthly_debt=state["monthly_debt"],
                requested_amount=state["requested_amount"],
                credit_score=state.get("credit_score"),
                loan_purpose=state["loan_purpose"],
                policy_context=state.get("policy_context", ""),
                llm=llm,
            )
            return {"policy_findings": findings}
        except Exception as exc:  # noqa: BLE001
            logger.error("policy_analysis_error", error=str(exc))
            return {
                "policy_findings": {
                    "policy_compliance": "BORDERLINE",
                    "confidence": 0.0,
                    "error": str(exc),
                },
                "errors": state.get("errors", []) + [f"policy_agent: {exc}"],
            }


async def decision_node(state: LoanState, llm: ChatOpenAI) -> dict:
    """Node: produce final decision."""
    with tracer.start_as_current_span("decision_agent"):
        try:
            application_summary = {
                "application_id": state["application_id"],
                "applicant_name": state["applicant_name"],
                "annual_income": state["annual_income"],
                "monthly_debt": state["monthly_debt"],
                "requested_amount": state["requested_amount"],
                "loan_purpose": state["loan_purpose"],
            }
            decision = await run_decision_agent(
                application_summary=application_summary,
                credit_findings=state.get("credit_findings", {}),
                document_findings=state.get("document_findings", {}),
                policy_findings=state.get("policy_findings", {}),
                llm=llm,
            )
            return {"decision": decision}
        except Exception as exc:  # noqa: BLE001
            logger.error("decision_node_error", error=str(exc))
            return {
                "decision": {
                    "recommendation": "MANUAL_REVIEW",
                    "confidence_score": 0.0,
                    "explanation": f"Decision agent error: {exc}. Manual review required.",
                },
                "errors": state.get("errors", []) + [f"decision_agent: {exc}"],
            }


# ── Graph Builder ──────────────────────────────────────────────────────────────


def build_loan_graph(llm: ChatOpenAI, db_session: Any = None):  # type: ignore[return]
    """
    Compile the LangGraph loan analysis workflow.

    The graph runs credit and document analysis sequentially (to demonstrate
    graph structure), then retrieves policies, applies them, and produces
    the final decision.

    Args:
        llm: Shared ChatOpenAI instance.
        db_session: Optional async DB session for RAG retrieval.

    Returns:
        Compiled LangGraph StateGraph.
    """
    builder = StateGraph(LoanState)

    # Register nodes with injected dependencies via closures
    builder.add_node("credit", lambda s: credit_node(s, llm))
    builder.add_node("documents", lambda s: document_node(s, llm))
    builder.add_node("policy_retrieval", lambda s: policy_retrieval_node(s, db_session))
    builder.add_node("policy_analysis", lambda s: policy_analysis_node(s, llm))
    builder.add_node("decision", lambda s: decision_node(s, llm))

    # Define edges (sequential pipeline)
    builder.add_edge(START, "credit")
    builder.add_edge("credit", "documents")
    builder.add_edge("documents", "policy_retrieval")
    builder.add_edge("policy_retrieval", "policy_analysis")
    builder.add_edge("policy_analysis", "decision")
    builder.add_edge("decision", END)

    return builder.compile()


# ── Public Interface ───────────────────────────────────────────────────────────


async def process_loan_application(
    applicant_name: str,
    applicant_email: str,
    annual_income: float,
    monthly_debt: float,
    requested_amount: float,
    loan_purpose: str,
    credit_score: int | None = None,
    document_texts: list[str] | None = None,
    db_session: Any = None,
) -> dict[str, Any]:
    """
    Main entry point: orchestrate all agents and return the final decision.

    Args:
        applicant_name: Full name of applicant.
        applicant_email: Email used as applicant identifier.
        annual_income: Gross annual income (USD).
        monthly_debt: Total monthly debt payments (USD).
        requested_amount: Loan amount requested (USD).
        loan_purpose: Purpose category of the loan.
        credit_score: Optional FICO score.
        document_texts: Optional list of raw document text strings.
        db_session: Optional SQLAlchemy async session for RAG.

    Returns:
        Complete decision dict with all agent findings and final recommendation.
    """
    application_id = str(uuid.uuid4())
    start_ms = time.time() * 1000

    logger.info(
        "orchestration_start",
        application_id=application_id,
        loan_purpose=loan_purpose,
        requested_amount=requested_amount,
    )

    from app.config import get_settings

    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=SecretStr(settings.openai_api_key),
        temperature=0,
        max_tokens=2000,
    )

    graph = build_loan_graph(llm=llm, db_session=db_session)

    initial_state: LoanState = {
        "application_id": application_id,
        "applicant_name": applicant_name,
        "applicant_email": applicant_email,
        "annual_income": annual_income,
        "monthly_debt": monthly_debt,
        "requested_amount": requested_amount,
        "loan_purpose": loan_purpose,
        "credit_score": credit_score,
        "document_texts": document_texts or [],
        "credit_findings": {},
        "document_findings": {},
        "policy_context": "",
        "policy_findings": {},
        "decision": {},
        "errors": [],
        "processing_start_ms": start_ms,
    }

    with tracer.start_as_current_span("loan_orchestration") as span:
        span.set_attribute("application.id", application_id)
        span.set_attribute("loan.purpose", loan_purpose)

        final_state = await graph.ainvoke(initial_state)

    elapsed_ms = int(time.time() * 1000 - start_ms)

    logger.info(
        "orchestration_complete",
        application_id=application_id,
        recommendation=final_state["decision"].get("recommendation"),
        elapsed_ms=elapsed_ms,
    )

    return {
        "application_id": application_id,
        "decision": final_state["decision"],
        "credit_findings": {
            k: v for k, v in final_state["credit_findings"].items() if not k.startswith("_")
        },
        "document_findings": {
            k: v for k, v in final_state["document_findings"].items() if not k.startswith("_")
        },
        "policy_findings": final_state["policy_findings"],
        "errors": final_state.get("errors", []),
        "processing_time_ms": elapsed_ms,
    }
