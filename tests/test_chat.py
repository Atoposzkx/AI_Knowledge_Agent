"""聊天接口测试。

TODO（实现 /chat 时逐步补充）：
- 正常消息返回 ChatResponse；
- 缺少 message 或空 message 时返回 422；
- 使用假的 LLMClient，避免测试真正消耗模型 API；
- LLM 超时或失败时返回约定的错误。
"""



'''聊天接口测试'''

from fastapi.testclient import TestClient
from app.main import app
from app.api.routes.chat import chat_service
from app.core.exceptions import LLMTimeoutError

'''测试时临时替换真实的模型调用'''
async def fake_genenerate(messages):
    '''代替真实的LLM,返回固定的答案'''
    return "这是测试答案"

def test_chat_sucess(monkeypatch):
    #临时替换当前LLM客户端的generate方法
    #。可以使用 monkeypatch.setattr 来将函数或属性替换为符合测试需求的版本
    #找到 chat_service.llm_client 这个对象，把它名为 "generate" 的属性，临时替换为 fake_genenerate 函数
    monkeypatch.setattr(
        chat_service.llm_client,
        "generate", #加引号，因为它是要替换的属性名称。
        fake_genenerate, #不加引号、不加括号，因为这里传递的是函数本身，让 Service 稍后调用。
    )
    #相当于你在 /docs 中填写 JSON 并点击 Execute。
    #TestClient 理解成：一个专门在测试代码里模拟 HTTP 客户端的工具。
    with TestClient(app) as client: #创建一个专门用来测试这个 FastAPI app 的客户端。

        #你的 FastAPI 返回的 HTTP Response。
        response = client.post(
            "/chat",
            json={"message":"你好"},
        )

    assert response.status_code == 200
    assert response.json() == {"answer":"这是测试答案"}

async def fake_generate_timeout(messages):
    '''模拟模型调用超时'''
    raise LLMTimeoutError("测试：模型超时")


def test_chat_timeout(monkeypatch):
    monkeypatch.setattr(
        chat_service.llm_client,
        "generate",
        fake_generate_timeout,
    )

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"message":"你好"},
        )

    assert response.status_code == 504
    assert response.json() == {
        "detail":"等待模型回答超时，请稍后再试"
    }


async def fake_generate_empty(messages):
    raise AssertionError("无效输入不应该调用此模型")
def test_chat_request(monkeypatch):
    #额外检查一件事：被拒绝的输入，不应该继续调用模型。
    monkeypatch.setattr(
        chat_service.llm_client,
        #模型客户端上的方法名字
        "generate",
        #
        fake_generate_empty,
    )

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"message":"  "},
        )
    assert response.status_code == 422

async def fake_generate_null(messages):
    raise AssertionError("无效输入不应该调用此模型")
def test_chat_full(monkeypatch):
    #额外检查一件事：被拒绝的输入，不应该继续调用模型。
    monkeypatch.setattr(
        chat_service.llm_client,
        #模型客户端上的方法名字
        "generate",
        #
        fake_generate_empty,
    )

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={},
        )
    assert response.status_code == 422


'''
Mock也就是：
用一个假的 LLM 行为替换真实模型调用。Mock 不是“伪造结果骗过测试”，而是把不稳定的外部依赖替换成一个可控替身，从而专门测试你自己的代码行为。

利用这个测试，流程就变为
TestClient
↓
POST /chat
↓
FastAPI
↓
Service
↓
假的 generate()
↓
固定返回 "你好呀"
↓
FastAPI Response
↓
assert 200
↓
assert answer == "你好呀"
因此我们在这里引用monkeypatch 可以在测试运行期间，把某个函数、方法、变量临时替换掉。

Mock 不只是“返回值一样”，最好连调用方式也保持一致：

真的 generate()
→ async
→ 返回 str

假的 generate()
→ async
→ 返回 str

monkeypatch.setattr(
    LLMClient,
    "generate",
    fake_generate,
)
LLMClient
→ 我要修改谁

"generate"
→ 我要修改它的哪个属性 / 方法

fake_generate
→ 临时替换成什么
'''