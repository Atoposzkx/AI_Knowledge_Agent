"""应用自己的异常类型，供 Client 和 Router 共用。"""


class LLMTimeoutError(Exception):
    """调用大语言模型服务超时。
    如果只抛出普通的 Exception，Router 就很难仅凭类型判断这是模型超时、连接失败，还是其他问题。
所以这个类虽然没有自己定义方法，却做了两件事：
- 继承 Exception 已有的异常能力。
- 创建一个名字明确、可以单独捕获的新异常类型。
    
    """
    pass