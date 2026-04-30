# 模块技术地图

这份文档说明主要模块“做什么、怎么做、为什么这样做、后续怎么扩展”。

## 总体边界

```text
web  -> gateway -> agent
tui  -> cli.bridge -> agent
cli  -> agent
```

- `agent` 是核心 SDK/kernel，不依赖 FastAPI、web UI 或 CLI。
- `gateway` 是 HTTP/SSE 服务适配层，负责外部协议、run 生命周期和持久化组合。
- `tui` 是 TypeScript/Ink 本地终端前端，负责高质量交互体验。
- `cli` 是 Python 本地适配层，包含 TUI NDJSON bridge 和 Python fallback CLI。
- `web` 是浏览器界面。

## agent.assembly

职责：

- 从 settings 和 `AgentSpec` 创建 `AgentSession`。
- 解析模型配置。
- 分配 workspace。
- 创建 tool registry。
- 装配 skills、MCP、memory、context、hooks、permission policy。

为什么这样做：

- 保留一个明确的 SDK 入口，避免 gateway、cli、测试各自拼 session。
- 让 agent 内核可以被外部项目直接作为库使用。

后续方向：

- 扩展不同 agent profile 的装配策略，例如 coding agent、browser agent、research agent。
- 支持 profile 化装配，例如 coding agent、browser agent、research agent。

## agent.config

职责：

- 读取 `config/defaults.toml`、`config/local.toml`、`.env` 和 shell env。
- 提供 CLI 与 gateway 共用的 runtime settings。
- 解析模型 protocol fallback、API key、base URL、model、proxy。
- 解析命名 model profile，供 CLI `/model` 和后续 Web 设置页选择。

为什么这样做：

- `cli` 应该直接依赖 `agent`，不能为了读配置 import `gateway`。
- model profile 是“配置组”，protocol 是“模型 API 协议”，二者必须分开，避免出现 `openai-chat/kimi` 这类语义混乱。

后续方向：

- 导出 model profile schema 给 Web 设置页。
- 增加配置诊断，明确显示缺 key、缺 model、endpoint 不可达等状态。

## agent.models

职责：

- 统一模型 wire protocol。
- 把 OpenAI Chat、OpenAI Responses、Claude Messages、Gemini 转为 protocol-neutral events。
- 处理 HTTP/SSE transport、重试和错误类型。

为什么这样做：

- runtime 不应该知道每个 protocol 的增量事件格式。
- 工具调用、reasoning delta、usage、final message 应统一进入 runtime。

后续方向：

- 增加 protocol capability discovery。
- 更完整地保存 request/response trace。
- 对 protocol-specific tool call 修复做统一归一化。

## agent.context

职责：

- 管理 system、project instructions、runtime policy、skills、memory、tool hints、task context。
- 编译 `ContextPack` 为最终 system text 和 trace。
- 管理上下文窗口和压缩。

为什么这样做：

- prompting 本质是上下文的一部分，不应该成为平行顶层概念。
- trace 能解释每段上下文来自哪里，方便调试和审计。

后续方向：

- 更强的 context budget 分配策略。
- memory relevance ranking。
- task/run scoped context injection。
- 压缩摘要持久化和引用追踪。

## agent.capabilities.tools

职责：

- 注册模型可见工具。
- 执行单个或多个工具调用。
- 管理并发、超时和错误转 tool result。
- 接入 builtin tools 和 MCP tools。

为什么这样做：

- 模型只看到工具 schema 和结构化结果。
- 具体执行细节留在 tool handler 或 sandbox client 中。

后续方向：

- 工具元数据：风险、权限、是否需要 workspace、是否需要网络。
- 工具执行事件统一写入 trace。
- tool result schema validation。

## agent.capabilities.sandbox

职责：

- 定义 `SandboxClient`、`SandboxProvider`、`SandboxLease`。
- 提供 local/Docker provider。
- 提供 sandbox lease/event store。
- 把 workspace 挂载给执行环境。

为什么这样做：

- workspace 是数据边界，sandbox 是执行租约。
- provider 可替换，上层工具不变。
- 避免模型或 runtime 直接绑定 Docker。

当前结构：

```text
agent/capabilities/sandbox/
  types.py    协议、lease、结构化结果
  local.py    本地执行 provider
  docker.py   Docker 执行 provider
  factory.py  从 settings 创建 provider/client
  store.py    lease/event 持久化接口和实现
  workspace.py artifacts 和 workspace snapshot/diff
```

后续方向：

- remote sandbox provider。
- resource quotas 和 remote execution lifecycle。
- browser/runtime-specific sandbox providers，用于 click/type/screenshot 等真实浏览器动作。

## agent.capabilities.skills

职责：

- 加载 skill manifest。
- 注入 skill prompt fragments。
- 声明 skill 需要的工具名。

为什么这样做：

- skill 是 agent 能力的一部分，但不应该散落到 runtime 或 gateway。
- 纯 prompt skill 和执行型 skill 要分层处理。

后续方向：

- skill 权限声明。
- skill 版本锁定。
- 执行型 skill 统一走 sandbox。

## agent.capabilities.web

职责：

- 提供 provider-neutral 的 web search/extract/map 能力。
- 当前内置 Tavily REST provider。
- 统一输出 `sources`、`usage`、`request_id`，给 citation、trace 和 audit 使用。
- 在 control plane 持有 API key、domain policy 和 credit budget。

为什么这样做：

- web search 是外部 API 和计费能力，不应该进入 sandbox。
- MCP 可以作为扩展，但内置搜索必须可治理、可审计、可测试。
- 与 `browser.open/download` 分层：web search 返回信息来源，browser 工具负责 sandbox 内取页面/落文件。

后续方向：

- SQLite/web cache。
- per-tenant search quota。
- crawl 工具需要 approval 和 quota 完整后再暴露。

## agent.capabilities.memory

职责：

- 定义长期 memory record 和 store。
- 由 `agent.context.memory` 按 scope 检索并注入上下文。

为什么这样做：

- memory 是长期能力，context 是当次请求拼装。
- 两者分开能避免把数据库记录和 prompt fragment 混在一起。

后续方向：

- embedding/relevance retrieval。
- 用户级、agent 级、workspace 级、run 级 memory 策略。
- memory 写入审批和可见性控制。

## agent.runtime

职责：

- 管理单 Agent 执行循环。
- 编译模型请求。
- 执行工具调用。
- 处理 checkpoint、resume、approval pause。
- 维护 session 历史和 context window。

为什么这样做：

- runtime 是内核，不关心 HTTP、web UI、CLI。
- 模型回合和工具回合拆开，方便测试和扩展。

后续方向：

- task/run scoped tool execution context。
- interrupt/cancel。
- retry policy for tools。
- deterministic replay。
- richer runtime state snapshots。

## agent.governance

职责：

- 工具权限策略。
- 审批、审计、trace。
- credential refs。
- sandbox policy。
- secret redaction 和 payload protection protocol。

为什么这样做：

- 安全、权限、审计不是 runtime 的附属逻辑，必须有独立治理域。
- 凭证引用和真实密钥应分离。

后续方向：

- 真正的 KMS/secret manager provider。
- policy DSL。
- tenant/user/agent 级权限继承。
- 审计查询 API。

## agent.state

职责：

- runs、identity、agent profiles、workspaces 等长期状态。
- 定义 store protocol 和 memory/SQLite/local file 实现。

为什么这样做：

- 状态域比 runtime 更长寿，不能散落在工具或 gateway 代码里。
- gateway 只选择 store，不拥有业务语义。

后续方向：

- workspace snapshot/diff metadata。
- agent profile versioning。
- tenant/user auth 绑定。

## agent.tasks

职责：

- 长程任务状态机。
- task、step、attempt。
- task runner 和 worker 基础设施。

为什么这样做：

- 长程智能体不能只依赖一次 HTTP 请求。
- task 和 run 分离后，一个 task 可以包含多个 step/run/attempt。

后续方向：

- durable queue。
- cancel/resume/retry。
- scheduled task。
- multi-agent workflow execution。

## agent.orchestration 与 agent.workflows

职责：

- `orchestration` 定义角色、handoff、router。
- `workflows` 定义 DAG plan、node、edge。

为什么这样做：

- 多智能体和工作流是 runtime 上层编排，不应该塞进单 agent loop。

后续方向：

- planner/worker/reviewer roles。
- workflow executor。
- cross-agent shared workspace policy。

## gateway

职责：

- HTTP/SSE API。
- 请求 schema 和 response schema。
- run lifecycle service。
- persistence service container。
- future auth/session。
- static UI mount。

为什么这样做：

- gateway 是服务适配层，不拥有 agent 内核逻辑。
- web 只通过 gateway 访问 agent。

后续方向：

- 登录态和 tenant/user 绑定。
- API token/session auth。
- approval/websocket protocol。
- background worker service。

## tui

职责：

- 本地终端前端体验。
- 渲染欢迎页、消息流、tool timeline、model profiles、approval prompt。
- 提供 slash command、`@file` 输入补全和快捷键。
- 通过 NDJSON 与 `cli.bridge` 通信。

当前结构：

```text
tui/src/
  App.tsx                 会话级状态、bridge event 路由、全局快捷键
  protocol/               NDJSON bridge client/types
  ui/                     命令定义、显示格式、主题 token、runtime event/markdown/diff/text helpers
  hooks/                  输入状态机、@file suggestions、输入队列、tool timeline、live draft、ticker/blink hooks
  components/design/      Dialog、Select、Divider、StatusIcon 等 TUI 设计系统
  components/messages/    user/assistant/thinking/tool/status/table/model 消息族
  components/prompt/      输入框、footer、slash/file suggestions、history search
  components/permissions/ permission request body/options/dialog family
  components/tools/       tool action/target/result preview、unified diff preview
```

为什么这样做：

- TUI 是产品界面，应该可以使用 Ink/React 组件化表达，而不是把复杂交互压进 Python print/Rich。
- 前端只关心显示协议，不直接耦合 agent runtime 内部对象。
- 可以更接近 Claude Code/Codex/Nexus Code 的终端交互质量。
- design/messages/prompt 分层后，后续对齐 Claude Code/Nexus Code 时可以逐个模块替换，而不是改一个巨大终端脚本。
- live turn 层单独处理 `text_delta/reasoning_delta`，避免最终 `model_message` 和 streaming draft 重复渲染。
- `ui/runtimeEvents.ts` 只做 runtime event 到 transcript 的纯转换，避免 `App.tsx` 继续膨胀。
- `components/MarkdownBlock.tsx` + `ui/markdown.ts` 负责终端 Markdown 渲染，assistant/thinking 消息不再只是纯文本输出。
- `components/tools/DiffPreview.tsx` + `ui/diff.ts` 负责 patch/git unified diff 预览，文件修改结果不再混在 JSON raw output 里。
- `ui/textBuffer.ts` 收束 Unicode-safe 输入编辑操作，slash picker 和 prompt input 共享同一套字符处理。
- `hooks/useFileSuggestions.ts` 只在 TUI 层索引本地文件，用 `@file` 提升输入体验，不把文件联想逻辑塞进 agent runtime。

后续方向：

- transcript folding 视觉继续接近 Claude Code。
- tool detail expand/collapse 继续补 code preview 和 shell output progress。
- model/profile picker 已具备基础 fuzzy search，后续补 provider health 和延迟诊断。
- running turn input queue 已具备基础排队，后续补 interrupt/cancel。
- task run monitor。

## cli

职责：

- `cli.bridge`：TUI 与 agent 的本地 NDJSON 协议适配。
- `cli.main`：Python fallback 终端入口。
- 解析本地 profile、workspace、permission、model profile 参数。
- 将 slash commands 转为 agent/session 操作。

为什么这样做：

- 本地交互不需要走 HTTP round trip，但 UI 也不应该直接 import agent 内部 Python 对象。
- bridge 把“本地进程协议”和“agent SDK 装配”收束在 Python 侧，保持 `agent/` 不依赖 UI。

后续方向：

- approval resume event 更细粒度。
- task run monitor bridge events。
- workspace selector bridge events。

## web

职责：

- 浏览器界面。
- 展示 chat、stream、tool approval、run trace、task 状态。

为什么这样做：

- web 是 UI，不应该实现 agent 决策逻辑。

后续方向：

- 工具审批面板。
- workspace 文件视图。
- run trace timeline。
- task dashboard。
