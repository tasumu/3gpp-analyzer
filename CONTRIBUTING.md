# Contributing to 3GPP Analyzer

Thank you for your interest in contributing to 3GPP Analyzer!

## Development Setup

### Prerequisites

- Python 3.12 or higher
- Node.js 18 or higher
- uv (Python package manager)
- Firebase CLI
- A GCP project with the following APIs enabled:
  - Cloud Run, Cloud Storage, Firestore, Vertex AI

### Initial Setup

1. Fork the repository
2. Clone your fork
3. Copy `.env.example` to `.env` and configure
4. Copy `.firebaserc.example` to `.firebaserc` and set your project ID

### Backend Development

```bash
cd backend
uv sync                      # Install dependencies
uv run uvicorn analyzer.main:app --reload --port 8000
```

### Frontend Development

```bash
cd frontend
npm install
npm run dev
```

### Running Tests

```bash
# Backend
cd backend
uv run pytest

# Frontend
cd frontend
npm test
```

### Code Quality

Before submitting a PR, ensure:

```bash
# Backend: Format and lint
cd backend
uv run ruff format src/
uv run ruff check src/

# Frontend: Lint
cd frontend
npm run lint
```

## Coding Standards

### Python

- Use Ruff for formatting and linting
- Line length: 100 characters
- Follow PEP 8 naming conventions
- Type hints are required
- Docstrings for public APIs

### TypeScript

- Strict mode enabled
- ESLint with Next.js config
- Use functional components with hooks
- Type all props and state

## Architecture Principles

Please read [docs/architecture.md](docs/architecture.md) before making significant changes.

Key principles:

1. **RAG Abstraction**: Analysis code should depend on `EvidenceProvider` interface, NOT on RAG implementation
2. **Tool Security**: Internal tools (FTP, conversion, embedding) are NOT public APIs
3. **Evidence Traceability**: All analysis results MUST include citations
4. **Normalization Priority**: docx is canonical format

## Pull Request Process

1. Create a feature branch from `main`
2. Make your changes with clear commit messages
3. Ensure all tests pass
4. Run formatters and linters
5. Update documentation if needed
6. Submit a PR with:
   - Clear description of changes
   - Reference to related issues
   - Test plan or evidence

## Commit Message Guidelines

Follow conventional commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Maintenance tasks

Examples:
- `feat: add multi-document comparison API`
- `fix: correct rate limiter exception handler setup`
- `docs: update deployment guide for GCS usage`

## Code Review

All contributions require code review. Reviewers will check:

- Code quality and style
- Test coverage
- Documentation completeness
- Architecture compliance
- Security considerations

## Questions?

- Open an issue for bugs or feature requests
- Tag with appropriate labels
- Be respectful and constructive

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
