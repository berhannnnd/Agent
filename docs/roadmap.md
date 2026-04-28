# TODO Plan

这份 roadmap 用来跟踪从当前内核地基到完整可运行长程智能体系统的剩余工作。优先级按“先稳定内核，再做体验，再做云化”排序。

## 当前状态

已完成的地基：

- 模型 provider 协议：OpenAI Chat、OpenAI Responses、Claude Messages、Gemini。
- provider-neutral streaming events。
- runtime tool loop、streaming、checkpoint/resume、approval pause。
- ContextPack 分层上下文。
- workspace scope：tenant/user/agent/workspace。
- builtin tools：filesystem、search、git、test、shell。
- sandbox abstraction：local/Docker provider、SandboxClient、lease/event store。
- run/task/checkpoint/trace/audit/memory/credential/workspace SQLite foundation。
- gateway HTTP/SSE run lifecycle。
- basic web approval controls。

## Phase 1: Sandbox Execution Closure

目标：让 workspace、sandbox、tool execution 成为真正闭环。

TODO:

- [x] 将 sandbox lease 绑定到 run/task 生命周期，而不是只在 session assembly 时创建 client。
- [x] 每次 builtin tool 执行写入 `sandbox_events`。
- [x] trace span 关联 sandbox lease id。
- [x] Docker provider 增加端到端 smoke test，Docker 不可用时跳过。
- [x] 增加 sandbox profile：coding、browser、test、restricted。
- [x] 增加 workspace artifacts 目录约定：`artifacts/`、`downloads/`、`screenshots/`。
- [x] 增加 workspace snapshot/diff 记录，用于任务完成后的变更摘要。

## Phase 2: Native Tool Expansion

目标：减少模型直接写 shell 的需求。

TODO:

- [x] `patch.apply`，支持精确文本 edit/create 和 unified diff 返回。
- [ ] `filesystem.delete`、`filesystem.move`，默认 ask。
- [ ] `git.add`、`git.commit`、`git.log`、`git.show`，按风险分级。
- [ ] `test.discover`，自动识别 pytest/npm/bun/make。
- [ ] `package.install`，显式高风险审批。
- [x] `browser.open`、`browser.download`，通过 sandbox process/network 权限抓取并落到 workspace。
- [ ] `browser.click`、`browser.type`、`browser.screenshot`，通过真实 sandbox browser runtime。
- [ ] `web.fetch`，只做受控页面抓取。
- [ ] `web.search`，API key 留在 control plane。

## Phase 3: Permission, Approval, Audit

目标：让用户能安全地授权长程 agent 操作。

TODO:

- [x] 工具 metadata 增加 risk、requires_network、writes_files 等基础字段。
- [ ] 权限策略支持 tenant/user/agent/workspace/run 级继承。
- [ ] 高风险工具默认 ask。
- [x] approval payload 展示即将修改的路径、命令、网络域名和 patch preview。
- [ ] approval 支持 allow once / allow for run / deny。
- [ ] audit records 扩展到文件写入、命令执行、凭证访问。
- [ ] 前端 approval 面板展示 tool args、risk、diff preview。

## Phase 4: Long-Running Task Runtime

目标：让 agent 可以可靠执行长任务，而不是只处理一次聊天请求。

TODO:

- [ ] durable task queue。
- [ ] worker service 入口。
- [ ] task cancel/resume/retry。
- [ ] step-level checkpoint。
- [ ] task progress events。
- [ ] task result artifact summary。
- [ ] scheduled task 基础能力。
- [ ] task 与 workflow DAG 打通。

## Phase 5: Memory And Context Quality

目标：让 agent 记得该记的，忘掉该忘的，并能解释上下文来源。

TODO:

- [ ] memory write policy：什么可以写入长期记忆。
- [ ] memory retrieval ranking。
- [ ] memory visibility：user/agent/workspace/run。
- [ ] context budget allocator。
- [ ] compaction summary 持久化。
- [ ] prompt/context trace UI。
- [ ] Agent instructions 版本化。

## Phase 6: MCP And Skill Runtime

目标：让 MCP/skill 成为安全能力扩展，而不是任意脚本入口。

TODO:

- [ ] MCP server 类型分类：remote trusted / local sandboxed。
- [ ] local MCP server 通过 sandbox 启动。
- [ ] MCP tool 权限 metadata。
- [ ] skill manifest 增加 permissions、sandbox profile、tools。
- [ ] 执行型 skill 只能调用受控 tool API。
- [ ] skill install/update/version lock。

## Phase 7: Multi-Agent And Workflow

目标：支持 planner/worker/reviewer 等多智能体协作。

TODO:

- [ ] AgentRole registry。
- [ ] Static router 升级为 policy/router。
- [ ] handoff event。
- [ ] shared workspace lock。
- [ ] workflow executor。
- [ ] reviewer/critic step。
- [ ] supervisor timeout/cancel。

## Phase 8: Cloud Multi-Tenant Foundation

目标：从本地开发走向可托管。

TODO:

- [ ] 登录和真实 user_id/tenant_id 绑定。
- [ ] 不信任请求体中的 user_id/tenant_id。
- [ ] API token/session auth。
- [ ] workspace quota。
- [ ] sandbox quota。
- [ ] secret manager/KMS provider。
- [ ] encrypted payload provider 替换本地 base64 测试实现。
- [ ] per-tenant audit export。

## Phase 9: Product Interfaces

目标：让 CLI 和 Web 都能真实操作长程 agent。

TODO:

- [ ] CLI 多轮 session。
- [ ] CLI approval prompt。
- [ ] CLI task monitor。
- [ ] Web run timeline。
- [ ] Web tool approval panel。
- [ ] Web workspace file/artifact browser。
- [ ] Web task dashboard。
- [ ] Web trace/context debugger。

## Phase 10: Hardening

目标：把 demo 级实现收敛为可维护系统。

TODO:

- [ ] 端到端 smoke：chat、tool、approval、task、sandbox。
- [ ] Docker sandbox integration test。
- [ ] provider live test profile。
- [ ] DB migration strategy。
- [ ] structured logging。
- [ ] metrics。
- [ ] failure injection tests。
- [ ] security review checklist。

## 下一步建议

最近应该按这个顺序继续：

1. Phase 2：补 `filesystem.delete/move` 和 git commit 系列 native tools。
2. Phase 3：approval 支持 allow once / allow for run / deny，并让前端面板展示 impact。
3. Phase 2：补真实浏览器 runtime，用于 click/type/screenshot。
4. Phase 6：local MCP server sandbox 化为可替换 provider。
5. Phase 8：sandbox quota 和 remote provider。

这条线能把“智能体能持续读写执行”的底层闭环补起来，然后再进入多智能体和云托管。
