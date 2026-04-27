# Agents

Python Agent 服务框架，提供 FastAPI HTTP 服务、Typer 终端 CLI、SolidJS Web UI、多模型 Provider 适配、工具调用 Runtime、MCP 工具接入和可组合 Hook 扩展。

## 能力概览

- **HTTP 与 CLI 双入口**：`main.py` / `app.app` 启动 FastAPI，`app.cli` 提供 `run` 和 `chat` 命令。
- **Agent Runtime**：支持非流式与 SSE 流式对话、工具调用循环、上下文截断、工具并发限制和请求并发限制。
- **多模型 Provider**：OpenAI Chat Completions、OpenAI Responses、Claude Messages、Gemini 统一为 `ModelClient` 接口。
- **Provider 基础设施**：provider alias 归一化、base URL 清理、HTTPX transport、SSE 解析、错误分类、429/5xx/timeout 重试退避。
- **工具系统**：`ToolRegistry` 管理本地工具，支持超时、并发执行和工具结果统一格式化。
- **MCP 工具接入**：通过 stdio 启动 MCP Server，把远端 MCP tools 注册为 `mcp_<server>_<tool>`。
- **Hook 扩展点**：`before_request`、`after_response`、`format_tool_result`、`on_error` 可组合扩展；内置意图引导、thinking 提取、审批拦截基础类。
- **Web UI**：`web/` 使用 SolidJS + Vite，构建产物位于 `web/dist/`，后端存在构建产物时挂载到 `/ui/`。
- **核心基础设施**：`app.core` 统一承接配置、日志、中间件和异常定义，`app.shared.server` 保留 FastAPI 注册与响应封装。

## 目录结构

```text
.
├── app/
│   ├── agent/               # Agent Runtime、schema、provider、tool、skill、hook
│   │   ├── hooks/           # Runtime Hook 基类、组合、意图引导、thinking、审批
│   │   ├── providers/       # ModelClient、adapters、transport、retry、stream、errors
│   │   └── tools/           # ToolRegistry 与 MCP stdio 工具接入
│   ├── api/                 # FastAPI 路由、请求模型、Agent HTTP API
│   ├── core/                # 配置聚合、日志、中间件、异常
│   │   └── config/          # server / agent / models / mcp / log 分域配置
│   ├── engines/             # 可注册引擎生命周期管理
│   ├── services/            # 服务编排预留层
│   ├── shared/              # FastAPI 注册器、统一响应、请求 ID、Provider 基类
│   ├── utils/               # 终端样式、通用函数、ID、Registry
│   ├── app.py               # FastAPI 应用工厂和 lifespan
│   ├── cli.py               # Typer CLI 入口
│   └── web.py               # /ui 静态文件挂载
├── web/                     # 前端源码和构建产物（SolidJS + Vite）
│   ├── src/                 # Conversation Studio 前端
│   └── dist/                # `npm run build` 输出，后端挂载到 /ui/
├── deploy/                  # Docker / Compose
├── docs/                    # 架构文档
├── tests/                   # 测试用例
├── main.py                  # 服务启动入口
├── makefile                 # 常用命令
└── pyproject.toml           # 项目配置
```

## 快速开始

```bash
# 1. 安装所有依赖（Python + 前端）
make setup

# 2. 配置模型
cp .env.example .env
# 编辑 .env，填入至少一个 provider 的 API_KEY 和 MODEL

# 3. 启动后端服务
make run
```

健康检查：

```bash
curl http://127.0.0.1:8010/health
```

## 常用命令

| 命令 | 说明 |
|---|---|
| `make setup` | 安装 Python + 前端所有依赖 |
| `make run` | 启动后端服务 |
| `make cli` | 启动终端对话窗口 |
| `make dev-web` | 同时启动后端 + 前端 dev server |
| `make stop` | 手动停止后台后端进程 |
| `make test` | 运行测试 |
| `make build` | Docker 构建镜像 |
| `make up` / `make down` | Docker Compose 启停 |
| `make log` | 查看 Compose 服务日志 |

也可以通过包入口启动：

```bash
agents run
agents chat --provider openai-chat --model gpt-4o
```

## 运行入口

- `python main.py`：读取 `settings.server` 并启动 uvicorn。
- `python -m app.cli run`：通过 Typer 启动 FastAPI。
- `python -m app.cli chat`：启动本地终端对话，直接创建 `AgentSession`。
- `POST /api/v1/agent/chat`：非流式 Agent 对话。
- `POST /api/v1/agent/chat/stream`：SSE 流式 Agent 对话。
- `GET /health`：健康检查。
- `POST /callback`：通用回调测试入口。

## 终端对话

在 `.env` 中配置模型：

```bash
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

启动：

```bash
make cli
```

可用 CLI 覆盖本次会话配置：

```bash
python -m app.cli chat \
  --provider openai-chat \
  --model gpt-4o \
  --base-url https://api.openai.com/v1
```

对话内支持 `/clear` 清空上下文，`/exit` 或 `/quit` 退出。

## HTTP API

非流式请求：

```bash
curl -X POST http://127.0.0.1:8010/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "hello",
    "provider": "openai-chat",
    "model": "gpt-4o"
  }'
```

流式请求：

```bash
curl -N -X POST http://127.0.0.1:8010/api/v1/agent/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'
```

请求体支持覆盖 `provider`、`model`、`base_url`、`api_key`、`system_prompt` 和 `enabled_tools`。

## Web UI

构建前端：

```bash
cd web && npm run build
```

然后启动后端，`app.web` 会检测 `web/dist/`，存在时自动把 `/` 重定向到 `/ui/`，并挂载静态 UI。

开发模式（前后端同时启动）：

```bash
make dev-web
```

## 配置说明

配置入口是 `app.core.config.settings`。内部按 domain 聚合配置对象：

| Domain | 环境变量前缀 | 示例 |
|---|---|---|
| `settings.server` | 无 | `DEBUG`, `PROJECT_NAME`, `API_PREFIX`, `HOST`, `PORT`, `WORKERS`, `ACCESS_TOKEN` |
| `settings.agent` | `AGENT_` | `AGENT_PROVIDER`, `AGENT_MAX_TOKENS`, `AGENT_MAX_RETRIES`, `AGENT_ENABLED_TOOLS`, `AGENT_GUIDED_TOOLS` |
| `settings.models.openai` | `OPENAI_` | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` |
| `settings.models.openai_responses` | `OPENAI_RESPONSES_` | `OPENAI_RESPONSES_API_KEY`, `OPENAI_RESPONSES_MODEL` |
| `settings.models.anthropic` | `ANTHROPIC_` | `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` |
| `settings.models.gemini` | `GEMINI_` | `GEMINI_API_KEY`, `GEMINI_MODEL` |
| `settings.mcp` | `MCP_` | `MCP_SERVER_NAME`, `MCP_SERVER_COMMAND`, `MCP_CLIENT_TIMEOUT` |
| `settings.log` | 无 | `LOG_LEVEL`, `LOG_PATH` |

Provider 标准名：

| Provider | 说明 | 主要配置 |
|---|---|---|
| `openai-chat` | OpenAI Chat Completions | `OPENAI_*` |
| `openai-responses` | OpenAI Responses API | `OPENAI_RESPONSES_*`，缺省回退到 `OPENAI_*` |
| `claude-messages` | Anthropic Claude Messages | 优先 `AGENT_CLAUDE_*`，再回退到 `ANTHROPIC_*` |
| `gemini` | Gemini Generate Content | `GEMINI_*` |

Provider 支持别名归一化，例如 `openai`、`chat`、`responses`、`anthropic`、`claude`、`google`、`gemini-generate-content`。

## Agent 调用链

1. API 或 CLI 调用 `app.agent.factory.create_agent_session`。
2. Factory 解析 provider/model/base_url/api_key，创建 `ModelClientConfig`。
3. Factory 创建 `ToolRegistry`，读取 skill manifests，并把 MCP tools 注册进工具表。
4. Factory 根据 `AGENT_GUIDED_TOOLS` 创建 `AgentHooks`，再组装 `AgentRuntime` 和 `AgentSession`。
5. `AgentSession` 维护消息历史，并按 `AGENT_MAX_CONTEXT_TOKENS` 截断旧轮次。
6. `AgentRuntime` 在每轮请求前后执行 hooks，调用模型，执行工具调用，返回 `AgentResult` 或流式 `RuntimeEvent`。
7. `ModelClient` 选择 provider adapter，经 `HttpxModelTransport` 发起请求，并用 retry policy 处理 429、5xx 和 timeout。

## 工具、MCP 与 Hooks

启用本地工具时，把工具名写入 `AGENT_ENABLED_TOOLS`，或在 HTTP 请求中传 `enabled_tools`。`ToolRegistry` 会按工具名暴露 schema，并并发执行模型返回的 tool calls。

配置 MCP stdio server：

```bash
MCP_SERVER_NAME=filesystem
MCP_SERVER_COMMAND="node /path/to/server.js"
```

MCP 工具会注册为 `mcp_filesystem_<tool_name>`。

配置意图引导：

```bash
AGENT_GUIDED_TOOLS=weather:天气,温度;search:搜索,查找
```

当最近一条用户消息命中关键词时，`IntentGuidanceHooks` 会在请求前插入工具使用提示。

## 服务基础设施

- `app.core.logging`：项目 logger、相对路径 formatter、文件与 stdout 双输出。
- `app.core.middleware`：CORS 与可选 Bearer token 鉴权；设置 `ACCESS_TOKEN` 后只保护 `API_PREFIX` 下的接口。
- `app.core.exceptions`：服务异常与认证异常定义。
- `app.shared.server.register`：注册 middleware、exception handler 和请求/响应 hook。
- `app.shared.server.common`：统一响应结构、请求 ID 依赖和基础依赖函数。
- `app.engines`：引擎注册与生命周期管理，目前作为后续能力扩展层。

## 扩展模块

1. 新增 HTTP 能力：在 `app/api/<module>/` 添加 schemas 和 router，并在 `app/api/router.py` 挂载。
2. 新增 Agent 工具：通过 `ToolRegistry.register()` 注册工具；`app/agent/skills.py` 负责 skill manifest、prompt fragment 和工具名声明加载。
3. 新增 MCP 工具：配置 `MCP_SERVER_COMMAND`，由 `MCPToolProvider` 自动加载远端工具。
4. 新增 Provider：在 `app/agent/providers/adapters/` 添加 adapter，并在 `adapter_for_provider()` 注册。
5. 新增 Runtime 行为：继承 `AgentHooks`，必要时用 `CompositeHooks` 组合多个 hook。
6. 新增服务基础设施：优先放入 `app.core`，`app.shared.server` 只保留 FastAPI 注册和跨模块复用封装。
7. 新增测试：按行为补充 `tests/test_agent_*`、`tests/test_health.py` 或前端结构测试。
