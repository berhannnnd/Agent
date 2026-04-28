# Tools 模块说明

`agent.capabilities.tools` 是模型可见能力的注册和执行边界。

## 工具设计原则

- 工具名表达语义，不表达底层实现。
- 工具参数结构化。
- 工具结果结构化。
- 高风险工具必须受 permission policy 和 sandbox policy 双重约束。
- 能用 native tool 解决，就不要默认让模型写 shell。

## 当前内置工具

| 工具 | 说明 |
|---|---|
| `filesystem.read` | 读 workspace 文本文件 |
| `filesystem.list` | 列 workspace 目录 |
| `filesystem.write` | 写 workspace 文本文件 |
| `patch.apply` | 基于精确文本匹配做结构化 edit/create，并返回 unified diff |
| `search.grep` | 正则搜索 workspace 文本 |
| `git.status` | 查看 Git 状态 |
| `git.diff` | 查看 Git diff |
| `test.run` | 运行测试命令 |
| `browser.open` | 在 sandbox 内抓取 HTTP(S) 页面并写入 artifacts |
| `browser.download` | 在 sandbox 内下载 HTTP(S) 资源到 workspace 路径 |
| `shell.run` | 兜底 shell 命令 |

## Tool Impact

approval 事件和 audit 记录会附带 `impact`：

- `risk`：low/medium/high/critical。
- `paths`：将读取或修改的 workspace 路径。
- `commands`：将执行的命令。
- `domains`：将访问的网络域名。
- `writes_files` / `requires_network`：UI 和策略层可直接使用的布尔标记。
- `diff_preview`：`patch.apply`、`filesystem.write` 等写入类工具的预览。

## 为什么要有 native tools

只给 `shell.run` 会让模型做所有决策，系统很难知道它要干什么。native tools 可以带来：

- 更好的权限审批。
- 更好的审计记录。
- 更稳定的提示词行为。
- 更容易做 UI 展示。
- 更容易做 provider-neutral replay。

## 后续重点

- `filesystem.delete`、`filesystem.move`。
- 真实浏览器 runtime：`browser.click`、`browser.type`、`browser.screenshot`。
- web search/fetch。
- package/install 类工具。
- schema validation。
