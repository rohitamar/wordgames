# Repository Guidelines

## Project Structure & Module Organization
`backend/` contains the active application code. `server.py` creates the FastAPI app and registers routes, `rhyme_route.py` holds HTTP handlers under `/rhyme`, and `services/rhyme_match.py` contains rhyme-matching logic. Keep new business rules in `backend/services/` and keep route files thin.

`frontend/` exists as a placeholder for future UI work and is currently empty. Do not commit generated files such as `__pycache__/`; `.gitignore` already excludes `.venv/` and cache directories.

## Build, Test, and Development Commands
Use the local virtual environment in `.venv/`.

- `source .venv/Scripts/activate` activates the project environment in Git Bash.
- `cd backend && ../.venv/Scripts/python -m uvicorn server:app --reload` runs the API locally with reload.
- `cd backend && ../.venv/Scripts/python -m compileall .` performs a quick syntax check across backend modules.

If you add dependencies, document them in the repository before relying on them in commits or PRs.

## Coding Style & Naming Conventions
Use Python with 4-space indentation, `snake_case` for functions and variables, and short, explicit module names such as `rhyme_route.py`. Prefer small route handlers that delegate to service functions. Keep return payloads simple JSON dictionaries unless a schema layer is introduced.

Follow the existing import style: standard library first, then third-party packages, then local modules. No formatter or linter is configured yet, so keep style changes minimal and consistent with surrounding code.

## Testing Guidelines
There is no automated test suite checked in yet. For now, validate changes with `python -m compileall` and manual API checks against `/health` and `/rhyme/check`.

When adding tests, place them under a top-level `tests/` directory and name files `test_<feature>.py`. Focus first on service-level coverage for `backend/services/` and edge cases around pronunciation lookup.

## Commit & Pull Request Guidelines
Recent history uses short commit subjects (`first`, `Bootstrap monorepo scaffold`). Prefer concise, imperative messages with actual scope, for example `Add rhyme endpoint health check`.

PRs should include a short summary, the behavior change, manual test steps, and sample request/response output for API changes. Link the relevant issue when one exists.
