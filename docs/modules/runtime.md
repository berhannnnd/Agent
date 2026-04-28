# Runtime 模块说明

`agent.runtime` 是单 Agent 执行内核。它负责一次或多次模型回合、工具调用、审批暂停和恢复。

## 当前职责

- 编译模型请求。
- 调用模型 client。
- 接收 protocol-neutral stream events。
- 收集 tool calls。
- 通过 `ToolRegistry` 执行工具。
- 应用 permission policy。
- 写 checkpoint。
- 支持 approval resume。
- 管理 session history 和 context window。

## 为什么 runtime 不直接管理 sandbox

runtime 的职责是调度，不是执行隔离。

```text
runtime -> ToolRegistry -> builtin tool -> SandboxClient
```

如果 runtime 直接操作 Docker 或进程，会出现几个问题：

- runtime 变得和执行 provider 耦合。
- 工具权限无法按语义工具统一处理。
- MCP、browser、filesystem 这些能力会散落在 runtime 里。

因此 runtime 只看到工具调用和工具结果。sandbox lease 可以由 session/tool context 持有，但 runtime 不应该知道 provider 细节。

## 后续重点

- run/task scoped tool context。
- tool retry policy。
- deterministic replay。
- cancellation。
- step-level checkpoint。
- richer runtime event taxonomy。
