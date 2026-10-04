# Skills Manager

[English](README.md) | **简体中文**

Skills Manager 是一个本地优先的 Skills 注册表、递归能力解析器、Workflow/Run 执行层、MCP Server 和人类管理界面。

它本身是一个独立项目，也可以单独部署；但在 WebGPT-as-Codex 体系里，它同时承担一层很重要的角色：**把散落在电脑各处的 Skills，从“文件集合”变成 Agent 真正能结构化检索、解析和编排的能力层。**

稳定的 WAC 组件 ID 仍然叫 `skills-control-plane`，所以已有的 WebGPT-as-Codex Gateway 集成可以继续使用。

## 电脑里已经有 Skills 了，为什么还要这个？

如果你电脑里只有十几个 Skill，我觉得确实没必要把事情搞复杂。Agent 搜一下目录，找到对应的 `SKILL.md`，读完就可以干活。

问题是，Skill 一多，事情就完全不是这样了。

你可能同时有：

- `.agents/skills` 里的公共 Skill；
- 某个项目自己带的 Skill；
- Obsidian 里的长期 Skill；
- 不同 Agent 软件复制出来的版本；
- 同名但版本、来源、可信度完全不同的 Skill；
- 还有 Router Skill、Composite Skill，以及只应该在某一个阶段出现的专项 Skill。

这时候，“搜得到”其实已经不够了。

真正的问题变成了：**现在这个 Stage 到底该谁上？同名的几份里哪份优先？它还依赖哪些 Skill？做完以后凭什么允许进入下一阶段？**

普通文件搜索很擅长告诉你“这里有一个 frontend-design”。但它不会自动告诉 Agent：你现在其实已经进入 Browser QA，当前 owner 应该换成 webapp-testing；web-design-guidelines 只是可选；上一阶段的设计 Agent 不应该继续写；而且这一阶段没有过 gate，就不能因为“看起来差不多”直接往后走。

Skills Manager 做的就是这一层。

它不是重新发明 Skill，也不是把你所有 Skill 再复制一遍，而是给现有 Skill 加上**结构化索引、authority、递归解析和 Workflow 执行关系**。

> **Skills 回答的是“我能做什么”；Skills Manager 回答的是“这个阶段该谁来做、该怎么解析、满足什么条件才能继续”。**

## 它具体解决什么

- 从多个 Skill root 自动发现能力，同时保留 authority tier 和不同 variant，不会因为名字一样就直接覆盖；
- 提供结构化的 `skills_search`、`skills_get`、`skills_resources`、`skills_resolve`，Agent 不用每次自己 grep 几千个文件；
- 支持 Router / Composite Skill，不会为了“扁平化”把原来的能力关系弄丢；
- Workflow 可以明确绑定 **Stage -> Skill -> gate -> next Stage**；
- Run、evidence、retry、fallback、blocker、audit history 都可以机器读取；
- SQLite 保存本机运行态，同时做 registry parity / integrity 检查；
- 8955 的 Manager UI 给人看，但不是 Agent 执行的硬依赖，Agent 平时直接调用 MCP/backend。

## 独立项目，也是 WAC 的伴生项目

Skills Manager 故意没有直接塞进 WebGPT-as-Codex 仓库。

它有自己的源码、版本、数据库模型和生产 Workflow；即使没有 WAC，也可以作为独立的 Skills MCP 使用。

但当 WAC 存在时，两边会自然拼起来：

```text
WebGPT-as-Codex
  ├─ 负责 Gateway / OAuth / HTTPS / runtime integration
  ├─ 暴露 Coding Tools / Serena / Playwright / Windows-MCP
  └─ 暴露 Skills Manager（skills-control-plane）

Skills Manager
  ├─ 发现和解析本地 Skills
  ├─ 管理 Workflow / Run / gate / evidence
  └─ 给 Agent 一个结构化的 Skills / Workflow 入口
```

WAC 部署时会安装/更新这个独立仓库，导入仓库里的生产 Workflow，并通过正常的 WAC Skill 同步流程让 canonical `webgpt-as-codex` Skill 可以被 Skills MCP 发现和解析。

现在仓库里版本化的主要生产 Workflow 包括：

- Frontend Product Builder v6
- Creator Studio v9
- WebGPT-as-Codex Loop Engineering v1
- WebGPT-as-Codex Parallel Agent Orchestration v1

其中后两个就是 WAC 自己的执行体系：

- Loop Engineering 解决“一个 Agent 怎么跨窗口长期干活”；
- Parallel Agent Orchestration 解决“父 Agent 怎么拆出多个 Research / DEV 子 Agent，等人工恢复以后再 Fan-in、Build、独立审计”。

## 为什么这对远程使用也有意义

Skills Manager 默认 MCP 在本机：

- MCP: `http://127.0.0.1:8943/mcp`
- Manager UI/API: `http://127.0.0.1:8955/`

单独使用时，它完全可以只监听 loopback。

接进 WAC 以后则不一样。WAC 可以把 Skills Manager 和其他本地 MCP 一起放到统一的 OAuth/HTTPS Gateway 后面。只要客户端本身支持 MCP，并且网络与授权配置完成，就可以从别的 Agent 客户端访问同一套结构化 Skills / Workflow 能力。

这意味着它并不天然被锁死在“电脑本机的一个聊天窗口”里。电脑端可以用；其他支持 MCP 的 Agent 可以远程接；如果手机端客户端支持 MCP，WAC 的远程 Edge 也已经配置好，手机同样可以成为入口。

原始 8943 端口不需要直接暴露到公网。

## 最快部署方式

仓库：

**https://github.com/lite-milkfrog/skills-manager**

如果你有一个能操作 Windows 的 coding/computer Agent，最简单的方式就是：

~~~text
https://github.com/lite-milkfrog/skills-manager
请帮我部署这个项目。
~~~

根目录 `AGENTS.md` 会继续把部署任务路由到 `prompts/ONE-CLICK-AGENT-DEPLOY.md`，要求 Agent：

- 先核对当前默认分支最新 HEAD；
- 不覆盖 dirty/diverged checkout；
- 完成安装/更新；
- 做真实 8943 MCP initialize / tools-list / read-only acceptance；
- 如果检测到 WAC，再安装/更新 WAC integration wrapper。

## 手动启动

~~~powershell
git clone https://github.com/lite-milkfrog/skills-manager.git
cd skills-manager
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
powershell -ExecutionPolicy Bypass -File scripts\desktop\ensure-headless.ps1
powershell -ExecutionPolicy Bypass -File scripts\desktop\ensure-manager.ps1
~~~

Agent 正常使用并不要求打开 Manager UI。只有人想看、整理或管理时，再打开 `http://127.0.0.1:8955/`。

## Skill roots

Skills Manager 可以独立于 WAC 工作，并支持额外 Skill 来源：

- `SKILLS_MANAGER_EXTRA_ROOTS`
- `SKILLS_MANAGER_WORKSPACE_ROOT`
- `SKILLS_MANAGER_USER_HOME`
- `SKILLS_MANAGER_STATE_DIR`
- `SKILLS_MANAGER_STATE_SKILLS_ROOT`
- `SKILLS_MANAGER_LEGACY_CONFIG`

历史 `SKILL_CONTROL_PLANE_*` 环境变量仍然兼容。

## 导入生产 Workflow

Workflow 不是只存在 SQLite 里的几行数据，正式 spec 会版本化保存在 `workflows/`。

~~~powershell
.\.venv\Scripts\python scripts\workflows\import-production.py --archive-older
~~~

这也是我希望它和“普通 Skill 搜索器”拉开差距的地方：**它不只知道有哪些 Skill，还知道一整套任务在不同阶段应该怎样组织这些 Skill。**

## WAC 集成

安装本地 WAC integration wrapper：

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\desktop\install-integration.ps1
~~~

兼容契约：

- component id: `skills-control-plane`
- display name: Skills Manager
- MCP endpoint: 8943
- Manager endpoint: 8955
- WAC gateway exposure: gateway
- dependency: mcpjungle

Skills Manager 负责 Skill / Workflow / Run 的真源；WAC 负责把这套能力接进自己的 Gateway、runtime 和远程访问链路。

## 验证

~~~powershell
powershell -ExecutionPolicy Bypass -File scripts\qa\verify-local.ps1
~~~

加 `-WithRunningServices` 可以连 8943 / 8955 的真实运行态一起检查。

## Repository hygiene

运行数据库、索引、截图、日志、PID、本地缓存、Serena 本机状态和 environment 文件都不应该进入 Git。

**仓库保存“这个系统应该是什么”；机器保存“这台机器现在是什么状态”。**