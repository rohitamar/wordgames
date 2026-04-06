from fastapi import APIRouter

from services.rhyme_match import rhymes

rhyme_router = APIRouter(prefix="/rhyme")

@rhyme_router.get("/check")
def check(word1: str, word2: str):
    condition = rhymes(word1, word2) if word1 != word2 else False 
    return {
        "rhymes": condition
    }
