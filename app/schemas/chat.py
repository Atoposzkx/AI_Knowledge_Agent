"""聊天接口的数据模型。"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """POST /chat 接收的 JSON 数据。"""

    # 最小长度避免空字符串；最大长度防止一次请求无限增大。
    message: str = Field(min_length=1, max_length=10_000)


class ChatResponse(BaseModel):
    """POST /chat 成功时返回的 JSON 数据。"""

    answer: str
