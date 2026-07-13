# Enterprise AI Loan Decision Assistant

> **HPE Principal AI Architect Interview Demo**
> Demonstrates senior/staff-level AI engineering across architecture, implementation, scalability, security, and AI engineering best practices.

---

## Architecture Overview

```
                         ┌─────────────────────────────────────┐
                         │          FastAPI Application         │
                         │                                     │
    Client ──────────────►  POST /api/v1/loans/analyze         │
                         │         │                           │
                         │  ┌──────▼──────────────────────┐   │
                         │  │    Input Guardrails          │   │
                         │  │  (PII detection, validation) │   │
                         │  └──────┬──────────────────────┘   │
                         │         │                           │
                         │  ┌──────▼──────────────────────────┐│
                         │  │  LangGraph Orchestrator          ││
                         │  │                                  ││
                         │  │  ┌──────────────────────────┐   ││
                         │  │  │ CreditAgent               │   ││
                         │  │  │  • get_credit_report(MCP)│   ││
                         │  │  │  • calculate_dti(MCP)    │   ││
                         │  │  └──────────┬───────────────┘   ││
                         │  │             │                    ││
                         │  │  ┌──────────▼───────────────┐   ││
                         │  │  │ DocumentAgent             │   ││
                         │  │  │  • extract_document(MCP) │   ││
                         │  │  └──────────┬───────────────┘   ││
                         │  │             │                    ││
                         │  │  ┌──────────▼───────────────┐   ││
                         │  │  │ PolicyAgent (RAG)         │   ││
                         │  │  │  • pgvector search        │   ││
                         │  │  │  • Retrieves policy docs  │   ││
                         │  │  └──────────┬───────────────┘   ││
                         │  │             │                    ││
                         │  │  ┌──────────▼───────────────┐   ││
                         │  │  │ DecisionAgent             │   ││
                         │  │  │  • Synthesises findings   │   ││
                         │  │  │  • flag_for_compliance    │   ││
                         │  │  │  • APPROVE/REJECT/REVIEW  │   ││
                         │  │  └──────────────────────────┘   ││
                         │  └─────────────────────────────────┘│
                         │         │                           │
                         │  ┌──────▼──────────────────────┐   │
                         │  │   Output Guardrails          │   │
                         │  │  (Bias detection, structure) │   │
                         │  └──────┬──────────────────────┘   │
                         │         │                           │
    Client ◄─────────────│  LoanDecisionResponse              │
                         │  (explainable, auditable)          │
                         └─────────────────────────────────────┘
                                   │
                     ┌─────────────┼──────────────┐
                     ▼             ▼              ▼
              PostgreSQL      pgvector         OpenTelemetry
              (audit logs)    (policies)       → Jaeger / AWS X-Ray
```

---

## Technology Stack

| Concern | Technology |
|---|---|
| API Framework | FastAPI + uvicorn |
| Language | Python 3.11+ |
| Agent Orchestration | LangGraph (directed state graph) |
| LLM | OpenAI GPT-4o |
| Tool Protocol | MCP (Model Context Protocol) |
| RAG | pgvector cosine similarity |
| Database | PostgreSQL 16 |
| Vector Store | pgvector extension |
| ORM | SQLAlchemy 2.0 async |
| Observability | OpenTelemetry SDK + Jaeger |
| Logging | structlog (JSON in prod, colorized in dev) |
| Configuration | pydantic-settings |
| Containerization | Docker multi-stage build |
| Orchestration | Kubernetes (EKS-ready) |
| Cloud | AWS deployment readiness |
| Testing | pytest + pytest-asyncio |

---

## Project Structure

```
ai-loan-assistance/
├── app/
│   ├── main.py                     # FastAPI entry point + lifespan
│   ├── config.py                   # pydantic-settings configuration
│   ├── api/
│   │   ├── routes/
│   │   │   ├── loans.py            # POST /api/v1/loans/analyze
│   │   │   └── health.py           # GET /health, /health/ready
│   │   └── middleware/
│   │       └── logging.py          # Request/response logging middleware
│   ├── agents/
│   │   ├── orchestrator.py         # LangGraph multi-agent workflow
│   │   ├── credit_agent.py         # FICO + DTI analysis
│   │   ├── document_agent.py       # Financial document extraction
│   │   ├── policy_agent.py         # RAG policy compliance checker
│   │   └── decision_agent.py       # Final recommendation + compliance gate
│   ├── mcp/
│   │   └── tools.py                # MCP tool definitions (5 tools)
│   ├── rag/
│   │   ├── embeddings.py           # OpenAI / Mock embedding service
│   │   ├── retriever.py            # pgvector cosine similarity retriever
│   │   └── ingestion.py            # Policy document ingestion pipeline
│   ├── db/
│   │   ├── models.py               # SQLAlchemy ORM models
│   │   ├── session.py              # Async session factory
│   │   └── migrations/init.sql    # pgvector extension bootstrap
│   ├── guardrails/
│   │   └── validators.py           # Input/output/bias guardrails
│   ├── evaluation/
│   │   └── evaluator.py            # LLM response quality scorer
│   ├── observability/
│   │   ├── logging.py              # structlog configuration
│   │   └── telemetry.py            # OpenTelemetry setup
│   └── schemas/
│       └── loan.py                 # Pydantic request/response models
├── tests/
│   └── unit/
│       ├── test_guardrails.py      # Guardrail unit tests
│       ├── test_mcp_tools.py       # MCP tool unit tests
│       ├── test_evaluation.py      # Evaluator unit tests
│       ├── test_config.py          # Config validation tests
│       ├── test_api_health.py      # Health endpoint tests
│       └── test_embeddings.py     # Embedding service tests
├── k8s/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── deployment.yaml             # 2-replica deployment + HPA
│   ├── service.yaml
│   └── ingress.yaml                # AWS ALB Ingress
├── docker/
│   └── otel-collector-config.yaml
├── Dockerfile                      # Multi-stage build
├── docker-compose.yml              # Full local stack
├── pyproject.toml
├── Makefile
└── .env.example
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Docker + Docker Compose
- OpenAI API key

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

### 2. Start the full stack (recommended)

```bash
make up        # starts app, postgres (pgvector), otelcol, jaeger
make migrate   # run alembic migrations
make seed      # ingest lending policies into pgvector
```

Visit:
- API: http://localhost:8000/docs
- Jaeger UI: http://localhost:16686

### 3. Submit a loan application

```bash
curl -X POST http://localhost:8000/api/v1/loans/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "applicant_name": "Jane Doe",
    "applicant_email": "jane.doe@example.com",
    "annual_income": 95000,
    "monthly_debt": 1200,
    "requested_amount": 350000,
    "loan_purpose": "home_purchase",
    "credit_score": 740
  }'
```

**Example response:**
```json
{
  "application_id": "550e8400-e29b-41d4-a716-446655440000",
  "recommendation": "APPROVE",
  "confidence_score": 0.87,
  "explanation": "The applicant has a strong FICO score of 740 and a DTI of 15.2%, well within the 43% conventional loan guideline. Income and documentation are consistent. Approved subject to standard conditions.",
  "debt_to_income_ratio": 0.152,
  "agent_steps": [
    {"agent": "CreditAgent", "finding": "FICO 740 | DTI 15.2% | Risk: EXCELLENT", "confidence": 0.92},
    {"agent": "DocumentAgent", "finding": "Documentation quality: PARTIAL | Income verified: false", "confidence": 0.5},
    {"agent": "PolicyAgent", "finding": "Policy compliance: COMPLIANT | Manual triggers: 0", "confidence": 0.88},
    {"agent": "DecisionAgent", "finding": "Strong credit profile...", "confidence": 0.87}
  ],
  "processing_time_ms": 3421,
  "model_used": "gpt-4o"
}
```

---

## Architecture Decisions

### Multi-Agent with LangGraph
The workflow is a directed acyclic graph (DAG). Each agent node is an async function that enriches shared `LoanState`. LangGraph handles state management, error isolation, and makes the flow inspectable/debuggable.

### RAG with pgvector
Lending policies are chunked, embedded (OpenAI text-embedding-3-small), and stored in PostgreSQL with the pgvector extension. At query time, cosine similarity search returns the most relevant policy excerpts, giving the PolicyAgent grounded context instead of relying on training data.

### MCP Tool Protocol
Five tools are registered as LangChain tools and follow the Model Context Protocol interface: `get_credit_report`, `calculate_dti`, `retrieve_policies`, `extract_document_data`, `flag_for_compliance`. In production, these would be served by a dedicated MCP server.

### Guardrails (Two Layers)
1. **Input guardrails**: PII detection (SSN, credit card, passport), range validation, loan purpose whitelist
2. **Output guardrails**: Structural validation, protected-class bias scanning, confidence bounds check

### Explainability
Every API response includes `agent_steps` — a structured trace of each agent's finding, confidence score, and supporting details. This provides a full audit trail for loan officers and regulators.

### OpenTelemetry
Every agent node is wrapped in a named OTEL span. The tracer is injected via `get_tracer()`. In development, spans are captured in-memory; in production they are exported to the OTLP collector → Jaeger/AWS X-Ray.

### AWS Deployment Readiness
- Kubernetes manifests with AWS ALB Ingress, IRSA (IAM Roles for Service Accounts), and HPA
- ECR-ready Docker image with non-root user and read-only filesystem
- Secrets managed via AWS Secrets Manager / External Secrets Operator
- WAFv2 integration on the ALB ingress

---

## Running Tests

```bash
make dev        # install dev deps
make test-unit  # unit tests only (no DB/LLM required)
make test       # full test suite
make test-cov   # with coverage report
```

---

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes (production) | OpenAI API key |
| `OPENAI_MODEL` | No | Default: `gpt-4o` |
| `POSTGRES_*` | Yes | Database connection |
| `JWT_SECRET_KEY` | Yes (production) | JWT signing secret |
| `OTEL_ENABLED` | No | Enable OTLP export (default: false) |

---

## Possible Decision Outcomes

| Outcome | Meaning |
|---|---|
| **APPROVE** | All policy criteria met; system recommends approval |
| **REJECT** | One or more hard disqualifiers present |
| **MANUAL_REVIEW** | Borderline case; human underwriter must decide |

> ⚠️ **The AI system is advisory only. All final credit decisions are made by human loan officers.**

---

## Fair Lending Compliance

The system includes multiple layers of fair-lending protection:
1. Agent prompts explicitly prohibit protected-class reasoning
2. The `flag_for_compliance` MCP tool scans all reasoning for ECOA/FHA violations
3. Output guardrails perform bias scanning before every response
4. All adverse action decisions are flagged for required adverse action notice

---

*Built to demonstrate Principal AI Engineer capabilities for the HPE technical interview.*