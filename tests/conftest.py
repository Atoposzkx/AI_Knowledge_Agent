"""公共测试配置与学习说明。

pytest 会自动加载这个目录下的 conftest.py，测试文件不用手动导入它。
这里做两件事，它们与每个测试自己的输入、假函数和断言各有不同职责：

1. 提供创建应用和客户端所需的配置，使测试不依赖真实密钥和本地 .env。
2. 在每个测试执行前拦截 SDK 请求；漏掉 Mock 时立即报错。

目前相关测试都已经正确替换了模型调用，所以正常运行不会触发拦截。
这个文件不是让 Mock 生效的必要步骤，也不是说明已有测试不完整。
假配置解决“创建对象需要什么”，请求拦截解决“忘了 Mock 会怎样”。
"""

import os

import pytest
from openai import AsyncOpenAI

# 第一部分：在加载应用之前提供测试配置。
#
# 测试虽然替换了 responses.create，但通常先执行 llm_client = LLMClient()。
# 创建真实客户端时，__init__ 仍会使用密钥、地址、模型、超时和重试配置。
# Mock 跳过实际请求，并没有跳过前面的配置读取和对象创建。
#
# 此处的“配置”不是测试的 message、预期答案或 assert，而是应用运行配置。
# os.environ 是当前进程的环境变量映射；下面赋值不会修改你的 .env 文件。
# Settings 默认优先使用环境变量，因此这些值会覆盖 .env 中的对应配置。
# 假密钥仅用于满足初始化要求，不是真实模型服务可用的凭据。
#
# 执行顺序：加载 conftest.py 设置变量 → 加载测试模块并导入 app
# → app/core/config.py 执行 settings = Settings() → 创建客户端 → 替换方法。
# 所以必须在模块加载时设置变量；普通 fixture 到每个测试执行前才运行，
# 那时 settings 可能已经创建，无法通过迟来的环境变量赋值自动更新它。
os.environ["LLM_API_KEY"] = "test-placeholder-not-a-real-key"
os.environ["LLM_BASE_URL"] = "https://example.invalid"
os.environ["LLM_MODEL"] = "test-model"
os.environ["LLM_TIMEOUT_SECONDS"] = "1"
os.environ["LLM_MAX_RETRIES"] = "0"


# 第二部分：在测试漏掉 Mock 时阻止 SDK 发送真实请求。
#
# fixture 是 pytest 提供的测试准备机制；monkeypatch 本身也是一个 fixture。
# autouse=True 表示本目录及子目录的测试自动使用它，不必写进测试参数。
# 默认作用域是 function，因此每个测试执行前都会运行一次下面的函数。
@pytest.fixture(autouse=True)
def prevent_real_llm_requests(monkeypatch):
    """所有测试自动使用：忘记替换模型方法时立即失败，而不是访问网络。"""
    # *args 接收位置参数，**kwargs 接收关键字参数。
    # 替换类方法后，实例调用还可能传入 self；这些参数都能接住。
    # 不关心具体请求内容，只要执行到这里，就立即让测试失败。
    async def blocked_request(*args, **kwargs):
        raise AssertionError("测试不得调用真实模型，请先替换 SDK 或模型方法")

    # 临时替换 SDK 类上的 request 方法；测试结束后 monkeypatch 自动恢复。
    #
    # 正确 Mock：真实 generate → 假 responses.create → 固定答案或异常。
    # 此时不会执行 SDK request，这个拦截函数也不会触发。
    #
    # 漏掉 Mock：真实 generate → 真实 responses.create → SDK request
    # → blocked_request 抛出 AssertionError，提醒测试漏掉了替换。
    # 它拦截的是这里的 SDK 请求路径，不是禁止整个测试进程使用网络。
    monkeypatch.setattr(AsyncOpenAI, "request", blocked_request)
