-- Initialize PostgreSQL extensions and schemas for ERP AI Copilot
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS erp;
CREATE SCHEMA IF NOT EXISTS ai;

-- RAG Indexes Reference (Vector HNSW & Full-Text Search GIN):
-- Note: These indexes are declared directly in SQLAlchemy ORM (app/rag/models.py)
-- and automatically ensured whenever running `python scripts/seed_demo_data.py`:
--
-- 1. HNSW index for Dense Vector Search (cosine ops, dim 1536):
-- CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
--   ON ai.document_chunks USING hnsw (embedding vector_cosine_ops);
--
-- 2. GIN index for Sparse Keyword Full-Text Search:
-- CREATE INDEX IF NOT EXISTS idx_document_chunks_fts 
--   ON ai.document_chunks USING gin (to_tsvector('simple', content));
--
-- 3. B-Tree indexes for Pre-ranking Access Control (ACL):
-- CREATE INDEX IF NOT EXISTS idx_documents_access_scope 
--   ON ai.documents (access_scope);
-- CREATE INDEX IF NOT EXISTS idx_documents_owner_id 
--   ON ai.documents (owner_id);
