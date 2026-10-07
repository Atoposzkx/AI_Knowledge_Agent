# AI Knowledge Agent

一个用于学习 FastAPI 分层开发的单轮聊天后端。V1 已实现请求校验、
模型调用封装、异常转换、依赖注入、资源生命周期管理、日志和自动化测试。

```text
POST /chat
→ FastAPI 使用 ChatRequest 校验请求
→ Router 调用 ChatService
→ Service 组织消息，交给 LLMClient
→ Client 调用模型 API，提取答案
→ Router 返回 ChatResponse
```

当前不包含知识库检索（RAG）、多轮记忆、流式响应、工具调用和用户认证。

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
