# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI-powered document analysis system for 3GPP standardization documents (寄書). Monorepo architecture with frontend (Next.js) and backend (FastAPI).

## Development Commands

### Backend (Python)
```bash
# IMPORTANT: Always use uv as package manager
cd backend
uv run uvicorn analyzer.main:app --reload --port 8000  # Development server
uv run ruff format src/                                 # Format code
uv run ruff check src/                                  # Lint
uv run pytest                                           # Run tests
```

### Frontend (TypeScript/Next.js)
```bash
cd frontend
npm run dev      # Development server
npm run build    # Build
npm run lint     # Lint
```

## Code Standards

- Python: Ruff (line-length=100, rules: E, F, I, N, W), Python 3.12+
- TypeScript: Strict mode, ESLint with Next.js config
- Format code before committing

## Architecture Principles

1. **RAG Abstraction**: Analysis code depends on `EvidenceProvider` interface, NOT on RAG implementation details. RAG backend is swappable (Firestore, Dify, LangGraph, Elastic).

2. **Tool Security**: Internal tools must NOT be exposed as standalone public APIs:
   - Internal (used only within backend services): FTP access, ZIP extraction, doc→docx conversion, embedding, DB operations
   - Public-facing: Analysis APIs, document listing, downloads
   - Note: Authenticated endpoints (e.g. `/process`) may invoke internal tools as part of their pipeline

3. **Evidence Traceability**: All analysis results MUST include citations with contribution_number, clause_number, page_number, and relevance score.

4. **Normalization Priority**: docx is the canonical format. All other formats (doc, potentially PDF) are converted before processing.

## Key Documentation

- `docs/architecture.md` - System design and layer responsibilities
- `docs/requirements.md` - Functional specs and 3-phase roadmap
- `docs/data-model.md` - Schema definitions (Document, Chunk, Evidence, AnalysisResult)
- `docs/api.md` - API specifications
- `docs/tech-stack.md` - Technology choices and versions

## Infrastructure

- Database: Firestore (NoSQL + Vector Search)
- Storage: **Cloud Storage (GCS)** - Direct access via google-cloud-storage SDK
- Auth: Firebase Auth
- LLM: Google Vertex AI (Gemini)
- Deployment: Cloud Run (backend), Firebase App Hosting (frontend)
- Local dev: Firebase Emulator Suite (port 4000 for UI)

## Critical Notes

### Storage Architecture (IMPORTANT)

**This project uses Cloud Storage (GCS) directly, NOT Firebase Storage:**

- **Access method**: Backend uses `google-cloud-storage` SDK for direct GCS access
- **Access control**: Implemented in backend API with user approval checks (see `analyzer.auth.get_current_user`)
- **File sharing**: Backend generates signed URLs with expiration for frontend access
- **Storage Rules**: `storage.rules` file exists but is NOT used (Firebase Storage is not enabled in `firebase.json`)

**DO NOT:**
- ❌ Deploy storage.rules with `firebase deploy --only storage` (Firebase Storage is not configured)
- ❌ Implement access control in storage.rules (won't be applied)
- ❌ Assume Firebase Storage SDK is used in frontend

**DO:**
- ✅ Implement access control in backend API endpoints
- ✅ Use `CurrentUserDep` for approval checks in all protected endpoints
- ✅ Generate signed URLs for temporary file access

### gcloud Environment Variables (IMPORTANT)

**When updating Cloud Run environment variables:**

```bash
# ❌ WRONG - Overwrites all existing variables
gcloud run services update SERVICE_NAME --set-env-vars "NEW_VAR=value"

# ✅ CORRECT - Updates only specified variables
gcloud run services update SERVICE_NAME --update-env-vars "NEW_VAR=value"

# ✅ CORRECT - Sets all variables at once (if you have the complete list)
gcloud run services update SERVICE_NAME --set-env-vars "VAR1=val1,VAR2=val2,VAR3=val3"
```

**Always verify after update:**
```bash
gcloud run services describe SERVICE_NAME --region REGION --format="yaml" | grep -A 20 "env:"
```

**Current required environment variables for gpp-analyzer-backend:**
- DEBUG (false for production)
- CORS_ORIGINS_STR
- GCP_PROJECT_ID
- GCS_BUCKET_NAME
- USE_FIREBASE_EMULATOR
- FTP_MOCK_MODE
- VERTEX_AI_LOCATION
- ANALYSIS_MODEL
- ANALYSIS_STRATEGY_VERSION
- REVIEW_SHEET_EXPIRATION_MINUTES
- INITIAL_ADMIN_EMAILS
