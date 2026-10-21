from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class HistoryMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=10000)

class ToolChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=10000)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def check_context(self):
        self.message = self.message.strip()
        if not self.message:
            raise ValueError("message不能为空")
        if sum(len(item.content) for item in self.history) + len(self.message) > 20000:
            raise ValueError("上下文总字符数不能超过20000")
        return self

class ToolChatResponse(BaseModel):
    answer: str
    tool_results: list[dict]
