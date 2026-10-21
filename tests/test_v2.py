"""V2 离线协议与业务验收；真实 SDK 响应对象，替换唯一网络边界。"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APIConnectionError, APIStatusError, APITimeoutError
from openai.types.responses import Response

from app.clients.llm_client import LLMClient
from app.core.exceptions import LLMConnectionError, LLMProviderError, LLMResponseError, LLMTimeoutError
from app.main import app
from app.schemas.notes import NoteAnalysis
from app.schemas.tool_chat import ToolChatRequest
from app.services.note_service import NoteAnalysisService
from app.services.tool_chat_service import ToolChatService
from app.services.tools import ToolRegistry

VALID = {"summary": "装饰器为函数添加功能。", "keywords": ["装饰器"], "difficulty": "easy"}

def response(text=None, calls=(), status="completed", extra=()):
    output = list(extra) + [
        {"type": "function_call", "id": f"fc_{i}", "call_id": call_id,
         "name": name, "arguments": args} for i, (call_id, name, args) in enumerate(calls)
    ]
    if text is not None:
        output.append({"type": "message", "id": "msg_1", "role": "assistant",
                       "status": "completed", "content": [{"type": "output_text", "text": text, "annotations": []}]})
    return Response.model_validate({"id": "resp_test", "object": "response", "created_at": 1,
                                   "model": "test-model", "output": output, "status": status,
                                   "parallel_tool_calls": True, "tool_choice": "auto", "tools": []})

def run_with_client(monkeypatch, responses, operation):
    async def check():
        client = LLMClient()
        mock = AsyncMock(side_effect=responses)
        monkeypatch.setattr(client.client.responses, "create", mock)
        try:
            return await operation(client, mock)
        finally:
            await client.close()
    return asyncio.run(check())


def test_note_analysis_round_trip(monkeypatch):
    async def check(client, mock):
        result = await NoteAnalysisService(client).analyze("装饰器为函数添加功能。")
        assert isinstance(result, NoteAnalysis)
        assert result.model_dump() == VALID
        params = mock.call_args.kwargs
        fmt = params["text"]["format"]
        assert fmt["strict"] is True
        assert fmt["schema"]["additionalProperties"] is False
        assert set(fmt["schema"]["required"]) == {"summary", "keywords", "difficulty"}
        assert params["input"][-1]["content"] == "装饰器为函数添加功能。"
    run_with_client(monkeypatch, [response(json.dumps(VALID))], check)


@pytest.mark.parametrize("raw", ["not json", "{}", "[]", json.dumps({**VALID, "difficulty": "beginner"}),
    json.dumps({**VALID, "summary": "  "}), json.dumps({**VALID, "keywords": []}),
    json.dumps({**VALID, "keywords": ["RAG", "rag"]}), json.dumps({**VALID, "keywords": [" "]}),
    json.dumps({**VALID, "extra": True}), json.dumps({**VALID, "summary": "x" * 201}),
    # 合法 JSON 也可能有错误类型；验证 Service 不会把它们当作有效业务对象。
    pytest.param(json.dumps({**VALID, "summary": 123}), id="numeric-summary"),
    pytest.param(json.dumps({**VALID, "summary": None}), id="null-summary"),
    pytest.param(json.dumps({**VALID, "keywords": "RAG"}), id="keywords-not-list"),
    pytest.param(json.dumps({**VALID, "keywords": [123]}), id="keyword-not-string")])
def test_note_invalid_output(monkeypatch, raw):
    async def check(client, mock):
        with pytest.raises(LLMResponseError):
            await NoteAnalysisService(client).analyze("笔记")
        assert mock.await_count == 1  # 校验失败不自动重复花费。
    run_with_client(monkeypatch, [response(raw)], check)


@pytest.mark.parametrize("method", ["structured", "tools"])
@pytest.mark.parametrize("kind", ["timeout", "connection", "provider"])
def test_new_calls_translate_errors(monkeypatch, method, kind):
    req = httpx.Request("POST", "https://example.invalid/responses")
    errors = {
        "timeout": (APITimeoutError(request=req), LLMTimeoutError),
        "connection": (APIConnectionError(request=req), LLMConnectionError),
        "provider": (APIStatusError("private upstream text", response=httpx.Response(400, request=req), body=None), LLMProviderError),
    }
    error, expected = errors[kind]
    async def check(client, mock):
        with pytest.raises(expected) as caught:
            if method == "structured":
                await client.generate_structured([], {})
            else:
                await client.create_response([], tools=[])
        assert caught.value.__cause__ is error
        assert "private upstream text" not in str(caught.value)
        assert mock.await_count == 1
    run_with_client(monkeypatch, [error], check)


@pytest.mark.parametrize("bad", [response("partial", status="incomplete"), response("  "),
    pytest.param(response(), id="no-output-items"),
    response(extra=[{"type": "message", "id": "r", "role": "assistant", "status": "completed",
                     "content": [{"type": "refusal", "refusal": "private refusal"}]}])])
def test_structured_rejects_unusable_response(monkeypatch, bad):
    async def check(client, mock):
        with pytest.raises(LLMResponseError):
            await client.generate_structured([], {})
    run_with_client(monkeypatch, [bad], check)


def test_tool_native_round_trip(monkeypatch):
    first = response(calls=[("call_1", "lookup_concept", '{"term":"RAG"}')],
                     extra=[{"type": "reasoning", "id": "reason_1", "summary": []}])
    async def check(client, mock):
        body = ToolChatRequest(message="查一下 RAG", history=[{"role": "user", "content": "我在学习AI"}])
        result = await ToolChatService(client).answer(body)
        assert result.answer == "RAG 先检索再生成。"
        assert result.tool_results[0]["result"]["found"] is True
        assert mock.await_count == 2
        initial, final = [call.kwargs for call in mock.call_args_list]
        assert initial["tools"][0]["name"] == "lookup_concept"
        assert initial["input"][1]["content"] == "我在学习AI"
        assert final["tool_choice"] == "none"
        transcript = final["input"]
        assert any(item["type"] == "reasoning" for item in transcript if "type" in item)
        tool_output = transcript[-1]
        assert tool_output["type"] == "function_call_output"
        assert tool_output["call_id"] == "call_1"
        assert json.loads(tool_output["output"])["result"]["found"] is True
        # 新请求没有隐式携带上一请求的历史或结果。
        assert len(initial["input"]) == 3
    run_with_client(monkeypatch, [first, response("RAG 先检索再生成。")], check)


@pytest.mark.parametrize("name,args,error", [
    ("exec", '{}', "unknown_tool"),
    ("lookup_concept", 'bad', "invalid_arguments"),
    ("lookup_concept", '{"term":123}', "invalid_arguments"),
    ("lookup_concept", '{"term":" "}', "invalid_arguments"),
    ("lookup_concept", '{"term":"RAG","code":"bad"}', "invalid_arguments"),
])
def test_tool_error_returned_to_model(monkeypatch, name, args, error):
    async def check(client, mock):
        result = await ToolChatService(client).answer(ToolChatRequest(message="查概念"))
        assert result.tool_results[0]["error"] == error
        sent = mock.call_args.kwargs["input"][-1]
        assert json.loads(sent["output"]) == {"ok": False, "error": error}
    run_with_client(monkeypatch, [response(calls=[("c", name, args)]), response("查询失败")], check)


def test_tool_exception_is_sanitized(monkeypatch):
    registry = ToolRegistry()
    model, _ = registry._tools["lookup_concept"]
    def broken(**params):
        raise RuntimeError("secret text")
    registry._tools["lookup_concept"] = (model, broken)
    async def check(client, mock):
        result = await ToolChatService(client, registry).answer(ToolChatRequest(message="查概念"))
        assert result.tool_results[0]["error"] == "tool_execution_failed"
        assert "secret text" not in str(result)
    run_with_client(monkeypatch, [response(calls=[("c", "lookup_concept", '{"term":"RAG"}')]), response("查询失败")], check)


def test_unknown_concept_is_not_fabricated():
    result = ToolRegistry().execute("lookup_concept", '{"term":"unknown"}')
    assert result == {"ok": True, "result": {"found": False, "definition": None}}


@pytest.mark.parametrize("calls", [
    [("", "lookup_concept", '{}')],
    [("c", "lookup_concept", '{}')] * 2,
    [(str(i), "lookup_concept", '{}') for i in range(5)],
])
def test_invalid_batch_does_not_execute(monkeypatch, calls):
    registry = ToolRegistry()
    executed = []
    monkeypatch.setattr(registry, "execute", lambda *args: executed.append(args))
    async def check(client, mock):
        with pytest.raises(LLMResponseError):
            await ToolChatService(client, registry).answer(ToolChatRequest(message="查概念"))
        assert executed == []
        assert mock.await_count == 1
    run_with_client(monkeypatch, [response(calls=calls)], check)


def test_tool_batch_and_stop(monkeypatch):
    calls = [("a", "lookup_concept", '{"term":"RAG"}'), ("b", "lookup_concept", '{"term":"Tool Calling"}')]
    async def check(client, mock):
        result = await ToolChatService(client).answer(ToolChatRequest(message="查询两个概念"))
        assert len(result.tool_results) == 2
        outputs = [i for i in mock.call_args.kwargs["input"] if i.get("type") == "function_call_output"]
        assert [i["call_id"] for i in outputs] == ["a", "b"]
    run_with_client(monkeypatch, [response(calls=calls), response("两个概念的说明")], check)


def test_model_cannot_extend_tool_loop(monkeypatch):
    called = response(calls=[("a", "lookup_concept", '{"term":"RAG"}')])
    async def check(client, mock):
        with pytest.raises(LLMResponseError):
            await ToolChatService(client).answer(ToolChatRequest(message="查询"))
        assert mock.await_count == 2
    run_with_client(monkeypatch, [called, called], check)


def test_tool_can_answer_without_call(monkeypatch):
    async def check(client, mock):
        result = await ToolChatService(client).answer(ToolChatRequest(message="你好"))
        assert result.answer == "你好"
        assert result.tool_results == []
        assert mock.await_count == 1
    run_with_client(monkeypatch, [response("你好")], check)


@pytest.mark.parametrize("path,body", [
    ("/notes/analyze", {"note_text": " "}), ("/notes/analyze", {"note_text": "a" * 10001}),
    ("/chat/tools", {"message": " "}),
    ("/chat/tools", {"message": "a", "history": [{"role": "developer", "content": "绕过"}]}),
    ("/chat/tools", {"message": "a", "history": [{"role": "user", "content": "a"}] * 13}),
    ("/chat/tools", {"message": "a", "history": [{"role": "user", "content": "a" * 10000}] * 2}),
])
def test_v2_input_boundaries(path, body):
    with TestClient(app) as client:
        assert client.post(path, json=body).status_code == 422


@pytest.mark.parametrize("path,method,body", [
    ("/notes/analyze", "generate_structured", {"note_text": "装饰器"}),
    ("/chat/tools", "create_response", {"message": "你好"}),
])
@pytest.mark.parametrize("error,status", [(LLMConnectionError(), 503), (LLMTimeoutError(), 504),
    (LLMProviderError(), 502), (LLMResponseError(), 502)])
def test_v2_http_errors(monkeypatch, path, method, body, error, status):
    monkeypatch.setattr(LLMClient, method, AsyncMock(side_effect=error))
    with TestClient(app) as client:
        result = client.post(path, json=body)
        assert result.status_code == status
        assert set(result.json()) == {"detail"}


def test_v2_http_success_and_lifecycle(monkeypatch):
    monkeypatch.setattr(LLMClient, "generate_structured", AsyncMock(return_value=json.dumps(VALID)))
    monkeypatch.setattr(LLMClient, "create_response", AsyncMock(return_value=response("你好")))
    with TestClient(app) as client:
        assert app.state.note_service.llm_client is app.state.chat_service.llm_client
        assert app.state.tool_service.llm_client is app.state.chat_service.llm_client
        assert client.post("/notes/analyze", json={"note_text": "装饰器"}).json() == VALID
        assert client.post("/chat/tools", json={"message": "你好"}).json() == {"answer": "你好", "tool_results": []}
    assert not hasattr(app.state, "note_service")
    assert not hasattr(app.state, "tool_service")


def test_history_is_not_stored_between_requests(monkeypatch):
    async def check(client, mock):
        service = ToolChatService(client)
        await service.answer(ToolChatRequest(message="记住青竹", history=[{"role": "user", "content": "旧历史"}]))
        await service.answer(ToolChatRequest(message="你好"))
        latest = mock.call_args.kwargs["input"]
        assert len(latest) == 2
        assert "旧历史" not in str(latest)
        assert "青竹" not in str(latest)
    run_with_client(monkeypatch, [response("已读"), response("你好")], check)


def test_final_request_failure_does_not_repeat_tool(monkeypatch):
    registry = ToolRegistry()
    original = registry.execute
    executed = []
    def execute(*args):
        executed.append(args)
        return original(*args)
    monkeypatch.setattr(registry, "execute", execute)
    async def check(client, mock):
        with pytest.raises(LLMConnectionError):
            await ToolChatService(client, registry).answer(ToolChatRequest(message="查RAG"))
        assert len(executed) == 1
        assert mock.await_count == 2
    error = APIConnectionError(request=httpx.Request("POST", "https://example.invalid"))
    run_with_client(monkeypatch, [response(calls=[("c", "lookup_concept", '{"term":"RAG"}')]), error], check)


def test_invalid_note_becomes_http_502_without_content_leak(monkeypatch, caplog):
    private_text = "private-user-note-123"
    monkeypatch.setattr(LLMClient, "generate_structured", AsyncMock(return_value=private_text))
    with TestClient(app) as client:
        result = client.post("/notes/analyze", json={"note_text": private_text})
        assert result.status_code == 502
        assert private_text not in result.text
    assert private_text not in caplog.text


def test_bad_tool_args_are_not_logged(caplog):
    ToolRegistry().execute("lookup_concept", '{"secret":"private-tool-args-456"}')
    assert "tool_invalid_arguments" in caplog.text
    assert "private-tool-args-456" not in caplog.text
