-- ============================================================
-- Initial schema bootstrap for AI Loan Assistance
-- Run via: make migrate  (Alembic manages versioning)
-- ============================================================

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
