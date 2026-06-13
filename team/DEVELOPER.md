# Developer — Role & Responsibilities

The Developer is responsible for writing clean, well-structured frontend and backend code. They build features according to the weekly deliverables, self-review before handoff, and keep the codebase secure at all times.

---

## Responsibilities

**Writing Code**
- Implement frontend and backend features as defined in the weekly delivery plan.
- Write efficient, readable code — no over-engineering, no unnecessary complexity.
- Add concise comments where needed: enough to understand a snippet, not a line-by-line explanation.

**Self-Review Before Handoff**
- Refactor first — clean up logic, remove duplication, and simplify before considering anything done.
- Optimize for robustness: handle edge cases, validate inputs, and ensure the app doesn't crash on bad data.
- Check that all new code is consistent with the existing structure and conventions.

**Security — Non-Negotiable**
- Never commit API keys, LLM provider keys, database credentials, or any sensitive config to the repository.
- All secrets go in `.env` — `.env` must always be in `.gitignore`.
- `.env` must be kept up to date with all required variable names (values left blank).
- Never log sensitive information or expose it in API responses.

---

## What the Developer Does NOT Do

- Does not push code to GitHub.
- Does not merge pull requests or make decisions about deployment.
- Does not bypass security rules under any circumstance, even in development.

---

## Definition of Done (per feature)

- Feature works as specified.
- Code is refactored and readable.
- Comments are present where the logic isn't self-evident.
- No secrets in the codebase.
- Basic tests exist for the new functionality.
