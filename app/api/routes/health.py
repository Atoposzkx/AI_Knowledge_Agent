"""应用健康检查接口。"""

from fastapi import APIRouter


router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """供开发环境或部署平台确认 API 进程是否正常运行。"""
    return {"status": "ok"}
