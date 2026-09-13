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


app = FastAPI(
    title="AI Knowledge Agent",
    version="0.1.0",
    description="AI Knowledge Agent V1 API",
)

# Router 在入口处统一注册。以后增加新的业务模块时，也在这里挂载。
app.include_router(health_router)
app.include_router(chat_router)
