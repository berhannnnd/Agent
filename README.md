# Agents

Python Agent 服务框架，支持多模型提供商异步调用、Agent Runtime（工具调用 + 上下文管理）、MCP 协议扩展，以及 Web UI 和终端 CLI 双端交互。

## 能力概览

- **多模型异步客户端**：OpenAI Chat / OpenAI Responses / Claude Messages / Gemini，统一接口 + 自动重试退避
- **Agent Runtime**：流式输出、工具调用循环、上下文窗口自动截断、并发控制
- **MCP 工具协议**：通过 stdio 接入外部 MCP Server 扩展工具能力
- **Skill 系统**：动态加载技能清单，注册自定义工具
- **Web UI**：SolidJS + Vite 构建的对话界面，FastAPI 挂载静态产物
- **终端 CLI**：Typer 驱动的本地聊天窗口
- **Domain 配置拆分**：server / agent / models / mcp / log 独立管理，避免命名冲突

## 目录结构

```text
.
├── app/
│   ├── agent/               # Agent Runtime、模型客户端、工具、技能
│   ├── api/                 # FastAPI 路由
│   ├── core/                # 配置（按 domain 拆分）
│   ├── engines/             # 引擎/能力管理
│   ├── services/            # 服务编排
│   ├── shared/              # 共享基础设施
│   ├── static/              # Web 构建产物（由 web/dist/ 生成）
│   ├── utils/               # 工具函数
│   ├── app.py               # FastAPI 应用工厂
│   ├── cli.py               # Typer CLI 入口
│   └── web.py               # Web UI 静态文件挂载
├── web/                     # 前端源码（SolidJS + Vite）
│   ├── src/
│   └── dist/                # 构建产物
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

# 2. 配置模型密钥
cp .env.example .env
# 编辑 .env，填入至少一个 provider 的 API_KEY / BASE_URL / MODEL

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

对话内支持 `/clear` 清空上下文，`/exit` 或 `/quit` 退出。

## Web UI

构建前端：

```bash
cd web && npm run build
```

然后启动后端，`/ui/` 路径会自动挂载对话界面。

开发模式（前后端同时启动）：

```bash
make dev-web
```

## 配置说明

配置按 domain 拆分，通过 `env_prefix` 隔离环境变量：

| Domain | 环境变量前缀 | 示例 |
|---|---|---|
| Server | 无 | `HOST`, `PORT`, `DEBUG` |
| Agent | `AGENT_` | `AGENT_PROVIDER`, `AGENT_MAX_TOKENS` |
| OpenAI | `OPENAI_` | `OPENAI_API_KEY`, `OPENAI_MODEL` |
| OpenAI Responses | `OPENAI_RESPONSES_` | `OPENAI_RESPONSES_API_KEY` |
| Anthropic | `ANTHROPIC_` | `ANTHROPIC_API_KEY` |
| Gemini | `GEMINI_` | `GEMINI_API_KEY` |
| MCP | `MCP_` | `MCP_SERVER_COMMAND` |
| Log | 无 | `LOG_LEVEL`, `LOG_PATH` |

代码中通过 `settings.server.*`、`settings.agent.*`、`settings.models.openai.*` 等访问。

## 扩展模块

1. 在 `app/api/<module>/` 添加接口和请求模型
2. 在 `app/services/<module>/` 添加服务编排
3. 在 `app/agent/tools/` 或 `app/agent/skills.py` 注册自定义工具
4. 在 `app/api/router.py` 挂载路由
5. 在 `tests/` 补充测试
