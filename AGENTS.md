# Repository Guidelines

## Project Structure & Module Organization
This repository is a small monorepo with a FastAPI backend and a React/Vite frontend.

- `backend/server.py` creates the FastAPI app, configures CORS, and registers routers.
- `backend/rhyme_route.py` exposes the HTTP rhyme check route under `/rhyme/check`.
- `backend/lobby_router.py` contains the realtime lobby and game flow, including SSE at `/lobby/stream` and WebSocket connections at `/ws/{username}`.
- `backend/services/rhyme_match.py` contains the pronunciation-based rhyme logic built on `pronouncing`.
- `frontend/src/App.jsx` is the main client and currently contains most of the game UI and realtime client logic.
- `frontend/src/main.jsx` bootstraps the React app.
- `frontend/vite.config.js` contains the Vite dev server config.
- `backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.yml` define the containerized local stack.

Keep business logic in `backend/services/`, keep backend route files thin where practical, and avoid introducing generated artifacts such as `__pycache__/`, `frontend/dist/`, or `frontend/node_modules/`.

## Build, Test, and Development Commands
Use the commands that match the environment you are actually running in. The checked-in Python virtual environment currently lives under `backend/.venv/`.

- `cd backend && .venv/bin/python -m uvicorn server:app --reload` runs the FastAPI backend locally from WSL/Linux.
- `cd backend && ../.venv/Scripts/python -m uvicorn server:app --reload` is the Windows-style variant if a repo-root virtual environment exists.
- `cd frontend && npm install` installs frontend dependencies.
- `cd frontend && npm run dev -- --host` runs the Vite frontend locally.
- `python3 -m py_compile backend/server.py backend/rhyme_route.py backend/lobby_router.py backend/services/rhyme_match.py` performs a quick backend syntax check without recursing into the virtual environment.
- `docker compose up --build` starts the current two-container local stack on `http://localhost:8080` for the frontend and `http://localhost:8000` for the backend.

If you add dependencies, update the relevant manifest and lockfile in the same change:

- Backend: `backend/requirements.txt`
- Frontend: `frontend/package.json` and `frontend/package-lock.json`

## Coding Style & Naming Conventions
Python code uses 4-space indentation, `snake_case`, and small modules with explicit names. Follow the existing import order: standard library, third-party, then local imports. Keep API responses simple JSON dictionaries unless the project adds a schema layer.

Frontend code uses React function components and the current project style is inline styles in `App.jsx`. Keep changes consistent with the existing code unless you are intentionally refactoring the UI structure. Use `camelCase` for JavaScript variables and functions.

Prefer environment-driven URLs for frontend-to-backend communication. The frontend currently reads:

- `VITE_API_BASE_URL`
- `VITE_WS_BASE_URL`

When those are absent, local development falls back to `localhost:8000`.

## Testing Guidelines
There is still no automated test suite checked in. For now, validate changes with targeted syntax checks and manual end-to-end verification.

Minimum manual checks:

- `GET /health`
- `GET /rhyme/check?word1=cat&word2=hat`
- Open two browser sessions and verify lobby presence updates through `/lobby/stream`
- Verify WebSocket game flow through `/ws/{username}`
- Verify turn countdown, guess submission, duplicate-word rejection, and timeout elimination

When adding tests:

- Put backend tests under top-level `tests/`
- Name files `test_<feature>.py`
- Focus first on `backend/services/` and `backend/lobby_router.py`
- Add frontend tests only if you also introduce the test tooling for them

## Docker & Hosting Notes
The current Docker setup does not use Nginx.

- `backend/Dockerfile` runs FastAPI with Uvicorn on port `8000`
- `frontend/Dockerfile` builds the Vite app and serves it with `vite preview` on port `8080`
- `docker-compose.yml` wires the two services together for local use

Because the browser talks directly to the backend in this setup, remember to keep backend CORS aligned with the frontend origin.

## Commit & Pull Request Guidelines
Prefer short, imperative commit messages with real scope, for example:

- `Add Docker compose setup`
- `Implement lobby websocket flow`
- `Wire frontend to env-based API URLs`

PRs should include:

- A short summary of the change
- Behavior changes and any API contract changes
- Manual test steps
- Sample request/response output for backend changes
- Screenshots or short recordings for frontend changes when useful
- Linked issue or task if one exists
