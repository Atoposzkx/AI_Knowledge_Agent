"""LLM 客户端抽象。

这个模块负责隐藏具体厂商 SDK 的调用方式，让 Service 不必知道底层使用
OpenAI、其他云模型还是本地模型。
"""


class LLMClient:
    """调用大语言模型的统一入口。"""

    async def generate(self, messages: list[dict[str, str]]) -> str:
        """把消息发送给模型，并返回文本答案。

        TODO（接入真实 LLM 时实现）：
        1. 从配置中读取 API Key 和模型名；
        2. 调用模型 SDK；
        3. 处理超时、认证失败和限流；
        4. 从厂商响应中提取最终文本。
        """
        raise NotImplementedError
