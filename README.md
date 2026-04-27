# Agents

一个手搓的智能体系统框架。项目按“核心智能体系统 + 后端网关 + 两个界面”组织：

- `agent/`：智能体核心系统，不依赖 FastAPI，也不属于某个界面。
- `gateway/`：后端网关，负责 HTTP API、鉴权、中间件、SSE、服务生命周期和 Web 静态产物挂载。
- `cli/`：终端界面，复用 `agent/` 核心能力。
- `web/`：浏览器界面，使用 SolidJS + Vite，通过 gateway HTTP API 交互。

## 能力概览

- **Agent Runtime**：非流式与流式对话、prompt 编译、工具调用循环、上下文窗口、工具权限策略、检查点恢复。
- **多模型 Provider**：OpenAI Chat Completions、OpenAI Responses、Claude Messages、Gemini。
- **Provider 基础设施**：provider alias、base URL 归一化、HTTPX transport、SSE 解析、错误分类、429/5xx/timeout 重试。
- **工具系统**：`ToolRegistry` 管理工具 schema、执行、超时和结果格式。
- **MCP 工具接入**：通过 stdio 启动 MCP Server，并注册为 `mcp_<server>_<tool>`。
- **Hook 扩展点**：`before_request`、`after_response`、`format_tool_result`、`on_error`，支持组合、意图引导、thinking 提取和审批拦截。
- **多智能体预留边界**：`agent/orchestration`、`agent/memory`、`agent/workflows` 已作为后续 planner/router/supervisor、记忆和 DAG 工作流边界。
- **Gateway 网关边界**：`gateway/auth`、`gateway/sessions`、`gateway/streaming` 预留鉴权、run/session 状态和协议流式输出层。

## 目录结构

```text
.
├── agent/                   # 智能体核心系统
│   ├── hooks/               # Runtime hook 基类、组合、意图引导、thinking、审批
│   ├── memory/              # session memory / long-term memory 边界
│   ├── orchestration/       # 多智能体 planner/router/supervisor 边界
│   ├── providers/           # ModelClient、adapters、transport、retry、stream、errors
│   ├── runtime/             # Agent loop、state、prompt、session、compaction、tool orchestration、permissions、checkpoints
│   ├── tools/               # ToolRegistry 与 MCP stdio 工具接入
│   ├── workflows/           # workflow / DAG 执行边界
│   ├── factory.py           # 从 settings 组装 AgentSession
│   ├── schema.py            # Message、ToolCall、ModelRequest、RuntimeEvent 等核心类型
│   └── skills.py            # skill manifest、prompt fragment、工具名声明加载
├── gateway/                 # 后端网关
│   ├── api/                 # FastAPI routes、schemas、Agent HTTP API
│   ├── auth/                # 鉴权/授权边界
│   ├── core/                # 配置、日志、中间件、异常
│   ├── engines/             # 可注册引擎生命周期管理
│   ├── sessions/            # run/session 状态边界
│   ├── shared/              # FastAPI 注册器、统一响应、请求 ID、Provider 基类
│   ├── streaming/           # SSE / future WebSocket 协议边界
│   ├── utils/               # 终端样式、通用函数、ID、Registry
│   ├── app.py               # FastAPI 应用工厂和 lifespan
│   └── static_ui.py         # /ui 静态构建产物挂载
├── cli/                     # 终端界面
│   └── main.py              # Typer CLI，包含 chat 命令
├── web/                     # 浏览器界面（SolidJS + Vite）
│   ├── src/
│   └── dist/                # `npm run build` 输出，gateway 挂载到 /ui/
├── deploy/                  # Docker / Compose
├── docs/                    # 架构文档
├── tests/                   # 测试用例
├── main.py                  # gateway 启动入口
├── makefile                 # 常用命令
└── pyproject.toml           # 包与命令配置
```

## 快速开始

```bash
make setup

cp .env.example .env
# 编辑 .env，填入至少一个 provider 的 API_KEY 和 MODEL

make run
```

健康检查：

```bash
curl http://127.0.0.1:8010/health
```

## 常用命令

| 命令 | 说明 |
|---|---|
| `make setup` | 安装 Python + 前端依赖 |
| `make run` | 启动 gateway 后端服务 |
| `make cli` | 启动终端对话界面 |
| `make dev-web` | 同时启动后端和前端 dev server |
| `make test` | 运行测试 |
| `make build` | Docker 构建镜像 |
| `make up` / `make down` | Docker Compose 启停 |
| `make log` | 查看 Compose 服务日志 |

包入口：

```bash
agents chat --provider openai-chat --model gpt-4o
python -m cli.main chat
python main.py
```

## 调用入口

- `python main.py`：启动 gateway FastAPI 服务。
- `python -m cli.main chat`：启动终端界面，直接复用 `agent/` 核心能力。
- `POST /api/v1/agent/chat`：非流式 Agent 对话。
- `POST /api/v1/agent/chat/stream`：SSE 流式 Agent 对话。
- `GET /health`：健康检查。
- `POST /callback`：通用回调测试入口。

## HTTP API

非流式：

```bash
curl -X POST http://127.0.0.1:8010/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "hello",
    "provider": "openai-chat",
    "model": "gpt-4o"
  }'
```

流式：

```bash
curl -N -X POST http://127.0.0.1:8010/api/v1/agent/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'
```

请求体支持覆盖 `provider`、`model`、`base_url`、`api_key`、`system_prompt` 和 `enabled_tools`。

## Web UI

```bash
cd web && npm run build
make run
```

构建产物存在于 `web/dist/` 时，gateway 会把 `/` 重定向到 `/ui/`，并挂载静态界面。

开发模式：

```bash
make dev-web
```

## 配置说明

配置入口是 `gateway.core.config.settings`。内部按 domain 聚合：

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

## Agent 调用链

1. gateway API 或 CLI 调用 `agent.factory.create_agent_session`。
2. Factory 解析 provider/model/base_url/api_key，创建 `ModelClientConfig`。
3. Factory 创建 `ToolRegistry`，读取 skill manifests，把 skill prompt 拼进 system prompt，并把 skill 声明的工具名并入 runtime enabled tools。
4. Factory 把 MCP tools 注册进工具表，根据 `AGENT_GUIDED_TOOLS` 创建 `AgentHooks`，再组装 `AgentRuntime` 和 `AgentSession`。
5. `AgentSession` 维护消息历史，并通过 `ContextWindowManager` 保持上下文窗口。
6. `AgentRuntime` 使用 `RuntimeState` 跟踪消息、事件、工具结果和 pending tool calls。
7. `PromptCompiler` 生成模型请求；`ToolOrchestrator` 执行工具调用，并通过 `ToolPermissionPolicy` 判断工具是否可执行。
8. 可选 `CheckpointStore` 在模型响应、工具结果、完成和错误节点保存检查点，用于从 pending tool calls 恢复。
9. `ModelClient` 选择 provider adapter，经 `HttpxModelTransport` 发起请求，并按 retry policy 处理 429、5xx 和 timeout。

## 扩展方向

1. 新增模型 Provider：在 `agent/providers/adapters/` 添加 adapter，并注册到 `adapter_for_provider()`。
2. 新增工具：通过 `ToolRegistry.register()` 注册；skill manifest 只声明 prompt fragment 和工具名。
3. 新增 MCP 工具：配置 `MCP_SERVER_COMMAND`，由 `MCPToolProvider` 自动加载远端工具。
4. 新增工具权限策略：实现 `ToolPermissionPolicy`，注入 `AgentRuntime`。
5. 新增断点恢复存储：实现 `CheckpointStore`，注入 `AgentRuntime`。
6. 新增多智能体能力：放入 `agent/orchestration/`，保持对 gateway transport 无依赖。
7. 新增记忆能力：放入 `agent/memory/`，由 runtime/orchestration 调用。
8. 新增工作流能力：放入 `agent/workflows/`，用于 DAG、计划执行和多步骤任务。
9. 新增后端协议能力：放入 `gateway/auth/`、`gateway/sessions/` 或 `gateway/streaming/`。
