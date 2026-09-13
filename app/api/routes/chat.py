"""聊天接口。

Router 只处理 HTTP 边界：接收并校验请求、调用 Service、包装响应。
Prompt 拼装、知识检索和 LLM 调用都不应该写在这个文件中。
"""

from fastapi import APIRouter, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse


router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def create_chat(request: ChatRequest) -> ChatResponse:
    """接收一条用户消息并返回模型回答。

    TODO（后续由你实现）：
    1. 获取 ChatService；
    2. 把 request.message 交给 Service；
    3. 将 Service 返回的答案包装为 ChatResponse。

    目前主动返回 501，表示接口已经规划但业务尚未实现。
    """
    del request  # 骨架阶段暂不使用；实现 Service 后删除这一行。
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Chat service has not been implemented yet.",
    )
