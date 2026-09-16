"""应用自己的异常类型，供 Client 和 Router 共用。"""


class LLMTimeoutError(Exception):
    """调用大语言模型服务超时。"""
