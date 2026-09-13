# AI Knowledge Agent

V1 的目标是建立一条清晰、可测试的聊天请求链路：

```text
POST /chat -> Router -> Schema -> Service -> LLM Client -> LLM API
```

当前状态：项目框架已建立，`GET /health` 可用，`POST /chat` 暂时返回
`501 Not Implemented`。
