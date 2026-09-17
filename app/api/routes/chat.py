"""聊天接口。

Router 只处理 HTTP 边界：接收并校验请求、调用 Service、包装响应。
Prompt 拼装、知识检索和 LLM 调用都不应该写在这个文件中。
"""


'''

'''
from fastapi import APIRouter,HTTPException
from app.clients.llm_client import LLMClient
from app.core.exceptions import LLMTimeoutError
from app.services.chat_service import ChatService

from app.schemas.chat import ChatRequest, ChatResponse

from typing import Annotated
from fastapi import APIRouter,Depends,HTTPException
'''
FastAPI    整家公司
APIRouter  一个部门
/chat      部门提供的一项服务
FastAPI 用于创建整个应用的主实例，而 APIRouter 用于创建子路由模块，创建的是一组接口，方便把不同业务拆到不同文件
'''

router = APIRouter(prefix="/chat", tags=["chat"])

chat_service = ChatService(llm_client=LLMClient())

def get_chat_service()->ChatService:
    '''向路由提供聊天服务对象'''
    return chat_service

#注册时的前缀 + Router 前缀 + 接口路径
@router.post("", response_model=ChatResponse)
async def create_chat(
    request: ChatRequest,
    #Annotated 用来把“类型”和“额外说明”放在一起。这里的额外说明就是 Depends(...)。这是 FastAPI 官方推荐的依赖声明写法。
    service:Annotated[ChatService,Depends(get_chat_service)]) -> ChatResponse:
    """接收一条用户消息并返回模型回答。

    TODO：
    1. 获取 ChatService；
    2. 把 request.message 交给 Service；
    3. 将 Service 返回的答案包装为 ChatResponse。

    接收用户消息，调用 ChatService，并返回符合 ChatResponse 的结果。"""
    
    '''调用聊天服务，并包装响应'''
    try:
        answer = await service.generate_answer(request.message)
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail="等待模型回答超时，请稍后再试",
        ) from exc

    return ChatResponse(answer=answer)
