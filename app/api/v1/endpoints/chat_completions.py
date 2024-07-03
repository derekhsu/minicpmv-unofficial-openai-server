from typing import Dict, Any, Optional
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import logging
from transformers import AutoModel
from app.api.v1.models.chat_completions import ChatCompletionsRequest
import json

logger = logging.getLogger()
router = APIRouter()

import globals

def format_openai_chunk(text: str, role: str = "assistant", finish_reason: Optional[str] = None) -> Dict[str, Any]:
    return {
        "choices": [
            {
                "delta": {"role": role, "content": text},
                "index": 0,
                "finish_reason": finish_reason
            }
        ]
    }

def sse_format(generator):
    for text in generator:
        chunk = format_openai_chunk(text)
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    
    end_chunk = format_openai_chunk("", finish_reason="stop")
    yield f"data: {json.dumps(end_chunk, ensure_ascii=False)}\n\n"

@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionsRequest):        
    answer = globals.chat_model.chat(request)

    if (request.stream):
        return StreamingResponse(sse_format(answer), media_type="text/event-stream")
    else:
        return answer