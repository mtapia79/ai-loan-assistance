"""
Database – Seed Data Generator

Generates sample data for development and testing.
Production-quality implementation with realistic data.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from uuid import uuid4

from app.config import get_settings
from app.db.models import Customer, LoanApplication, PolicyDocument, AuditLog
from app.db.session import session_context
from app.db.unit_of_work import UnitOfWork

logger = logging.getLogger(__name__)


async def seed_customers(uow: UnitOfWork, count: int = 10) -> list[str]:
    """
    Create sample customers.

    Args:
        uow: Unit of Work instance
        count: Number of customers to create

    Returns:
        List of created customer IDs
    """
    customer_ids = []

    first_names = [
        "John", "Jane", "Michael", "Sarah", "David",
        "Emma", "James", "Olivia", "Robert", "Sophia"
    ]
    last_names = [
        "Smith", "Johnson", "Williams", "Brown", "Jones",
        "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"
    ]
    cities = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix"]
    states = ["NY", "CA", "IL", "TX", "AZ"]
    industries = [
        "Technology", "Finance", "Healthcare", "Manufacturing",
        "Retail", "Education", "Transportation", "Construction"
    ]

    for i in range(count):
        first_name = first_names[i % len(first_names)]
        last_name = last_names[i % len(last_names)]
        email = f"{first_name.lower()}.{last_name.lower()}{i}@example.com"

        customer = await uow.customers.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=f"+1-555-{100+i:03d}-{i:04d}",
            date_of_birth=datetime.now() - timedelta(days=365 * (25 + i)),
            street_address=f"{100 + i} Main Street",
            city=cities[i % len(cities)],
            state=states[i % len(states)],
            postal_code=f"{10000 + i:05d}",
            country="US",
            kyc_status="VERIFIED" if i % 3 != 0 else "PENDING",
            kyc_verified_at=datetime.now() if i % 3 != 0 else None,
            annual_income=50000 + (i * 5000),
            credit_score=650 + (i * 5),
            employment_status="EMPLOYED",
            employment_industry=industries[i % len(industries)],
        )
        customer_ids.append(str(customer.id))
        logger.info(f"Created customer: {email}")

    return customer_ids


async def seed_loan_applications(uow: UnitOfWork, customer_ids: list[str], count_per_customer: int = 2) -> list[str]:
    """
    Create sample loan applications.

    Args:
        uow: Unit of Work instance
        customer_ids: List of customer IDs to create applications for
        count_per_customer: Number of applications per customer

    Returns:
        List of created application IDs
    """
    application_ids = []
    statuses = ["PENDING", "PROCESSING", "COMPLETED", "FAILED"]
    recommendations = ["APPROVE", "REJECT", "MANUAL_REVIEW"]
    purposes = [
        "Home Purchase", "Vehicle Purchase", "Debt Consolidation",
        "Business Expansion", "Education", "Medical Expenses", "Home Improvement"
    ]

    for cust_idx, customer_id in enumerate(customer_ids):
        for app_idx in range(count_per_customer):
            customer = await uow.customers.get_by_id(customer_id)
            if not customer:
                continue

            application = await uow.loans.create(
                customer_id=customer_id,
                applicant_name=f"{customer.first_name} {customer.last_name}",
                applicant_email=customer.email,
                annual_income=customer.annual_income or 75000,
                monthly_debt=500 + (app_idx * 100),
                requested_amount=50000 + (app_idx * 10000),
                loan_purpose=purposes[(cust_idx + app_idx) % len(purposes)],
                credit_score=customer.credit_score or 700,
                recommendation=recommendations[(cust_idx + app_idx) % len(recommendations)] if app_idx % 2 == 0 else None,
                confidence_score=0.85 + (app_idx * 0.05) if app_idx % 2 == 0 else None,
                explanation="Application reviewed by automated underwriting system" if app_idx % 2 == 0 else None,
                agent_reasoning={"score": 0.85 + (app_idx * 0.05), "factors": ["income", "credit_score"]} if app_idx % 2 == 0 else None,
                status=statuses[app_idx % len(statuses)],
            )
            application_ids.append(str(application.id))
            logger.info(f"Created loan application: {application.id} for customer {customer_id}")

    return application_ids


async def seed_audit_logs(uow: UnitOfWork, application_ids: list[str]) -> None:
    """
    Create sample audit logs.

    Args:
        uow: Unit of Work instance
        application_ids: List of application IDs to create audit logs for
    """
    agents = ["credit_assessment", "document_verification", "policy_engine", "decision_maker"]
    actions = [
        "Application received",
        "Credit score evaluated",
        "Income verified",
        "Policy check completed",
        "Recommendation issued",
        "Manual review requested",
        "Application approved",
        "Application rejected",
    ]

    for app_idx, application_id in enumerate(application_ids):
        # Create 2-4 audit logs per application
        log_count = 2 + (app_idx % 3)
        for log_idx in range(log_count):
            audit_log = await uow.audits.log_action(
                application_id=application_id,
                agent_name=agents[(app_idx + log_idx) % len(agents)],
                action=actions[(app_idx + log_idx) % len(actions)],
                details={
                    "step": log_idx + 1,
                    "status": "completed",
                    "duration_ms": 100 + (log_idx * 50),
                },
                trace_id=f"trace-{uuid4()}",
                span_id=f"span-{uuid4()}",
            )
            logger.info(f"Created audit log: {audit_log.id}")


async def seed_policies(uow: UnitOfWork) -> None:
    """
    Create sample policy documents.

    Args:
        uow: Unit of Work instance
    """
    policies = [
        {
            "title": "Income Verification Policy",
            "content": """
            Income Verification Policy
            
            1. Acceptable Income Documentation
               - Recent pay stubs (last 2 months)
               - W-2 forms (last 2 years)
               - Tax returns (last 2 years)
               - Bank statements (last 3 months)
            
            2. Income Calculation
               - Use average of last 24 months
               - Exclude one-time bonuses
               - Include overtime as average of last 12 months
            
            3. Self-Employment Income
               - Use average net income from last 2 years
               - Require business tax returns
               - May require personal tax returns
            """,
        },
        {
            "title": "Credit Score Requirements",
            "content": """
            Credit Score Policy
            
            1. Minimum Credit Scores
               - Excellent (750+): Approved at lower rates
               - Good (700-749): Standard approval
               - Fair (650-699): Requires manual review
               - Poor (below 650): Additional documentation required
            
            2. Credit Report Analysis
               - Review all accounts on file
               - Assess payment history
               - Evaluate credit utilization
               - Consider recent inquiries
            
            3. Adverse Items
               - Evaluate bankruptcy (must be 2+ years old)
               - Consider late payments (weight by recency)
               - Review charge-offs and collections
            """,
        },
        {
            "title": "Debt-to-Income Ratio Policy",
            "content": """
            Debt-to-Income Ratio (DTI) Policy
            
            1. Calculation Method
               - Total monthly debt payments / gross monthly income
               - Include: Credit cards, car loans, student loans, proposed loan
               - Maximum acceptable DTI: 43%
            
            2. Special Cases
               - Compensating factors may allow up to 50% DTI
               - Large reserves may allow higher DTI
               - Significant income increase expected documented
            
            3. Debt Classification
               - Mortgage payments: Include principal, interest, taxes, insurance
               - Auto loans: Include full payment
               - Student loans: Use documented payment amount
               - Credit cards: Use higher of 2% of balance or minimum payment
            """,
        },
        {
            "title": "Employment Verification Policy",
            "content": """
            Employment Verification Policy
            
            1. Verification Methods
               - Direct employer verification letter
               - Verification of Employment (VOE) form
               - Recent pay stubs
               - Tax returns for self-employed
            
            2. Employment History
               - Require 2 years employment history
               - Same employer required for last 2 years
               - Current job tenure: minimum 90 days
            
            3. Job Changes
               - Career progression in same field acceptable
               - Lateral moves acceptable
               - Significant career changes require additional documentation
            """,
        },
        {
            "title": "Loan Amount Guidelines",
            "content": """
            Loan Amount Policy
            
            1. Loan-to-Value (LTV) Ratio
               - Maximum LTV: 95%
               - LTV Calculation: Loan amount / Property value
               - Higher LTV requires additional compensation
            
            2. Loan Amount Limits
               - Conventional loans: Up to $1,000,000
               - Jumbo loans: $1,000,001 and above
               - FHA loans: $431,200 (varies by county)
            
            3. Requested Amount Validation
               - Must align with stated loan purpose
               - Cannot exceed property value
               - Verify all funds accounted for
            """,
        },
    ]

    for idx, policy_data in enumerate(policies):
        policy = await uow.policies.create(
            title=policy_data["title"],
            content=policy_data["content"],
            chunk_index=0,
            metadata_={"version": "1.0", "category": "lending", "effective_date": "2026-01-01"},
        )
        logger.info(f"Created policy document: {policy.id}")


async def main() -> None:
    """Main seed function."""
    settings = get_settings()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info(f"Starting seed data generation for environment: {settings.app_env}")

    try:
        async with session_context() as session:
            async with UnitOfWork(session) as uow:
                # Seed customers
                logger.info("Seeding customers...")
                customer_ids = await seed_customers(uow, count=10)
                await uow.commit()
                logger.info(f"Created {len(customer_ids)} customers")

                # Seed loan applications
                logger.info("Seeding loan applications...")
                application_ids = await seed_loan_applications(
                    uow, customer_ids, count_per_customer=2
                )
                await uow.commit()
                logger.info(f"Created {len(application_ids)} loan applications")

                # Seed audit logs
                logger.info("Seeding audit logs...")
                await seed_audit_logs(uow, application_ids)
                await uow.commit()
                logger.info(f"Created audit logs for {len(application_ids)} applications")

                # Seed policies
                logger.info("Seeding policy documents...")
                await seed_policies(uow)
                await uow.commit()
                logger.info("Created policy documents")

        logger.info("✓ Seed data generation completed successfully!")

    except Exception as e:
        logger.error(f"✗ Seed data generation failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
