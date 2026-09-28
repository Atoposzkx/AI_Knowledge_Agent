"""聊天接口测试。

TODO（实现 /chat 时逐步补充）：
- 正常消息返回 ChatResponse；
- 缺少 message 或空 message 时返回 422；
- 使用假的 LLMClient，避免测试真正消耗模型 API；
- LLM 超时或失败时返回约定的错误。
"""

#这个文件综述：Router 测 HTTP；Service 测业务逻辑；Client 测外部 API 封装。我们测试了三个层面。

#测试哪一层，就保留这一层真实，把它下面的依赖替换掉。
'''
Router Test
→ 保留真实 Router
→ Fake ChatService

Service Test
→ 保留真实 ChatService
→ Fake LLMClient

LLMClient Test
→ 保留真实 LLMClient
→ Fake SDK / responses.create

对应 Mock：

Router Test
→ dependency_overrides

Service Test
→ Fake LLMClient / monkeypatch

Client Test
→ Mock SDK / HTTP 层
'''
'''聊天接口测试'''

from fastapi.testclient import TestClient
from app.main import app
from app.api.routes.chat import get_chat_service
from app.core.exceptions import LLMTimeoutError,LLMResponseError


'''测试时临时替换真实的模型调用'''
async def fake_genenerate(messages):
    '''代替真实的LLM,返回固定的答案'''
    return "这是测试答案"

# 旧版学习记录：使用模块级 chat_service，在启动 TestClient 前替换方法。
# 下面用多行字符串保留旧代码，不会被 pytest 收集或执行。
"""
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
"""


def test_chat_sucess(monkeypatch):
    """验证正常聊天，并记录生命周期改造前后的测试顺序。

    旧版：导入 chat.py 时就创建全局 chat_service，因此可以先替换
    generate，再进入 TestClient。

    新版：导入 app 只是注册 lifespan；进入 with TestClient(app) 时，
    才执行 lifespan 中 yield 前的代码，创建客户端和 Service。
    因此必须先启动应用，再取服务、替换方法，最后发送请求。
    启动时创建这些对象不会调用模型；实际调用发生在处理聊天请求时。
    """
    # 1. 进入上下文：触发应用启动，等待 lifespan 完成资源准备。
    with TestClient(app) as client:
        # 2. 取得本次启动创建的对象，不是复制或新建 Service。
        # get_chat_service() 给路由提供的也是 app.state 中的同一个对象。
        chat_service = app.state.chat_service
        # 3. 在发请求之前替换 generate；此时只是替换，还未执行假函数。
        monkeypatch.setattr(
            chat_service.llm_client, "generate", fake_genenerate
        )
        # 4. 请求经过真实 Router、Service，调用替换后的假模型方法。
        response = client.post("/chat", json={"message": "你好"})
    # 5. 退出 with：lifespan 的 finally 关闭客户端；已取得的响应仍可检查。
    # 下次进入 TestClient 会重新创建客户端，不复用本次已关闭的对象。
    assert response.status_code == 200
    assert response.json() == {"answer": "这是测试答案"}
    # 测试结束后，pytest 的 monkeypatch 撤销方法替换。
    # 方法恢复由 monkeypatch 负责，客户端关闭由 lifespan 负责。


#--------------------------------------

#单独测试LLMClient
'''
在lim_client.py中，我们有APITimeoutError,但是在这个版本中我们

| 测试         |        保留真实代码       |    替换部分 |

| 之前的聊天测试 | Router、Service | `LLMClient.generate()` |
| 下一步的 Client 测试 | `LLMClient.generate()` | SDK 的 `responses.create()` |

让假的 SDK 调用抛出 APITimeoutError，再检查真实 Client 是否抛出 LLMTimeoutError。这样无需访问 DeepSeek，也能验证异常转换。
这个我们将新建文件test_llm_client.py,专门测试客户端
'''


async def fake_generate_timeout(messages):
    #模拟模型调用超时
    raise LLMTimeoutError("测试：模型超时")

# 旧版学习记录：假函数抛出 LLMTimeoutError，Router 将它转换为 504。
"""
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
"""


def test_chat_timeout(monkeypatch):
    # 新版：先启动应用、取出服务，再替换模型方法。
    with TestClient(app) as client:
        chat_service = app.state.chat_service
        monkeypatch.setattr(
            chat_service.llm_client, "generate", fake_generate_timeout
        )
        response = client.post("/chat", json={"message": "你好"})
    assert response.status_code == 504
    assert response.json() == {"detail": "等待模型回答超时，请稍后再试"}


async def fake_generate_empty(messages):
    raise AssertionError("无效输入不应该调用此模型")
# 旧版学习记录：空白输入应返回 422，且不应调用模型。
"""
def test_chat_request(monkeypatch):
    #其实下面不写假函数也可以，额外检查一件事：被拒绝的输入，不应该继续调用模型。
    
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
"""


def test_chat_request(monkeypatch):
    with TestClient(app) as client:
        chat_service = app.state.chat_service
        # 保留“误调用就报错”的替身，验证输入被拒绝后不会调用模型。
        monkeypatch.setattr(
            chat_service.llm_client, "generate", fake_generate_empty
        )
        response = client.post("/chat", json={"message": "  "})
    assert response.status_code == 422

async def fake_generate_null(messages):
    raise AssertionError("无效输入不应该调用此模型")
# 旧版学习记录：缺少必填字段 message，也应在调用模型前被拒绝。
"""
def test_chat_full(monkeypatch):
    #额外检查一件事：被拒绝的输入，不应该继续调用模型。
    monkeypatch.setattr(
        chat_service.llm_client,
        #模型客户端上的方法名字
        "generate",
        #
        fake_generate_null,
    )

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={},
        )
    assert response.status_code == 422
"""


def test_chat_full(monkeypatch):
    with TestClient(app) as client:
        chat_service = app.state.chat_service
        monkeypatch.setattr(
            chat_service.llm_client, "generate", fake_generate_null
        )
        response = client.post("/chat", json={})
    assert response.status_code == 422


#------------------------------------------------------

#Router层面测试，Client 负责识别并报告问题，Router 负责把问题表达成 HTTP 响应。
class FakeChatService:
    '''测试用聊天服务，不调用真实模型'''
    async def generate_answer(self,message:str)->str:
        return "这是依赖替换的测试答案"
def get_fake_chat_service():
    return FakeChatService()
def test_chat_dependency_override(monkeypatch):
    #告诉FastAPI:用假服务提供函数替代原来的提供函数
    #setitem 用来修改字典的键值。（与setattr的区别，那个是临时替换对象/类的属性）
    #app.dependency_overrides。它是 FastAPI 提供的一个字典，用来记录：原本要调用哪个依赖函数，现在改用哪个函数。
    #setitem相当于app.dependency_overrides[get_chat_service] = get_fake_chat_service
    #在这次测试期间，告诉 FastAPI：原本凡是要执行 get_chat_service 的地方，都不要执行它，改成执行 get_fake_chat_service
    '''
真实的流程
POST /chat
↓
FastAPI
↓
发现 Depends(get_chat_service)
↓
检查 dependency_overrides
↓
发现：

get_chat_service
→ get_fake_chat_service

↓
调用 get_fake_chat_service()
↓
得到 FakeChatService
↓
注入 Router 的 service 参数

使用参数之间的联系
app.dependency_overrides
→ 我要修改哪个字典

get_chat_service
→ key，原来的依赖

get_fake_chat_service
→ value，用什么替代

app.dependency_overrides = {
    get_chat_service: get_fake_chat_service
}

为什么这个不用app.state.chat_service
原因是：app.state.chat_service 是在应用启动时创建的单例对象，而依赖注入机制允许我们在测试期间临时替换依赖函数，从而控制注入到路由中的服务实例。使用 dependency_overrides 可以在不修改全局状态的情况下替换依赖，保证测试的隔离性和可控性。
    '''
    monkeypatch.setitem(
        app.dependency_overrides,
        get_chat_service,
        get_fake_chat_service,
    )
    '''
    FastAPI 的 dependency_overrides：决定使用哪个依赖函数。
    pytest 的 monkeypatch.setitem()：临时添加这条字典记录，并在测试结束后自动恢复，避免影响其他测试。所以不用上面那个app.dependency_overrides[
    get_chat_service
] = get_fake_chat_service 这个之后还必须手动清理
    '''

    with TestClient(app) as client:
        response = client.post(
            "/chat",
            json={"message":"你好"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer":"这是依赖替换的测试答案"
    }



async def fake_generate_invalid_response(messages):
    '''模拟Client报告模型响应不可用'''
    raise LLMResponseError("模型没有返回文本答案")

def test_chat_invalid_response(monkeypatch):
    with TestClient(app) as client:
        chat_service = app.state.chat_service
        monkeypatch.setattr(
            chat_service.llm_client, "generate", fake_generate_invalid_response
        )
        response = client.post("/chat", json={"message":"你好"})
    assert response.status_code == 502
    assert response.json() == {
        "detail": "模型返回了不可用的响应，请稍后再试"
    }



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
