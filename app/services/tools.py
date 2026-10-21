"""仅执行白名单中的只读函数，不执行模型生成的 Python。"""
import json
import logging
from typing import Annotated
from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

logger = logging.getLogger(__name__)
GLOSSARY = {
    "rag": "RAG（检索增强生成）：先检索相关资料，再将资料作为上下文交给模型生成回答。",
    "tool calling": "工具调用：模型提出函数名称与参数，由应用校验执行，并把结果回传模型。",
    "structured output": "结构化输出：按约定的数据结构生成结果，应用仍需验证格式与业务语义。",
}

class LookupArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    term: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


def lookup_concept(term: str) -> dict:
    definition = GLOSSARY.get(term.casefold())
    return {"found": definition is not None, "definition": definition}


class ToolRegistry:
    def __init__(self):
        self._tools = {"lookup_concept": (LookupArguments, lookup_concept)}

    def definitions(self) -> list[dict]:
        return [{"type": "function", "name": "lookup_concept",
                 "description": "查询本地 AI 术语表，支持 RAG、Tool Calling、Structured Output；不存在时返回 found=false。",
                 "parameters": LookupArguments.model_json_schema(), "strict": True}]

    def execute(self, name: str, arguments: str) -> dict:
        if name not in self._tools:
            logger.warning("tool_unknown")
            return {"ok": False, "error": "unknown_tool"}
        model, handler = self._tools[name]
        try:
            if not isinstance(arguments, str) or len(arguments) > 4000:
                raise ValueError("invalid arguments")
            params = model.model_validate_json(arguments)
        except (ValidationError, ValueError):
            logger.warning("tool_invalid_arguments")
            return {"ok": False, "error": "invalid_arguments"}
        try:
            result = handler(**params.model_dump())
            json.dumps(result, allow_nan=False)
        except Exception:
            # 不向模型或日志暴露异常原文和参数。
            logger.warning("tool_execution_failed")
            return {"ok": False, "error": "tool_execution_failed"}
        logger.info("tool_success")
        return {"ok": True, "result": result}
