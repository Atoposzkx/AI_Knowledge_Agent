"""生命周期测试学习记录。

测试目标：一次应用运行期间复用客户端，退出时关闭，再次启动时创建新对象。
保留真实 lifespan、Router 和 Service，只替换启动时创建的 LLMClient。
因此测试不访问模型 API，但会真正执行应用的启动与关闭逻辑。

阅读顺序：
1. 准备能记录调用情况的假客户端。
2. 让 lifespan 创建这个假客户端。
3. 进入 TestClient，检查启动和请求期间的行为。
4. 退出 TestClient，检查资源是否关闭。
5. 重复一次生命周期，检查是否创建了新客户端。
"""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

# 导入整个模块并取别名：main_module.app 是应用，main_module.LLMClient 是
# main.py 中使用的客户端类。后面要替换的是这个模块中的 LLMClient 名称。
import app.main as main_module


def test_lifespan_reuses_and_closes_client(monkeypatch):
    # 1. 准备假客户端：列表记录每次启动创建的对象，方便统计数量、比较身份。
    created_clients = []

    class FakeLLMClient:
        def __init__(self):
            # AsyncMock 是能被 await 调用、还能记录调用情况的假函数。
            # await self.generate(messages) 返回下面的固定答案；同时记录参数和次数。
            self.generate = AsyncMock(return_value="生命周期测试答案")
            # 假 close 不关闭真实网络资源，只记录应用是否 await 过它。
            self.close = AsyncMock()
            # 每次 FakeLLMClient() 都会执行 __init__，把新对象加入列表。
            created_clients.append(self)

    # 2. 临时替换 main.py 中的类名称，相当于 main_module.LLMClient = FakeLLMClient。
    # lifespan 仍执行原来的 LLMClient()，但测试期间它实际创建 FakeLLMClient。
    # monkeypatch 在测试结束时恢复这个名称，真实 lifespan 本身没有被替换。
    monkeypatch.setattr(main_module, "LLMClient", FakeLLMClient)

    # 同一个应用对象经历两轮“启动 → 请求 → 关闭”，不是重启 Python 进程。
    # startup 第一轮为 0，第二轮为 1；列表累计应分别有 1、2 个客户端。
    # 外层循环的目的：检查第一次关闭以后，第二次启动会创建新客户端，
    # 而不是误用已经关闭的对象。只启动一次，无法检查“再次启动”的行为。
    # 两层循环的执行顺序：
    # 第一次启动 → 创建 A → 请求 1 用 A → 请求 2 用 A → 关闭 A
    # 第二次启动 → 创建 B → 请求 1 用 B → 请求 2 用 B → 关闭 B
    # 同一次运行：不同请求应复用同一个客户端；不同生命周期：应创建不同客户端。
    # 循环负责制造这些场景，assert 才负责检查行为是否正确。
    for startup in range(2):
        # 3. 进入 with：执行 lifespan 中 yield 前的代码，准备好服务和客户端。
        with TestClient(main_module.app) as client:
            assert len(created_clients) == startup + 1
            # 取得本次启动创建的客户端，以及真实 lifespan 保存的 Service。
            llm_client = created_clients[startup]
            service = main_module.app.state.chat_service
            # is 检查是否为同一个对象，不只是内容是否相等。
            assert service.llm_client is llm_client
            # 应用还在运行，此时 close 不应该被 await 执行过。
            llm_client.close.assert_not_awaited()

            # _ 表示不需要使用循环序号，只重复发两次请求。
            # 请求经过真实 Router、Service，最后调用假客户端的 generate。
            # 内层循环的目的：检查多次请求是否复用本次启动创建的客户端。
            # 发两次请求后，再检查创建数量不变；若每个请求都通过被替换的
            # 工厂创建新客户端，下面的数量断言就会发现问题。
            for _ in range(2):
                response = client.post("/chat", json={"message": "你好"})
                assert response.status_code == 200
                assert response.json() == {"answer": "生命周期测试答案"}

            assert main_module.app.state.chat_service is service  # Service 没有换对象。
            assert len(created_clients) == startup + 1  # 请求期间没有额外创建客户端。
            assert llm_client.generate.await_count == 2  # 本次客户端处理了两个请求。

        # 4. 这里已退出 with，lifespan 的 finally 应当执行完毕。
        # assert_awaited_once 要求 await llm_client.close() 恰好执行一次。
        llm_client.close.assert_awaited_once()
        # hasattr 检查属性是否存在；not 要求它不存在，对应 del app.state.chat_service。
        assert not hasattr(main_module.app.state, "chat_service")

    # 5. is not 检查两次启动创建的不是同一个对象，避免复用已关闭的客户端。
    assert created_clients[0] is not created_clients[1]
