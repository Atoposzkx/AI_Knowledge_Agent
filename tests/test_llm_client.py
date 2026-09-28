import asyncio

import httpx
import pytest
from openai import APITimeoutError

from app.clients.llm_client import LLMClient
from app.core.exceptions import LLMTimeoutError,LLMResponseError
#SimpleNamespace 可以创建一个通过点号访问属性的简单对象
'''
举例
response = SimpleNamespace(output_text="你好")
print(response.output_text)  # 你好
'''
from types import SimpleNamespace

#APITimeoutError 怎么人为创建？它是 OpenAI SDK 的异常。
#
async def fake_create(model,input):
    '''模拟SDK请求超时，不发送网络请求'''
    #httpx.Request(...）只是创建了一个 Python Request 对象，方便构造 SDK 异常。
    request = httpx.Request(
        "POST",
        "https://example.invalid/response",
    )
    raise APITimeoutError(request=request)

def test_llm_timeout(monkeypatch):
    llm_client = LLMClient()

    #保留真实 generate，只替换它内部调用的 SDK 方法。

    monkeypatch.setattr(
        llm_client.client.responses,
        "create",
        fake_create,
    )

    async def run_check():
        try:
            #我预期真实的 generate() 最终必须抛 LLMTimeoutError
            '''
            如果确实抛了：PASS
            如果没抛：
            FAIL
            Expected ValueError to be raised
            如果抛了别的：
            TypeError
            '''

            #执行时，假 create() 抛出 APITimeoutError，真实 generate() 接住它并转换为 LLMTimeoutError。pytest.raises() 收到预期异常，测试就通过
            with pytest.raises(LLMTimeoutError) as exc_info:
                await llm_client.generate(
                    [{"role":"user","content":"你好"}]
                )
            # 检查 from exc 是否保留了原始的 SDK 超时异常。
            assert isinstance(exc_info.value.__cause__, APITimeoutError)
        finally:
            await llm_client.client.close()
    #之前通过 TestClient 发送 HTTP 请求，它帮你运行异步路由。这次直接测试异步的 generate()，没有经过 FastAPI，所以我们用 asyncio.run(run_check()) 启动这段异步检查。
    asyncio.run(run_check())

'''
with的实际用法:
| 写法                      |     管理的对象      |      退出时主要做什么 |

|with open(...) as file: |          文件对象 | 关闭文件 |
with TestClient(app) as client:`|    测试客户端 | 清理测试客户端的相关资源 |
| with pytest.raises(...)` |       异常检查器 | 检查是否抛出了预期异常 |
try / finally：无论检查结果如何，都执行客户端清理。
'''


def test_llm_success(monkeypatch):
    llm_client = LLMClient()
    messages = [{"role": "user", "content": "你好"}]

    async def fake_create_success(model, input):
        # 检查真实 generate 有没有把消息正确传给 SDK。
        assert input == messages
        return SimpleNamespace(output_text="这是模型答案")

    monkeypatch.setattr(
        llm_client.client.responses,
        "create",
        fake_create_success,
    )

    async def run_check():
        try:
            answer = await llm_client.generate(messages)
            assert answer == "这是模型答案"
        finally:
            await llm_client.client.close()

    asyncio.run(run_check())


def test_llm_empty_answer(monkeypatch):
    """模型返回空文本时，Client 应拒绝这个答案。"""
    llm_client = LLMClient()
    messages = [{"role": "user", "content": "你好"}]

    async def fake_create_empty(model, input):
        return SimpleNamespace(output_text="")

    monkeypatch.setattr(
        llm_client.client.responses,
        "create",
        fake_create_empty,
    )

    async def run_check():
        try:
            # 同时检查异常类型和错误说明。
            with pytest.raises(LLMResponseError, match="模型没有返回文本答案"):
                await llm_client.generate(messages)
        finally:
            await llm_client.client.close()

    asyncio.run(run_check())
