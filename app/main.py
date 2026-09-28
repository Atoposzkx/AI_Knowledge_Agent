"""FastAPI 应用入口。

这里仅负责创建应用和注册 Router，不放聊天业务或 LLM 调用代码。
一次聊天请求未来会按以下方向流动：

HTTP Request -> Router（前台接单）-> Schema -> Service -> LLM Client
"""
'''
v1版本流程：
1. main.py
   找到已经注册的 chat router

2. api/routes/chat.py
   接收 POST /chat 请求

3. schemas/chat.py
   将 JSON 验证并转换为 ChatRequest

4. services/chat_service.py
   决定如何处理这条消息

5. clients/llm_client.py
   请求真实 LLM API

6. services/chat_service.py
   获得模型生成的答案

7. schemas/chat.py
   将答案包装成 ChatResponse

8. Router
   返回 JSON 和 HTTP 200
'''

from fastapi import FastAPI

from app.api.routes.chat import router as chat_router
from app.api.routes.health import router as health_router

from contextlib import asynccontextmanager
import logging
from app.clients.llm_client import LLMClient
from app.services.chat_service import ChatService
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)

'''
启动 Uvicorn
↓
进入 lifespan
↓
执行 yield 前面的代码
↓
创建各种资源
↓
遇到 yield
↓
────────────────
FastAPI 开始工作
处理 /chat
处理 /health
处理其他请求
────────────────
↓
应用准备关闭
↓
从 yield 后面继续
↓
关闭各种资源
↓
程序退出


应用启动
↓
LLMClient 创建一次

请求 1 ─┐
请求 2 ─┼→ 复用 LLMClient
请求 3 ─┘

应用关闭
↓
统一 close
'''
@asynccontextmanager
async def lifespan(app: FastAPI):

    configure_logging()
    llm_client = LLMClient()
   #lifespan 可以理解为：定义应用启动之前做什么，以及应用关闭时做什么。客户端要在应用运行期间持续复用，等整个应用关闭时再关闭。
   
   #app.state 是应用提供的一个存放共享对象的位置。这里把 ChatService 存进去，之后 get_chat_service() 就从这个位置取出服务，交给 Route
    try:
        #启动时创建服务，保存在当前应用上
        #app.state.chat_service	保存应用运行期间使用的 Service。get_chat_service()	取出 Service，供 Depends 注入
        app.state.chat_service = ChatService(llm_client=llm_client)
        logger.info("application_started")
        yield
    finally:
       #应用关闭时，清理本次启动创建客户端
        await llm_client.close()
        del app.state.chat_service
        logger.info("application_stopped")


app = FastAPI(
    title="AI Knowledge Agent",
    version="0.1.0",
    description="AI Knowledge Agent V1 API",
    lifespan=lifespan,
)

# Router 在入口处统一注册。以后增加新的业务模块时，也在这里挂载。
app.include_router(health_router)
app.include_router(chat_router)
