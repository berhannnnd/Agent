# 技术设计说明

这份文档解释当前 agent 内核为什么这样拆、沙箱为什么这样接、工具为什么暴露为语义接口，以及后续开发需要守住的工程边界。

## 核心目标

这个项目不是一个单轮聊天包装器，而是一个可长期运行、可审计、可扩展、可云托管的智能体系统。核心能力最终包括：

- 多模型协议：统一发送消息、接收流式事件、解析工具调用。
- 上下文系统：系统提示、项目指令、workspace、memory、skills、工具提示和任务上下文分层拼装。
- 工具系统：内置工具、MCP 工具、skill 声明工具、浏览器和搜索工具。
- 执行隔离：文件读写、命令执行、测试运行、浏览器自动化等高风险操作进入 sandbox。
- 治理系统：权限确认、审批、审计、追踪、凭证引用、payload 保护。
- 长程任务：task、step、attempt、run、checkpoint、resume、worker。
- 多租户：tenant/user/agent/workspace/run 的完整隔离和可追溯记录。

## 三个平面

当前架构按三个平面组织：

```text
control plane  : gateway / runtime / model calls / credentials / permissions / audit / tracing
data plane     : workspace / memory / run records / checkpoints / task records / artifacts
execution plane: sandbox provider / sandbox client / filesystem / shell / browser / tests
```

关键判断：

- `agent runtime` 不进入 sandbox。它负责调度、组装上下文、调用模型、执行权限判断和记录状态。
- `workspace` 是持久化数据边界。它可以是本地目录、Docker volume、云盘挂载、对象存储同步目录或 Git checkout。
- `sandbox` 是临时执行租约。它负责执行工具，不负责长期保存业务数据。
- `tool` 是模型可见的操作接口。模型看到的是 `filesystem.read`、`search.grep`、`test.run`，不是 Docker 容器、宿主路径或内部 lease。

## 为什么不是直接暴露沙箱

如果把 sandbox 本身暴露给模型，模型就会感知底层执行机制：

```text
model -> docker/container/session/path/process
```

这会带来几个问题：

- 迁移困难：从 local 换到 Docker、gVisor、Firecracker 时，上层提示词和工具行为都可能变化。
- 审批困难：用户真正关心的是“是否允许写文件/跑测试/访问网络”，不是“是否允许操作某个容器”。
- 审计困难：审计记录应该稳定表达“哪个工具在什么 workspace 做了什么”，而不是依赖底层命令文本。
- 安全边界混乱：模型不应该知道宿主机路径、容器 ID、密钥位置、provider 细节。

所以当前链路是：

```text
model -> runtime -> tool registry -> builtin tool -> SandboxClient -> provider -> workspace
```

## 早期代码片段执行器的定位

你早期的思路是：给智能体暴露一套工具函数，让智能体生成类似 Python 的子代码片段，然后在受控环境中执行这些片段。概念上类似：

```python
files = workspace.list(".")
content = workspace.read("README.md")
result = shell.run("pytest")
```

这个设计有价值，因为它能让模型把多个小操作编排成一个短程序，减少多轮工具调用开销，也更像一个可编程 agent runtime。

但它不应该成为第一层模型可见主接口，原因是：

- 权限粒度会变粗。用户审批的是整段代码，而不是单个 `filesystem.write` 或 `shell.run` 行为。
- 审计语义会变弱。系统只能记录“执行了一段代码”，需要再解析代码才能知道真实行为。
- 错误恢复更难。代码片段执行到一半失败时，需要定义事务、回滚、断点和副作用边界。
- 提示词耦合更强。模型必须学会内部 DSL 或伪 Python API，而不同模型的代码生成稳定性不同。
- 安全面更大。哪怕在 sandbox 内，动态代码执行也需要处理循环、资源耗尽、网络、文件逃逸、隐式 import、反序列化等问题。

因此当前定位是：

```text
语义工具是主接口
代码片段执行器可以作为未来的高级工具
```

也就是说，未来可以增加一个受控的 `code.run` 或 `plan.execute` 工具，但它必须满足这些条件：

- 运行在 sandbox 内。
- 只能调用受控 capability API。
- 每个底层动作都能被权限系统拦截。
- 每个底层动作都能写入 trace/audit。
- 有超时、输出截断、资源限制和失败恢复。
- 默认不替代 `filesystem.*`、`search.*`、`git.*`、`test.*` 这些稳定语义工具。

## Workspace 与 Sandbox 的关系

推荐模型：

```text
tenant_id / user_id / agent_id / workspace_id
          |
          v
persistent workspace
          |
          v
sandbox lease
          |
          v
native tools
```

当前本地实现：

```text
.agents/workspaces/{tenant_id}/{user_id}/{agent_id}/{workspace_id}
```

local provider 直接在 workspace 路径内执行。Docker provider 用 `docker run --rm -v workspace:/workspace` 方式把 workspace 挂载进去执行。

后续云托管实现可以替换 provider，但不应该改变模型可见工具：

```text
LocalSandboxProvider
DockerSandboxProvider
GVisorSandboxProvider
FirecrackerSandboxProvider
RemoteSandboxProvider
```

## 工具分层

内置工具按风险拆分：

| 工具 | 风险 | 执行位置 | 说明 |
|---|---:|---|---|
| `filesystem.read` | low | sandbox | 读 workspace 文件 |
| `filesystem.list` | low | sandbox | 列 workspace 目录 |
| `search.grep` | low | sandbox | 搜索 workspace 文本 |
| `filesystem.write` | medium | sandbox | 写 workspace 文件 |
| `git.status` | high | sandbox | 查看 Git 状态 |
| `git.diff` | high | sandbox | 查看 diff |
| `test.run` | high | sandbox | 运行测试命令 |
| `shell.run` | high | sandbox | 兜底命令执行 |

设计原则：

- 优先给模型稳定语义工具。
- `shell.run` 是兜底能力，不是常规主路径。
- 工具结果必须结构化，避免只返回不可解析的大段文本。
- 所有 host-affecting 行为必须通过 `SandboxClient`。

## Web Search、Browser、MCP、Skill 的边界

### Web Search

API 型搜索适合留在 control plane：

```text
web.search -> gateway/tool broker -> search API
```

原因是 API key 不应该进入 sandbox。模型只看到搜索结果，不看到密钥。

网页抓取、页面解析、浏览器点击、下载文件适合进入 execution plane：

```text
browser.open/click/screenshot/download -> SandboxClient -> browser runtime -> workspace/artifacts
```

### Browser

浏览器工具应当作为原生工具族：

```text
browser.open
browser.click
browser.type
browser.screenshot
browser.downloads
```

浏览器进程应运行在 sandbox 或 remote sandbox 内。下载文件和截图落到 workspace 的 artifacts 区域。

### MCP

MCP 分两类：

- 远程可信 MCP：由 gateway 代理，凭证留在 control plane。
- 本地或用户上传 MCP：必须跑在 sandbox 内，通过受控网络和文件权限访问 workspace。

### Skill

Skill 分两类：

- 纯提示词/说明文档：进入 context。
- 带脚本或本地执行逻辑：必须通过 sandbox tool 执行。

## 权限和审计

权限系统应该围绕语义动作，而不是底层 provider：

```text
allow filesystem.read
ask filesystem.write
ask shell.run
deny network
```

Trace 和 audit 的边界不同：

- trace 记录运行链路，用于调试和用户可见时间线。
- audit 记录可追责决策，例如用户审批、凭证访问、高风险写入确认。

未来需要让 `SandboxClient` 的重要动作写入 sandbox events，并和 run/tool trace 关联。

## 当前实现状态

已具备：

- `SandboxPolicy`：文件、进程、网络授权策略。
- `SandboxClient` protocol：文件、目录、命令、搜索的执行接口。
- `LocalSandboxProvider`：本地 workspace 执行。
- `DockerSandboxProvider`：Docker 挂载 workspace 执行。
- `SandboxLeaseRecord` / `SandboxEventRecord`：sandbox 租约和事件记录模型。
- SQLite 表：`sandbox_leases`、`sandbox_events`。
- builtin tools 已经通过 `SandboxClient` 执行。

尚未完成：

- run/task 级 sandbox lease 生命周期绑定。
- tool execution 自动写入 sandbox events。
- Docker daemon 端到端 smoke。
- 浏览器工具族。
- web search 控制面工具。
- 本地 MCP server sandbox 化。
- 高风险工具的更细审批策略和前端确认面板。

## 开发约束

新增能力时遵守这些规则：

- 只要会读写文件、执行命令、跑测试、启动浏览器、运行用户代码，就必须通过 `agent.capabilities.sandbox`。
- 不要在 `agent.capabilities.tools.builtin` 里直接调用宿主 `Path.write_text` 或 `asyncio.create_subprocess_shell`。
- 不要让模型看到 Docker、容器 ID、宿主路径、密钥路径。
- 不要为了兼容旧结构保留双通道执行。
- 能用语义工具表达，就不要让模型写 shell。
- 能记录成结构化事件，就不要只存文本日志。
