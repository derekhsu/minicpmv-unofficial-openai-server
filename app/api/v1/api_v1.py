from fastapi import APIRouter
from app.api.v1.endpoints import (
    chat_completions
)

router = APIRouter()

router.include_router(chat_completions.router, tags=["OpenAI"])