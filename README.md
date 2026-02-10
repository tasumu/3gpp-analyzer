# 3GPP Analyzer

AI-powered document analysis system for 3GPP standardization documents (寄書).

## Overview

This system provides intelligent analysis capabilities for 3GPP Technical Documents (TDocs), including:

- Document processing and normalization (doc/docx/zip support)
- RAG (Retrieval-Augmented Generation) powered Q&A
- Contribution comparison and analysis
- Review sheet generation
- FTP synchronization with 3GPP servers

## Architecture

- **Frontend**: Next.js (TypeScript, React)
- **Backend**: FastAPI (Python 3.12+)
- **Database**: Firestore (NoSQL + Vector Search)
- **Storage**: Cloud Storage (GCS)
- **LLM**: Google Vertex AI (Gemini)
- **Auth**: Firebase Authentication

For detailed architecture, see [docs/architecture.md](docs/architecture.md).

## Key Features

### RAG Abstraction

Analysis code depends on `EvidenceProvider` interface, NOT on RAG implementation details. RAG backend is swappable (Firestore, Dify, LangGraph, Elasticsearch).

### Security

- Internal tools (FTP, document conversion, embedding) are NOT public APIs
- All analysis results include citations with traceability
- User approval flow with admin management
- Rate limiting and logging with sensitive data masking

### Document Normalization

All documents are normalized to `.docx` format before processing. This enables consistent chunking and analysis regardless of the original format.

## Project Structure

```
3gpp-analyzer/
├── frontend/          # Next.js application
├── backend/           # FastAPI application
├── docs/              # Documentation
├── firebase.json      # Firebase configuration
├── firestore.rules    # Firestore security rules
└── firestore.indexes.json
```

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- uv (Python package manager)
- Firebase CLI
- GCP project with required APIs enabled

### Local Development

See [docs/deployment.md](docs/deployment.md) for detailed setup instructions.

#### Backend

```bash
cd backend
uv sync
uv run uvicorn analyzer.main:app --reload --port 8000
```

#### Frontend

```bash
cd frontend
npm install
npm run dev
```

#### Firebase Emulators

```bash
# Start emulators for Firestore, Auth, and Storage
firebase emulators:start
```

## Documentation

- [Requirements](docs/requirements.md) - Functional specs and roadmap
- [Architecture](docs/architecture.md) - System design and layer responsibilities
- [Data Model](docs/data-model.md) - Schema definitions
- [API Specification](docs/api.md) - API documentation
- [Tech Stack](docs/tech-stack.md) - Technology choices
- [Deployment](docs/deployment.md) - Deployment guide
- [CLAUDE.md](CLAUDE.md) - Instructions for Claude Code AI assistant

## Code Standards

- **Python**: Ruff (line-length=100), Python 3.12+
- **TypeScript**: Strict mode, ESLint with Next.js config
- Format code before committing

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Security

This project implements comprehensive security measures:

- Firebase Authentication with user approval flow
- Rate limiting on all API endpoints
- Sensitive data masking in logs
- CORS configuration
- Security headers (CSP, HSTS, etc.)

For security concerns, please open an issue or contact the maintainers.
