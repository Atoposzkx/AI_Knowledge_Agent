"""集中管理应用配置。

TODO（接入真实 LLM 前实现）：
- 使用 pydantic-settings 读取环境变量；
- 定义 LLM_API_KEY、LLM_MODEL 等配置；
- 只在这里处理配置，不在 Router 或 Service 中散落 os.getenv 调用。
"""
