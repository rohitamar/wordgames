from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lobby_router import lobby_router
from rhyme_route import rhyme_router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(lobby_router)
app.include_router(rhyme_router)

@app.get("/health", status_code=200)
def health():
    return { "message": "ok" }
