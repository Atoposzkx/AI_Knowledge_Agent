"""聊天接口。

Router 只处理 HTTP 边界：接收并校验请求、调用 Service、包装响应。
Prompt 拼装、知识检索和 LLM 调用都不应该写在这个文件中。
"""


'''

'''
from app.core.exceptions import (
    LLMConnectionError, LLMProviderError, LLMResponseError, LLMTimeoutError,
)

from app.services.chat_service import ChatService

from app.schemas.chat import ChatRequest, ChatResponse

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request

'''
FastAPI    整家公司
APIRouter  一个部门
/chat      部门提供的一项服务
FastAPI 用于创建整个应用的主实例，而 APIRouter 用于创建子路由模块，创建的是一组接口，方便把不同业务拆到不同文件
'''

router = APIRouter(prefix="/chat", tags=["chat"])



def get_chat_service(request:Request)->ChatService:
    '''向路由提供聊天服务对象,取得应用启动时创建的聊天服务'''
    '''
    Request 是 FastAPI 提供的 HTTP 请求对象，能通过 request.app 找到处理请求的应用。
    ChatRequest 是你定义的 JSON 数据模型，里面有用户发送的 message
    FastAPI 会为这个依赖函数提供 Request，不需要用户额外传参。

    完整过程：
FastAPI startup
↓
lifespan
↓
ChatService 创建
↓
app.state.chat_service = ...

================

POST /chat
↓
Depends(get_chat_service)
↓
FastAPI 调 get_chat_service(request)
↓
request.app.state.chat_service
↓
拿到之前创建的 ChatService
↓
注入 Router
    '''
    return request.app.state.chat_service

#注册时的前缀 + Router 前缀 + 接口路径
@router.post(
    "", response_model=ChatResponse,
    responses={
        502: {"description": "模型响应不可用或上游返回错误"},
        503: {"description": "无法连接模型服务"},
        504: {"description": "等待模型超时"},
    },
)
async def create_chat(
    request: ChatRequest,
    #Annotated 用来把“类型”和“额外说明”放在一起。这里的额外说明就是 Depends(...)。这是 FastAPI 官方推荐的依赖声明写法。
    #create_chat() 需要一个 ChatService；这个对象不要从 HTTP 请求里拿，也不要让我自己创建，而是让 FastAPI 调用 get_chat_service() 帮我取得。
    #Router 声明：“我需要一个 ChatService”；FastAPI 根据 Depends(get_chat_service) 找到获取方法，执行它，然后把结果注入 service 参数。
    service:Annotated[ChatService,Depends(get_chat_service)]) -> ChatResponse:
    """接收一条用户消息并返回模型回答。

    处理步骤（已实现）：
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
    except LLMResponseError as exc:
        raise HTTPException(
            status_code=502,
            detail="模型返回了不可用的响应，请稍后再试",
        ) from exc
    except LLMConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail="暂时无法连接模型服务，请稍后再试",
        ) from exc
    except LLMProviderError as exc:
        # 上游的 401 并不代表本接口用户未登录，不直接照搬上游状态码。
        raise HTTPException(
            status_code=502,
            detail="模型服务请求失败，请稍后再试",
        ) from exc

    return ChatResponse(answer=answer)
