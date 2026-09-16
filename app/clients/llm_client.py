"""LLM 客户端抽象。

这个模块负责隐藏具体厂商 SDK 的调用方式，让 Service 不必知道底层使用
OpenAI、其他云模型还是本地模型。
"""
from openai import AsyncOpenAI,APITimeoutError

from app.core.config import settings
from app.core.exceptions import LLMTimeoutError

class LLMClient:
    """调用大语言模型的统一入口。"""
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.llm_api_key.get_secret_value(),
            base_url=settings.llm_base_url,
            #单位为秒，用于限制网络操作的等待时间
            timeout=60.0,
            #表示失败后不自动尝试
            max_retries=0,
        )

    async def generate(self, messages: list[dict[str, str]]) -> str:
        # Responses API 的 input 可以接收 Service 组织好的消息列表。
        '''
        抛出异常流程
        OpenAI SDK 世界

APITimeoutError
        ↓
LLMClient
        ↓

你的业务异常世界

LLMTimeoutError
        ↓
Router 捕获 LLMTimeoutError，抛出 HTTPException
        ↓

HTTP 世界

504 Gateway Timeout

Exception Translation(异常转换):
SDK 异常
→ Infrastructure Layer 处理

业务异常
→ Application 内传播

HTTP 转换
→ Web Layer 处理
        '''
        try:
            response = await self.client.responses.create(
                model=settings.llm_model,
                input=messages,
            )
            #Exception Chaining，异常链。from exc 是明确说明“新异常由原异常引起”
        except APITimeoutError as exc:
            raise LLMTimeoutError("等待模型回答超时，请稍后重试") from exc

        # output 包含不同类型的输出项；output_text 快捷提取其中的文本。
        answer = response.output_text
        if not answer:
            raise ValueError("模型没有返回文本答案")

        return answer
        
'''
OpenAI Python SDK 是一个客户端库，它帮我们构造 HTTP Request、发送请求、携带认证信息，并把 API 返回的数据解析成 Python 对象。以下是流程
① 读取参数
   ↓
② 构造 HTTP Request
   ↓
③ 添加 API Key 等认证信息
   ↓
④ 把数据编码成 JSON
   ↓
⑤ 发送 HTTPS 请求
   ↓
⑥ OpenAI API 接收
   ↓
⑦ 模型运行
   ↓
⑧ API 返回 JSON
   ↓
⑨ SDK 解析
   ↓
⑩ 生成 Python Response 对象

两组API区别：
Chat Completions 是“给一组聊天消息，生成下一条聊天结果”；Responses 是“给模型输入，让模型产生一组通用输出项”，因此更容易统一承载文本、工具调用、推理状态和 Agent 工作流。
|                   | Chat Completions             | Responses API                 |
| ----------------- | ---------------------------- | ----------------------------- |
| 核心抽象              | 聊天消息                         | 模型响应 / 输出项                    |
| 输入核心              | `messages=[...]`             | `input=...`                   |
| 输出核心              | `choices[0].message`         | `response.output`             |
| 纯文本快捷读取           | `choices[0].message.content` | `response.output_text`        |
| 主要思维              | 聊天                           | 通用 AI / Agent 工作流             |
| Function Calling  | 支持                           | 支持                            |
| Structured Output | 支持                           | 支持                            |
| Streaming         | 支持                           | 支持                            |
| OpenAI 内置 Tools   | 相对不是其核心抽象                    | Responses 的重要设计部分             |
| 多轮状态/推理连续性        | 主要围绕消息历史                     | 提供 response/conversation 状态机制 |
| 新项目定位             | 仍支持                          | 当前主要 API                      |

'''
