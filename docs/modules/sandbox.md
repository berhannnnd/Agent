# Sandbox 模块说明

`agent.capabilities.sandbox` 是执行资源边界。它的目标不是把 agent 放进容器，而是让所有高风险工具通过统一执行接口进入受控环境。

## 关键概念

```text
WorkspaceContext -> SandboxPolicy -> SandboxProvider -> SandboxClient -> Tool Result
```

- `WorkspaceContext`：持久化数据位置。
- `SandboxPolicy`：允许哪些文件、进程、网络操作。
- `SandboxProvider`：创建执行环境。
- `SandboxClient`：工具调用的执行接口。
- `SandboxLease`：一次执行环境租约。

## 文件结构

```text
agent/capabilities/sandbox/
  types.py    协议、lease、结构化结果
  local.py    本地 workspace 执行
  docker.py   Docker workspace 挂载执行
  factory.py  settings -> provider/client
  store.py    lease/event store
```

## 为什么放在 capabilities 下

Sandbox 是 agent 的执行能力，不是治理策略本身，也不是 runtime loop 本身。

- `governance.sandbox` 负责授权策略。
- `capabilities.sandbox` 负责实际执行资源。
- `capabilities.tools` 负责模型可见工具。

这样可以避免一个模块同时承担 policy、execution、tool schema 三种职责。

## Provider 行为

local provider：

- 直接在 workspace 路径内执行。
- 适合本地开发和测试。
- 不提供强隔离。

Docker provider：

- 每次命令通过 `docker run --rm` 执行。
- workspace 挂载到 `/workspace`。
- provider 可替换，不改变模型工具接口。

Profiles：

| Profile | 默认策略 |
|---|---|
| `restricted` | 只读 workspace，不允许进程和网络。 |
| `coding` | 允许文件写入和常见代码命令。 |
| `test` | 允许测试相关命令。 |
| `browser` | 允许浏览器/Node 相关命令和网络。 |

未来 provider：

- remote sandbox service。
- gVisor/Kata/Firecracker。
- Kubernetes job。

## Run/Task Scoped Lease

工具执行时，runtime 会把 `run_id` 和可选 `task_id` 传到 `ToolRegistry`。`SandboxToolExecutionRecorder` 会为该 scope 绑定确定性的 lease id：

```text
sandbox_{run_id}
sandbox_{run_id}_{task_id}
```

每次工具执行会写入：

- `lease_acquired`
- `tool_started`
- `tool_finished`

run 完成或失败时，gateway 会把该 run 下的 sandbox leases 标记为 `released`。这让 trace、sandbox events、run record 和 task step 能串成同一条操作动线。

## Artifacts And Snapshots

每个 workspace 会创建固定 artifact 目录：

```text
artifacts/
artifacts/downloads/
artifacts/screenshots/
artifacts/logs/
artifacts/snapshots/
```

工具执行前会记录 `before` workspace snapshot，工具执行后会记录 `after` snapshot 和 diff summary。snapshot 默认跳过 `.git`、`.venv`、`node_modules`、`__pycache__` 和 `artifacts`，避免把依赖目录和运行产物误当成代码变更。

## 和早期代码片段执行器的关系

早期“伪 Python 代码片段执行”可以看成 future `code.run` 工具的雏形。它不应该绕过 `SandboxClient`，而应该作为一个更高层的 sandbox tool：

```text
code.run -> sandboxed interpreter -> controlled tool API -> SandboxClient
```

这样保留可编程性，同时不牺牲权限、审计和可替换执行层。
