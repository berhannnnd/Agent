# Agents Framework Template

这是一个精简的 Python Agent 服务骨架，当前核心能力是 OpenAI 兼容协议的 LLM 调用和终端对话。

## 保留内容

- FastAPI 应用工厂、生命周期、路由聚合
- Typer CLI 与本地启动入口
- Pydantic Settings 配置加载
- 全局异常处理、统一响应、请求 ID、耗时日志、鉴权中间件
- 注册器模式、引擎生命周期管理、Provider 扩展点
- OpenAI 兼容协议的 LLM client 和会话历史
- Docker、Compose、Makefile、测试和架构文档

## 目录结构

```text
.
├── app/
│   ├── api/                 # API 层
│   ├── core/                # 配置
│   ├── engines/             # 引擎/能力管理
│   ├── services/            # 服务编排层
│   ├── shared/              # 共享基础设施
│   └── utils/               # 工具函数
├── deploy/                  # 容器化部署
├── docs/                    # 架构与开发说明
├── requirements/            # 依赖清单
├── tests/                   # 测试用例
└── main.py                  # 本地启动入口
```

## 快速开始

```bash
cp .env.example .env
make install
make run
```

`make install` 会自动使用可用的 Python 3.10+ 创建 `.venv`。如果本机默认 `python3` 是 3.9，可以显式指定：

```bash
make install PYTHON_BIN=/path/to/python3.11
```

如果本机安装了 `uv`，`make install` 会用 `uv venv` 和 `uv pip install` 创建环境，兼容 uv 管理的 Python。

健康检查：

```bash
curl http://127.0.0.1:8010/health
```

## 开发命令

```bash
make install
make run
make dev
make test
make build
make up
```

## 终端 LLM 对话

先在 `.env` 中配置 OpenAI 兼容协议：

```bash
AGENT_PROVIDER=openai-chat
OPENAI_API_KEY=你的密钥
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=你的模型名
```

然后启动终端对话窗口：

```bash
make dev
```

对话内支持 `/clear` 清空上下文，`/exit` 或 `/quit` 退出。

## 扩展新业务模块

1. 在 `app/api/<module>/` 添加接口和请求模型。
2. 在 `app/services/<module>/` 添加服务编排。
3. 如需模型、算法或外部能力，在 `app/engines/` 或 `app/shared/provider/` 注册实现。
4. 在 `app/api/router.py` 中挂载路由。
5. 在 `tests/` 中补充接口或服务测试。
