# WordGames

## Docker

The app can be run as a two-container stack:

- `backend`: FastAPI on port `8000`
- `frontend`: Node serving the built Vite app on port `8080`

### Run

```bash
docker compose up --build
```

Then open `http://localhost:8080`.

### Endpoints

- Frontend: `http://localhost:8080`
- Backend health check: `http://localhost:8000/health`
- Backend rhyme check: `http://localhost:8000/rhyme/check?word1=cat&word2=hat`

