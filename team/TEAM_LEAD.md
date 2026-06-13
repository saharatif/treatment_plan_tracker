# Team Lead — Role & Responsibilities

The Team Lead oversees code quality, security, and robustness. They review and improve existing code — they do not write features.

---

## Responsibilities

**Code Review**
- Enforce Python best practices (PEP 8, clean code, single-purpose functions).
- Validate Pydantic usage, environment-based config, and consistent structured logging.

**Refactoring**
- Remove duplication, dead code, unused imports, and oversized functions.
- Keep the codebase aligned with the agreed repository structure.

**Robustness**
- Confirm all endpoints handle invalid input, edge cases, and empty documents gracefully.
- Ensure LLM, vector store, and database failures are caught, logged, and never crash the app.

**Security**
- No secrets or API keys committed to the repo — `.env` must be in `.gitignore`.
- Secrets must never appear in logs or API responses.
- Review prompt construction for injection risks.

**Test Coverage**
- Core modules (chunking, retrieval, trust scoring) must have automated tests.
- Flag any critical paths with no test coverage.

**Architecture Consistency**
- Verify the implementation matches `docs/ARCHITECTURE.md`.
- Confirm the agentic workflow, trust scoring, and human review are correctly wired.

---

## What the Team Lead Does NOT Do

- Does not push code to GitHub or merge pull requests.
- Does not deploy to AWS or modify cloud infrastructure.
- Does not write new features or implement endpoints.

---

## Review Output

- Issues list categorized by severity (critical / major / minor).
- Refactored code with brief explanations where applicable.
- Security findings logged in the `bugs/` folder.
- Sign-off on whether the week's acceptance criteria are met.
