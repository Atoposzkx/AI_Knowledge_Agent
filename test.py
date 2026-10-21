from app.clients.llm_client import LLMClient
import asyncio
from pydantic import ValidationError
from app.clients.llm_client import LLMClient
from typing import Literal
from pydantic import BaseModel, Field
from app.core.config import settings
'''

messages_a = [
    {
        "role":"user",
        "content":"什么是Python装饰器"
    }
]

messages_b = [
    {
        "role": "developer",
        "content": "你是一名 Python 教师，请用一句话回答，不要给代码。",
    },
    {
        "role": "user",
        "content": "什么是 Python 装饰器？",
    },
]

messages_c = [
    {
        "role":"user",
        "content":"我刚开始学 Python，请用生活中的例子解释概念。",
    },
    {
        "role":"assistant",
        "content":"好的，我会优先使用生活中的类比来解释 Python 装饰器的概念。",
    },
    {
        "role":"user",
        "content":"什么是 Python 装饰器？",
    }
]


# 你原来的导入和三个 messages 列表保留

async def main():
    client = LLMClient()
    try:
        print("=== messages_a ===")
        answer_a = await client.generate(messages_a)
        print(answer_a)
        print("=== messages_b ===")
        answer_b = await client.generate(messages_b)
        print(answer_b)
        print("=== messages_c ===") 
        answer_c = await client.generate(messages_c)
        print(answer_c)

        # 请你按同样方式补上 messages_b 和 messages_c
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())

'''


class NoteAnalysis(BaseModel):
    summary: str = Field(min_length=1, max_length=200)
    keywords: list[str] = Field(min_length=1, max_length=5)
    difficulty: Literal["easy", "medium", "hard"]

data = {
    "summary": "Python 装饰器基础",
    "keywords": ["decorator", "wrapper"],
    "difficulty": "beginner"
}
bad_json = {
    "summary": "Python 装饰器基础",
    "keywords": [],
    "difficulty": "beginner"
}


""" 
model_validate() 方法会根据 NoteAnalysis 的定义对 data 进行验证。如果 data 不符合模型的要求，它会抛出 ValidationError 异常。你可以捕获这个异常并打印错误信息，以便了解验证失败的原因。
"""
""" try:
     result = NoteAnalysis.model_validate(bad_json)
except ValidationError as exc:
     print(str(exc))
     print(exc.errors())  """

"""
model_json_schema() 方法会生成 NoteAnalysis 模型的 JSON Schema。JSON Schema 是一种用于描述 JSON 数据结构的规范，它可以帮助你理解模型的字段、类型和约束条件。你可以打印这个 JSON Schema 来查看模型的定义。
schema = NoteAnalysis.model_json_schema()
print(schema)
"""
messages = [
    {
        "role": "user",
        "content": (
            "请分析以下 Python 学习笔记，"
            "提取摘要、关键词和学习难度："
            "Python 装饰器可以在不修改原函数代码的前提下，"
            "为函数添加额外功能，常见于日志、权限校验和性能统计。"
        ),
    }
]
'''
async def main():
    llm_client = LLMClient()

    try:
        schema = NoteAnalysis.model_json_schema()

        response = await llm_client.client.responses.create(
            model=settings.llm_model,
            input=messages,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "note_analysis",
                    "schema": schema,
                }
            },
        )
        result = NoteAnalysis.model_validate_json(response.output_text)
        print(type(result))
        print(result.keywords)
    finally:
        await llm_client.close()


if __name__ == "__main__":
    asyncio.run(main())
'''

class NoteAnalysisService:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    async def analyze(self, note_text: str) -> NoteAnalysis:
        # 1. 根据业务模型生成 Schema
        schema = NoteAnalysis.model_json_schema()

        # 2. 构造消息
        messages = [
            {
                "role": "user",
                "content": "请分析以下学习笔记：" + note_text,
            }
        ]

        # 3. 调用你自己封装的 LLMClient
        raw_json = await self.llm_client.generate_structured(
            messages=messages,
            schema=schema,
        )

        # 4. 使用 Pydantic 解析与校验
        result = NoteAnalysis.model_validate_json(raw_json)

        # 5. 返回业务对象
        return result

async def main():
    llm_client = LLMClient()

    try:
        service = NoteAnalysisService(llm_client)

        result = await service.analyze(
            "Python 装饰器能够在不修改原函数代码的前提下，"
            "为函数增加日志记录、权限校验等功能。"
        )

        print(result)
        print(type(result))
        print(result.summary)
    finally:
        await llm_client.close()


if __name__ == "__main__":
    asyncio.run(main())