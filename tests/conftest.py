"""在导入应用前设置测试配置，不依赖真实密钥，并阻止误调用外部模型。"""

import os

import pytest
from openai import AsyncOpenAI

# 必须早于测试模块导入 app；普通 fixture 在模块导入后才执行。
os.environ["LLM_API_KEY"] = "test-placeholder-not-a-real-key"
os.environ["LLM_BASE_URL"] = "https://example.invalid"
os.environ["LLM_MODEL"] = "test-model"
os.environ["LLM_TIMEOUT_SECONDS"] = "1"
os.environ["LLM_MAX_RETRIES"] = "0"


@pytest.fixture(autouse=True)
def prevent_real_llm_requests(monkeypatch):
    """所有测试自动使用：忘记替换模型方法时立即失败，而不是访问网络。"""
    async def blocked_request(*args, **kwargs):
        raise AssertionError("测试不得调用真实模型，请先替换 SDK 或模型方法")

    monkeypatch.setattr(AsyncOpenAI, "request", blocked_request)
