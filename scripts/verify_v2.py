"""显式开启的真实提供商验收；pytest 不会执行此脚本。"""
import argparse
import asyncio


async def verify():
    # 确认 --live 后才读取模型配置和创建客户端。
    from app.clients.llm_client import LLMClient
    from app.core.exceptions import LLMConnectionError, LLMProviderError, LLMResponseError, LLMTimeoutError
    from app.schemas.tool_chat import ToolChatRequest
    from app.services.note_service import NoteAnalysisService
    from app.services.tool_chat_service import ToolChatService

    client = LLMClient()
    try:
        note = await NoteAnalysisService(client).analyze(
            "Python 装饰器在不修改原函数代码的前提下添加日志记录等功能。"
        )
        print("结构化结果本地校验通过：", note.model_dump_json())
        chat = await ToolChatService(client).answer(ToolChatRequest(
            message="请务必调用 lookup_concept 查询 RAG，再根据工具结果解释它。"
        ))
        if not chat.tool_results or not any(
            item.get("ok") and item.get("result", {}).get("found")
            for item in chat.tool_results
        ):
            print("工具闭环尚未通过：模型未成功执行概念查询。")
            return 1
        print("工具执行及结果回传通过：", chat.model_dump_json())
        print("请人工核对摘要是否忠于笔记、最终回答是否忠于工具结果；格式通过不代表事实正确。")
        return 0
    except (LLMConnectionError, LLMProviderError, LLMResponseError, LLMTimeoutError) as exc:
        print(f"验收失败：{type(exc).__name__}：{exc}")
        return 1
    finally:
        await client.close()


def main():
    parser = argparse.ArgumentParser(description="真实 V2 验收：会发送最多三次模型请求，可能产生费用；SDK 重试另计。")
    parser.add_argument("--live", action="store_true", help="明确允许使用当前 .env 配置调用真实模型")
    args = parser.parse_args()
    if not args.live:
        parser.error("需显式提供 --live 才会调用模型")
    raise SystemExit(asyncio.run(verify()))


if __name__ == "__main__":
    main()
