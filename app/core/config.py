"""集中管理应用配置。

配置职责（已实现）：
- 使用 pydantic-settings 读取环境变量；
- 定义 LLM_API_KEY、LLM_MODEL 等配置；
- 只在这里处理配置，不在 Router 或 Service 中散落 os.getenv 调用。
"""
#.env是纸上的配置，Settings() 把它读成 Python 对象；SecretStr 防止日常打印时直接显示密钥，但不是加密。
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    llm_api_key: SecretStr
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-flash"
    # 网络操作超时，不是整个 /chat 的总时长上限。
    llm_timeout_seconds: float = Field(default=60.0, gt=0)
    llm_max_retries: int = Field(default=0, ge=0)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
