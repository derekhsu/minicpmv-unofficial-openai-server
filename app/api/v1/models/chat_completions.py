from typing import Any, List, Literal, Text, Optional, Union
from click import Option
from pydantic import BaseModel

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: Union[Text, List[Any]]

class ChatCompletionsRequest(BaseModel):
    messages: List[ChatMessage]
    temperature: Optional[float] = 1.0
    top_p: Optional[float] = 1.0
    top_k: Optional[int] = 100
    max_tokens: Optional[int] = 2048
    stream: Optional[bool] = False
    stop: Optional[List[str]] = None
    repetition_penalty: Optional[float] = 1.05
    force_zhtw: bool = False

    