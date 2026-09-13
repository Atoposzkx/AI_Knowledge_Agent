"""聊天接口的数据模型。"""

from pydantic import BaseModel, Field,field_validator


class ChatRequest(BaseModel):
    """POST /chat 接收的 JSON 数据。"""
  
    # 最小长度避免空字符串；最大长度防止一次请求无限增大。
    #Field 是 Pydantic 提供的字段配置工具。用来为类属性（字段）设置默认值、添加描述、以及提供数据验证和元数据约束
    #数据验证库 Pydantic 中，pydantic.Field 是最常用的函数之一，它和 BaseModel 配合使用。它可以帮我们在声明字段类型的同时，做更精细的限制
    message: str = Field(min_length=1, max_length=10_000,description="用户发送的聊天消息")
    #这个下面是处理消息前后的空字符串
    #装饰器，不直接修改函数内部代码，而是在函数外面给它增加身份或功能。装饰器本质上是：把一个函数交给另一个函数处理，再把处理后的结果重新赋值回来。
    #这个函数专门处理 message，而且要在正式校验前执行
    @field_validator("message",mode="before")
    @classmethod #把下面这个函数变成“类方法，个方法属于 ChatRequest 这个类，而不是某一个具体的 ChatRequest 对象。
    #cls 代表 ChatRequest 类本身
    def strip_message(cls,value:object)->object:
        '''校验长度前，删除消息首尾的空白字符。'''
        if isinstance(value,str):
            return value.steip()
        return value

class ChatResponse(BaseModel):
    """POST /chat 成功时返回的 JSON 数据。"""

    answer: str
