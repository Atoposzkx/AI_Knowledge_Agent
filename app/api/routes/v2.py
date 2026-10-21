"""V2 的 HTTP 边界；业务错误映射沿用 V1 状态码。"""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.exceptions import LLMConnectionError, LLMProviderError, LLMResponseError, LLMTimeoutError
from app.schemas.notes import NoteAnalysis, NoteRequest
from app.schemas.tool_chat import ToolChatRequest, ToolChatResponse
from app.services.note_service import NoteAnalysisService
from app.services.tool_chat_service import ToolChatService

router = APIRouter()

def get_note_service(request: Request) -> NoteAnalysisService:
    return request.app.state.note_service

def get_tool_service(request: Request) -> ToolChatService:
    return request.app.state.tool_service

async def http_result(operation):
    try:
        return await operation
    except LLMTimeoutError as exc:
        raise HTTPException(504, "等待模型回答超时，请稍后再试") from exc
    except LLMConnectionError as exc:
        raise HTTPException(503, "暂时无法连接模型服务，请稍后再试") from exc
    except (LLMProviderError, LLMResponseError) as exc:
        raise HTTPException(502, "模型服务或响应不可用，请稍后再试") from exc

ERRORS = {502: {"description": "模型服务或响应不可用"},
          503: {"description": "无法连接模型服务"}, 504: {"description": "模型超时"}}

@router.post("/notes/analyze", response_model=NoteAnalysis, responses=ERRORS, tags=["notes"])
async def analyze_note(body: NoteRequest, service: Annotated[NoteAnalysisService, Depends(get_note_service)]):
    return await http_result(service.analyze(body.note_text))

@router.post("/chat/tools", response_model=ToolChatResponse, responses=ERRORS, tags=["chat"])
async def tool_chat(body: ToolChatRequest, service: Annotated[ToolChatService, Depends(get_tool_service)]):
    return await http_result(service.answer(body))
