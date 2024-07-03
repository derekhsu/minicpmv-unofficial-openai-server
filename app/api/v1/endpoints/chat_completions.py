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

def format_openai_chunk(text: str, role: str = "assistant", finish_reason: Optional[str] = None, force_zhtw: bool = False) -> Dict[str, Any]:

    if force_zhtw:
        opencc_converter = globals.opencc_converter
        text = opencc_converter.convert(text)

    return {
        "choices": [
            {
                "delta": {"role": role, "content": text},
                "index": 0,
                "finish_reason": finish_reason
            }
        ]
    }

def sse_format(generator, force_zhtw: bool = False):
    for text in generator:
        chunk = format_openai_chunk(text, force_zhtw=force_zhtw)
        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    
    end_chunk = format_openai_chunk("", finish_reason="stop")
    yield f"data: {json.dumps(end_chunk, ensure_ascii=False)}\n\n"

@router.post("/chat/completions")
async def chat_completions(request: ChatCompletionsRequest):        
    answer = globals.chat_model.chat(request)

    if (request.stream):
        return StreamingResponse(sse_format(answer, request.force_zhtw), media_type="text/event-stream")
    else:
        return answer