# Agents

一个手搓的智能体系统框架。项目按“核心智能体系统 + 后端网关 + 两个界面”组织：

- `agent/`：智能体核心系统，不依赖 FastAPI，也不属于某个界面。
- `gateway/`：后端网关，负责 HTTP API、鉴权、中间件、SSE、服务生命周期和 Web 静态产物挂载。
- `cli/`：终端界面，复用 `agent/` 核心能力。
- `web/`：浏览器界面，使用 SolidJS + Vite，通过 gateway HTTP API 交互。

## 能力概览

- **Agent Runtime**：非流式与流式对话、工具调用循环、运行状态、检查点恢复。
- **Context 系统**：按 system、runtime policy、workspace instructions、skills、memory、tool hints 分层拼装上下文，并保留 trace。
- **多模型协议**：OpenAI Chat Completions、OpenAI Responses、Claude Messages、Gemini。
- **Model 基础设施**：provider alias、base URL 归一化、HTTPX transport、SSE 解析、错误分类、429/5xx/timeout 重试。
- **工具系统**：`ToolRegistry` 管理工具 schema、执行、超时和结果格式。
- **MCP 工具接入**：通过 stdio 启动 MCP Server，并注册为 `mcp_<server>_<tool>`。
- **Hook 扩展点**：`before_request`、`after_response`、`format_tool_result`、`on_error`，支持组合、意图引导、thinking 提取和审批拦截。
- **多智能体预留边界**：`agent/orchestration`、`agent/memory`、`agent/workflows` 已作为后续 planner/router/supervisor、记忆和 DAG 工作流边界。
- **Gateway 网关边界**：`gateway/auth`、`gateway/sessions`、`gateway/streaming` 预留鉴权、run/session 状态和协议流式输出层。
- **SDK 装配入口**：`agent.assembly` 组装 AgentSession；`agent.config` 解析模型配置；`agent.integrations` 接入 skills/MCP。

## 目录结构

```text
.
├── agent/                   # 智能体核心系统
│   ├── hooks/               # Runtime hook 基类、组合、意图引导、thinking、审批
│   ├── assembly/            # AgentSession 组装入口，提供 sync/async 两种创建方式
│   ├── config/              # 模型配置解析、provider fallback、代理设置
│   ├── context/             # ContextPack、ContextBuilder、AGENTS.md、window、model request compiler
│   ├── identity/            # Principal、Tenant/User/Agent 引用
│   ├── integrations/        # skills / MCP 等外部能力接入装配
│   ├── memory/              # session memory / long-term memory 边界
│   ├── models/              # ModelClient、adapters、protocol、transports、retry、errors
│   ├── orchestration/       # 多智能体 planner/router/supervisor 边界
│   ├── runtime/             # Agent loop、state、session、events、turns、checkpoints
│   ├── security/            # permissions、approval、sandbox、secrets、encryption 边界
│   ├── skills/              # skill manifest、prompt fragment、工具名声明加载
│   ├── storage/             # workspace/run/memory/artifact store 边界
│   ├── tools/               # ToolRegistry 与 MCP stdio 工具接入
│   ├── workflows/           # workflow / DAG 执行边界
│   ├── factory.py           # 兼容入口，转发到 assembly/config/integrations
│   └── schema.py            # Message、ToolCall、ModelRequest、RuntimeEvent 等核心类型
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
| `settings.agent` | `AGENT_` | `AGENT_PROVIDER`, `AGENT_MAX_TOKENS`, `AGENT_MAX_RETRIES`, `AGENT_ENABLED_TOOLS`, `AGENT_GUIDED_TOOLS`, `AGENT_WORKSPACE_ROOT` |
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

1. gateway API 调用 `agent.factory.create_agent_session_async`；CLI 调用同步 `agent.factory.create_agent_session`。
2. `agent.config` 解析 provider/model/base_url/api_key，创建 `ModelClientConfig`。
3. `agent.assembly` 创建 `ToolRegistry`，通过 `agent.integrations` 读取 skill manifests 和 MCP tools。
4. `agent.storage` 根据 `tenant_id / user_id / agent_id / workspace_id` 解析 workspace，读取 workspace `AGENTS.md` 作为 project instructions。
5. `ContextPack` 汇总 system、runtime policy、workspace instructions、skills 和 tool hints，`ContextBuilder` 编译最终上下文并保留 trace。
6. `agent.integrations` 把 MCP tools 注册进工具表；`agent.assembly` 根据 `AGENT_GUIDED_TOOLS` 创建 `AgentHooks`，再组装 `AgentRuntime` 和 `AgentSession`。
7. `AgentSession` 维护消息历史，并通过 `ContextWindowManager` 保持上下文窗口。
8. `AgentRuntime` 使用 `RuntimeState` 跟踪消息、事件、工具结果和 pending tool calls。
9. `ModelRequestCompiler` 生成模型请求；`ToolOrchestrator` 执行工具调用，并通过 `ToolPermissionPolicy` 判断工具是否可执行。
10. 可选 `CheckpointStore` 在模型响应、工具结果、完成和错误节点保存检查点，用于从 pending tool calls 恢复。
11. `ModelClient` 选择 provider adapter，经 `HttpxModelTransport` 发起请求，并按 retry policy 处理 429、5xx 和 timeout。

## 扩展方向

1. 新增模型 Provider：在 `agent/models/adapters/` 添加 adapter，并注册到 `adapter_for_provider()`；通用 stream 语义放在 `agent/models/protocol/`。
2. 新增工具：通过 `ToolRegistry.register()` 注册；skill manifest 只声明 prompt fragment 和工具名。
3. 新增 MCP 工具：配置 `MCP_SERVER_COMMAND`，由 `MCPToolProvider` 自动加载远端工具。
4. 新增上下文来源：放入 `agent/context/sources.py`，输出 `ContextFragment`。
5. 新增 workspace 指令：写入对应 workspace 的 `AGENTS.md`。
6. 新增工具权限策略：实现 `ToolPermissionPolicy`，注入 `AgentRuntime`。
7. 新增断点恢复存储：实现 `CheckpointStore`，注入 `AgentRuntime`。
8. 新增多智能体能力：放入 `agent/orchestration/`，保持对 gateway transport 无依赖。
9. 新增记忆能力：放入 `agent/memory/`，由 context/runtime/orchestration 调用。
10. 新增工作流能力：放入 `agent/workflows/`，用于 DAG、计划执行和多步骤任务。
11. 新增后端协议能力：放入 `gateway/auth/`、`gateway/sessions/` 或 `gateway/streaming/`。
