# SCP-M10 Beginner-First Product Redesign

STABLE_CORE_VERSION = LE-STABLE-2026-09-17.2
PROGRAM_ID = SKILL-CONTROL-PLANE-UNIFIED-LOCAL-20260922
CURRENT_STAGE = SCP-M10-BEGINNER-FIRST-PRODUCT-REDESIGN
NEXT_STAGE = SCP-M11-VISUAL-SYSTEM-AND-COMPONENT-REDESIGN
AFTER_NEXT_STAGE = SCP-M12-FULL-BROWSER-USABILITY-QA

## Why this stage exists

User feedback overrides the earlier M05/M09 product assumption: the current Manager is too developer-centric, hard to understand, visually unattractive, and too weakly categorized for a beginner.

Observed product facts:
- the current primary navigation exposes implementation nouns: Skills / Workflows / Runs / Deployments / System;
- Overview leads with variant counts, discovery issues, SQLite/parity/runtime ports;
- Skills leads with source class / authority / variants instead of “what can this do for me?”;
- canonical DB currently reports categories = 0 and tags = 0;
- therefore the current classification layer is effectively absent for normal users;
- the previous “high-density developer/admin instrument” default is no longer the primary UX target.

## Product principle

The default experience is for a user who does **not** know Skill Control Plane internals.

Primary question: **“What can I do with these Skills?”**

Technical truth remains available, but is progressively disclosed under Advanced / Technical details rather than occupying the default path.
## New primary information architecture

Primary navigation:
1. **首页** — “现在能做什么” + search + common tasks + recent activity in plain language.
2. **技能库** — browse/search by human use case; card-first by default.
3. **自动流程** — formerly Workflows; explain it as “把多个技能按步骤串起来”.
4. **运行记录** — formerly Runs; explain it as “以前自动流程做过什么、成功没”.
5. **高级工具** — Deployment + System + source/authority/variant/runtime details.

Routes may remain backward-compatible internally; labels and hierarchy change first.

## Progressive disclosure

Beginner layer:
- human name;
- one-sentence purpose;
- “适合做什么”;
- use-case category;
- obvious action: 查看 / 使用 / 打开详情.

Intermediate layer:
- workflow relation;
- tags;
- alternate versions count;
- local folder action.

Advanced layer:
- source class;
- authority tier;
- variant IDs;
- hashes;
- filesystem path;
- parity / SQLite / listener / deployment transaction internals.

Never require the user to understand the Advanced layer to browse or discover Skills.

## Use-case discovery layer

This layer does not replace canonical skill_id or move files. It is a presentation taxonomy over existing metadata/search truth.
Initial human-facing use cases:
- 网页与界面 — frontend / web / UI / design
- 写作与内容 — writing / copy / script / social
- 图片与视觉 — image / design / poster
- 视频与口播 — video / remotion / subtitle / media
- 调研与学习 — research / paper / academic / search
- 浏览器与网页操作 — browser / playwright / web automation
- 自动化与 Agent — automation / agent / workflow
- 知识库与 Obsidian — obsidian / knowledge / markdown
- 数据与分析 — data / csv / spreadsheet / analytics
- PPT 与办公 — presentation / slides / office
- 编程与开发 — code / coding / debug / test
- 系统与工具 — windows / shell / devops / mcp

The first implementation may use deterministic keyword/query-backed collections. M11/M12 can refine the taxonomy with sampled results and counts. This is intentionally separate from empty user-authored Categories/Tags.

## Homepage redesign

The homepage must no longer look like a monitoring dashboard.

Top:
- headline: “你想让 AI 帮你做什么？”
- large search field;
- short explanation that Skills are reusable capabilities.

Main:
- “按用途找技能” grid;
- “常用入口”: 找技能 / 看自动流程 / 最近运行;
- “最近做过什么” in human language.

Secondary:
- compact status summary: “系统正常 / 有 X 个可用技能”;
- technical health expands only on demand.

No SQLite, parity, ports, source authority or variant counts above the fold.

## Skill library redesign

Default = card/list hybrid, not database table.
Each card:
- name;
- readable description;
- use-case chips;
- source path hidden;
- authority hidden;
- variants summarized as “有 N 个版本” only if helpful;
- “查看详情” action.

View controls:
- beginner card view default;
- advanced table view optional.

Filters:
- task/use-case first;
- search second;
- “来源 / 权威 / variant” under Advanced filters.

## Detail page redesign

Default tabs:
- 能做什么
- 使用说明
- 分类与标签
- 技术详情

Technical detail contains old Overview / Variants / Body / Validation / Relations material as secondary disclosure.

Raw SKILL.md remains available, but never the first explanation.

## Visual direction for M11

M10 defines structure only. M11 owns the full visual refresh.

Target personality:
- approachable;
- clear;
- calm;
- modern;
- not “terminal admin panel”;
- not childish;
- not generic purple AI SaaS.

Prefer a light neutral default surface with strong hierarchy, generous but controlled spacing, clear cards, and a restrained blue-green accent. Dark technical styling may remain as an optional future theme, not the default beginner experience.

## Stage boundaries

M10 owns:
- SoT/product contract rewrite;
- nav hierarchy;
- beginner homepage;
- use-case discovery entry;
- beginner-first Skill list;
- advanced-content demotion;
- backward-compatible routes where practical.

M11 owns:
- full component visual system;
- final palette/typography/iconography;
- detail-page visual polish;
- motion and responsive refinement.

M12 owns:
- full browser screenshots and interaction QA across breakpoints/locales;
- classification sampling and obvious-misclassification fixes;
- accessibility and regression gate.

No GitHub publication. No Windows reboot in M10-M12.
