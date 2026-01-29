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

2. **Tool Security**: Internal tools are NOT public APIs:
   - Private: FTP access, ZIP extraction, doc→docx conversion, embedding, DB operations
   - Public: Analysis APIs, document listing, downloads

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
- Storage: Google Cloud Storage
- Auth: Firebase Auth
- LLM: Google Vertex AI (Gemini)
- Deployment: Cloud Run (backend), Firebase App Hosting (frontend)
- Local dev: Firebase Emulator Suite (port 4000 for UI)
