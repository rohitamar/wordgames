from fastapi import FastAPI

from rhyme_route import rhyme_router

app = FastAPI()
app.include_router(rhyme_router)

@app.get("/health", status_code=200)
def health():
    return { "message": "ok" }
