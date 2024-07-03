from typing import Any, List, Literal, Text, Optional, Union
from pydantic import BaseModel

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: Union[Text, List[Any]]

class ChatCompletionsRequest(BaseModel):
    messages: List[ChatMessage]    
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    stop: Optional[List[str]] = None
    repetition_penalty: Optional[float] = None

    