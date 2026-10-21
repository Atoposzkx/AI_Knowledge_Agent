# AI Knowledge Agent

一个分层实现的 AI 学习助手后端。V2 新增结构化笔记分析和原生工具调用。V1 已实现请求校验、
模型调用封装、异常转换、依赖注入、资源生命周期管理、日志和自动化测试。

```text
POST /chat
→ FastAPI 使用 ChatRequest 校验请求
→ Router 调用 ChatService
→ Service 组织消息，交给 LLMClient
→ Client 调用模型 API，提取答案
→ Router 返回 ChatResponse
```

当前不包含知识库检索（RAG）、长期记忆、流式响应和用户认证。
V2 显式历史仅随请求传入，不在服务端保存。

## 项目结构

```text
app/
├── main.py                  # 创建应用、注册路由、管理启动与关闭
├── api/routes/
│   ├── health.py            # 健康检查
│   └── chat.py              # 聊天接口、服务依赖、HTTP 错误映射
├── schemas/chat.py          # 请求与响应的数据模型
├── services/chat_service.py # 组织模型消息、调用客户端
├── clients/llm_client.py    # SDK 调用、答案检查、SDK 异常转换
└── core/
    ├── config.py            # 环境变量与 .env 配置
    ├── exceptions.py        # 项目自己的模型异常
    └── logging.py           # 日志配置及学习说明
tests/
├── conftest.py              # 公共测试配置、阻止误调用真实模型
├── test_health.py           # 健康检查测试
├── test_chat.py             # HTTP 行为与依赖替换测试
├── test_llm_client.py       # 模型客户端测试
└── test_lifespan.py         # 资源复用与关闭测试
```

启动时，`lifespan` 创建客户端和服务，将服务保存到 `app.state.chat_service`。
路由通过 `Depends(get_chat_service)` 取得这个对象；同一次应用运行期间复用
客户端，关闭时调用 `close()`。再次启动时创建新的客户端。

代码中保留了学习注释，以及用多行字符串保存的旧测试；旧测试不会执行。

## 安装与配置

需要 Python 3.13 或更高版本，以及已安装的 uv。以下命令均在项目根目录执行。

安装应用和测试依赖：

```bash
uv sync --locked --dev
```

首次配置时，将 `.env.example` 复制为 `.env`；已有 `.env` 时直接编辑它。
以下命令在 macOS/Linux 上避免覆盖已有文件：

```bash
cp -n .env.example .env
```

在 `.env` 中填写真实密钥，并确认模型地址和名称：

```dotenv
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-flash
LLM_TIMEOUT_SECONDS=60
LLM_MAX_RETRIES=0
```

以上地址和模型名是当前示例配置。Client 使用 OpenAI Python SDK 的
`responses.create()`；实际模型服务需要支持该请求格式，仅支持 Chat Completions
格式的服务需要调整 Client。请使用你已验证可用的地址和模型名称。

| 配置 | 用途 |
| --- | --- |
| `LLM_API_KEY` | 模型服务密钥，启动应用时必填 |
| `LLM_BASE_URL` | SDK 请求的模型服务地址 |
| `LLM_MODEL` | 请求使用的模型名称 |
| `LLM_TIMEOUT_SECONDS` | 网络操作超时秒数，必须大于 0；不是整个聊天请求的总时长上限 |
| `LLM_MAX_RETRIES` | SDK 自动重试次数，必须大于等于 0；当前默认不重试 |

`Settings()` 读取并验证配置；环境变量优先于 `.env`，未提供的可选字段使用
代码默认值。修改配置后需要重启应用。`.env` 已被 Git 忽略，真实密钥不要写入
代码、README 或提交记录。

## 启动应用

```bash
uv run uvicorn app.main:app --reload
```

打开 [交互式接口文档](http://127.0.0.1:8000/docs)，可以直接填写 JSON 并发送请求。
`--reload` 用于本地开发。终端按 `Ctrl+C` 关闭应用，触发生命周期中的资源清理。

## 接口使用

### GET /health

```bash
curl http://127.0.0.1:8000/health
```

返回 HTTP `200`：

```json
{"status": "ok"}
```

这是应用存活检查，不调用模型，也不验证模型服务、密钥或模型名称是否可用。
但应用本身仍需要配置才能启动。

### POST /chat

```bash
curl -i http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"请用简单语言解释什么是 RAG"}'
```

成功时返回 HTTP `200`，响应格式如下（答案内容由模型生成）：

```json
{"answer": "这里是模型生成的回答"}
```

`message` 是必填字符串。首尾空白会先被删除，处理后的长度必须为
1～10,000 个字符。每次请求只携带这一条消息，不保留之前的聊天历史。

## 错误响应

| HTTP 状态码 | 情况 | 返回说明 |
| --- | --- | --- |
| `422` | 请求校验失败，例如缺少 message、空白消息或长度超限 | FastAPI 的字段校验详情 |
| `502` | 模型答案不可用 | 模型返回了不可用的响应，请稍后再试 |
| `502` | 上游返回错误 HTTP 响应 | 模型服务请求失败，请稍后再试 |
| `503` | 无法连接模型服务 | 暂时无法连接模型服务，请稍后再试 |
| `504` | 模型调用超时 | 等待模型回答超时，请稍后再试 |

模型调用错误使用统一的响应结构，例如：

```json
{"detail": "等待模型回答超时，请稍后再试"}
```

Client 将 SDK 异常转换成自定义异常，Router 再转换成 HTTP 响应。
上游的认证失败、限流等错误在当前 V1 中统一映射为 `502`，不会直接照搬
上游状态码；例如上游 `401` 不表示本接口用户未登录。
未被明确处理的程序异常仍可能返回 `500`。

## 自动化测试

运行全部测试：

```bash
uv run python -m pytest -v
```

单独运行 Client 测试：

```bash
uv run python -m pytest tests/test_llm_client.py -v
```

测试不需要真实模型密钥。`conftest.py` 在导入应用前提供假配置，并通过
自动 fixture 拦截 SDK 的 `request()`：忘记替换模型调用时立即失败。
正确 Mock 的测试不会走到这个拦截方法；这不是对整个进程网络访问的禁用。

测试分别验证 HTTP 请求校验与错误映射、依赖替换、Client 的答案处理与异常转换，
以及生命周期内的资源复用、关闭和再次创建。它们使用可控的假模型行为，
通过这些测试不代表真实上游服务当前可用。

## 日志与本地验收

应用日志输出到终端，包含时间、级别、模块来源和消息。
`main.py` 记录启动与关闭，Client 记录模型调用结果、耗时及上游错误状态码。
这些应用日志不主动记录密钥、用户消息或上游响应原文。
详细的日志学习说明位于 `app/core/logging.py`。

本地验收顺序：

1. 启动应用，确认出现 `application_started` 日志。
2. 请求 `/health`，确认 HTTP `200` 和 `{"status":"ok"}`。
3. 在 `/docs` 发送正常聊天消息，确认 HTTP `200` 和非空 `answer`；这一步会调用真实模型。
4. 分别发送 `{}` 和 `{"message":"   "}`，确认 HTTP `422`。
5. 按 `Ctrl+C` 关闭，确认出现 `application_stopped` 日志。
6. 运行全部自动化测试，确认通过。


## V2 接口

继续使用上述安装、配置和启动方式，在 `/docs` 可查看所有请求模型。
开发在 `v2` 分支，暂不合并 `main`。

### POST /notes/analyze

```json
{"note_text":"Python 装饰器在不修改原函数代码的前提下，为函数添加日志记录等功能。"}
```

返回经过 Pydantic 校验的对象，例如：

```json
{"summary":"装饰器可为函数添加日志功能。","keywords":["装饰器","日志"],"difficulty":"easy"}
```

摘要 1～200 字符；关键词 1～5 项，每项非空且不重复；难度为 easy、medium、hard。
笔记去除首尾空白后为 1～10,000 字符。格式校验不能保证内容真实。

### POST /chat/tools

```json
{"message":"请调用工具查询 RAG 并解释它。","history":[]}
```

返回 `answer` 和 `tool_results`。每个工具结果包含 `call_id`、`name`、`ok` 及
`result` 或 `error`；无需工具时 `tool_results` 为空。工具仅查询本地 AI 术语表，
包含 RAG、Tool Calling、Structured Output，没有联网搜索或真正的知识库检索。

history 可含最多 12 条 user/assistant 消息，每条非空且最多 10,000 字符；message
也为 1～10,000 字符，历史与当前问题总计不超过 20,000 字符。应用字符上限不等于模型
的 token 窗口。客户端须自行携带历史，不允许通过 history 注入 developer/system 角色。

工具最多执行一批（最多四个），再请求最终回答；不运行自主 Agent 循环。
未知工具、参数非法和工具执行异常作为结构化错误回传；批次异常、无效结构化输出、
拒绝、未完成响应或上游错误映射 502，连接失败 503，超时 504，输入不合法 422。
新功能和 V1 共享生命周期中的客户端。

### 验证与限制

```bash
uv run python -m pytest -q
```

正式测试仅收集 `tests/`，不会运行你保留的 `test.py` 实验或真实验收脚本。
真实提供商验收需显式开启，可能产生费用：

```bash
LLM_MAX_RETRIES=0 uv run python -m scripts.verify_v2 --live
```

本次交付仅执行离线测试，真实工具闭环尚待上述命令与人工核对。实际服务必须同时支持
Responses、严格 JSON Schema 和 function calling；只兼容 Chat Completions 的服务
不能直接运行这些接口。未修改用户 `.env`，也没有自动更换提供商或静默降级。
SDK 重试由 LLM_MAX_RETRIES 控制，Service 不叠加重试；默认不重试。

详细的上下文实验、格式与语义区别、失败案例、验收步骤及 Streaming 待办见
[验证记录](docs/v2-validation.md)。协议依据
[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 和
[Function Calling](https://developers.openai.com/api/docs/guides/function-calling)，第三方兼容性需独立验证。
