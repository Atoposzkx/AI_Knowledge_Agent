"""聊天业务服务。"""

from app.clients.llm_client import LLMClient


class ChatService:
    """协调一次完整的聊天业务流程。

    Service 不处理 HTTP，也不依赖 FastAPI 的 Request/Response 对象。
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    async def generate_answer(self, message: str) -> str:
        """根据用户消息生成答案。

         
        """
        messages = [
        {"role": "user", "content": message}
        ]

        answer = await self.llm_client.generate(messages)
        return answer
