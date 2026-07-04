# 基于图数据库的长篇小说 Agent 框架设计方案

> 目标：设计一个专门服务于长篇小说创作的 Agent 系统，使其能够长期维护世界观、人物关系、势力结构、时间线、伏笔、文风与叙事节奏，避免普通 RAG/记忆库在长文本创作中快速污染、冗余和失控。

---

## 0. 项目代号

**StoryGraph Agent**

一个面向长篇小说创作的图数据库驱动 Agent 框架。

核心理念：

> 不把“小说全文”当作记忆，而把“小说世界状态”建模为可查询、可验证、可回滚的结构化图谱。

---

## 1. 背景判断

目前大多数 AI 小说写作工具仍主要依赖以下模式：

1. 直接调用 LLM 续写。
2. 使用大纲、角色卡、世界观卡片作为上下文。
3. 使用向量数据库检索历史片段。
4. 人工维护“故事圣经”或 Codex。

这些方法对短篇、单章、局部润色有效，但在长篇小说中会暴露明显问题：

- 上下文窗口不足。
- 向量检索容易召回语义相似但叙事状态错误的内容。
- 角色关系、秘密、人物知识边界难以稳定维护。
- 世界规则、地点状态、势力格局容易漂移。
- 文风、叙述视角、人物口吻难以跨几十万字保持一致。
- 普通记忆库会被废稿、推测、临时设定、重复摘要污染。

因此，本项目的关键不是“让 LLM 多记一点”，而是建立一个**叙事状态管理系统**。

---

## 2. 设计目标

### 2.1 产品目标

StoryGraph Agent 应该帮助作者完成：

- 长篇小说世界观管理。
- 角色、势力、地点、事件关系维护。
- 章节/场景规划。
- 场景级正文生成。
- 伏笔埋设与回收追踪。
- 时间线与因果链检查。
- 人物知识边界检查。
- 文风一致性维护。
- 草稿事实抽取与人工确认。
- 多轮修订与版本回滚。
- 中文优先的本地作者工作台界面。
- 清晰区分当前可用的 CLI / API + Web 工作台、源码构建桌面包，以及未来签名发布的桌面安装器。
- 桌面版应让作者不必理解开发环境即可启动本地后端、打开写作工作台、管理本地项目数据，并通过程序内更新通道获得新版。

### 2.2 工程目标

系统应满足：

- 可本地运行。
- 模块化，方便 Codex 分阶段实现。
- 图数据库与向量库解耦。
- 正文、摘要、事实、风格样本分层存储。
- 所有 canon 变更可追溯来源。
- 自动生成内容不得直接污染 canon。
- 支持人工审阅后写入正式设定。
- 当前 MVP 必须明确标注本地可用入口、源码构建桌面包和未发布签名安装器之间的差异。
- 可安装桌面版必须复用同一本地 API、工作流引擎、Graph Store、Draft Store 和 ReviewService，不得另建一套 canon 写入逻辑。
- 应维护单一明确版本号来源，并同步到 Python、Web、Tauri/Rust 和前端显示。
- 桌面 updater 必须使用签名 artifact 和明确 release endpoint；更新安装不得绕过后端 canon/review 边界。
- GitHub 同步在当前项目中只表示软件发布/更新通道，不表示本地小说 workspace、canon、草稿、导入文档、项目设置或审阅状态同步。
- Windows 桌面包启动本地后端时不得显示额外空控制台窗口，后端输出应进入日志。
- 桌面图标、品牌资源和本地化文案属于桌面/前端体验层，不得引入 canon 数据路径。

---

## 3. 非目标

MVP 阶段不追求：

- 一键生成完整百万字小说。
- 完全自动替代作者决策。
- 复杂多人协作编辑器。
- 商业级排版出版流程。
- 复杂 UI。
- 对所有小说类型通用的完美写作模型。

MVP 应优先做成一个**本地引擎 + API + CLI + Web UI + 桌面宿主** 的创作引擎。桌面版不应另起一套逻辑，而应作为同一本地 API 与工作流引擎之上的桌面工作台。

项目对作者公开的使用方式应表述为：

- CLI 本地工作区，用于持久化 demo、图谱种子、场景流程和待审事实。
- FastAPI + React/Vite Web 工作台，用于本地浏览器中的写作、Context Pack 检查和人工审阅。
- Tauri 桌面应用，可从源码构建本地 Windows 可执行文件、NSIS 安装器和 updater artifact；仓库不提交签名 release 二进制。
- 签名发布通道，未来通过 GitHub Release 提供安装器、updater 签名和 `latest.json`，供程序内更新检查与安装使用。

其中 GitHub Release 只负责软件 release 资产分发，不承载小说项目数据同步。当前已验证的 Windows updater artifact 命名是 NSIS setup executable 加 `setup.exe.sig`，不是 `nsis.zip`。

---

## 4. 核心架构

```text
┌───────────────────────────────────────────────┐
│        Author / Editor / Desktop Workbench     │
└───────────────────────┬───────────────────────┘
                        │
┌───────────────────────▼───────────────────────┐
│              LangGraph Orchestrator            │
│ 工作流状态、节点调度、HITL 中断、任务路由       │
└───────┬───────────────┬───────────────┬───────┘
        │               │               │
        ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Graph Store │ │ Vector Store│ │ Draft Store │
│ Canon 状态  │ │ 语义检索    │ │ 正文/版本   │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       ▼               ▼               ▼
┌───────────────────────────────────────────────┐
│              Context Pack Builder             │
│      写作前构造场景上下文包，而非全文回忆       │
└───────────────────────┬───────────────────────┘
                        ▼
┌───────────────────────────────────────────────┐
│        StoryGraph Writing Agent Modules        │
│ Plot / Character / World / Style / Scene / QA │
└───────────────────────┬───────────────────────┘
                        ▼
┌───────────────────────────────────────────────┐
│              State Extraction Layer           │
│      从草稿中抽取事实变更、矛盾、伏笔等        │
└───────────────────────┬───────────────────────┘
                        ▼
┌───────────────────────────────────────────────┐
│             Human Review / Canon Commit       │
│       人工确认后写入正式图谱，支持回滚         │
└───────────────────────────────────────────────┘
```

实现原则：

- LangGraph 负责**长流程编排**：规划、上下文构建、写作、检查、抽取、人工审阅、提交或回滚。
- 图数据库负责**canon 真相源**：角色关系、知识边界、秘密、伏笔、地点状态、事件因果。
- Draft Store 负责**文本与版本**：正文、废稿、修订、作者批注。
- Proposal Store 负责**非 canon 协作产物**：Agent 与作者共同修改的场景草稿提案、事实草稿提案、场景重建和 canon patch 提议。
- Vector Store 负责**相似性辅助**：风格样本、情绪节奏片段、历史场景摘要。
- StoryGraph Writing Agent 不直接写入 canon，只能提出 `CandidateFact` 或 `GraphPatch`，经人工审阅后提交。

---

## 5. 数据分层

### 5.1 Graph Store：叙事状态图谱

图数据库只保存结构化叙事状态，不保存整章正文。

适合保存：

- 人物。
- 地点。
- 组织/势力。
- 物品。
- 事件。
- 秘密。
- 伏笔。
- 世界规则。
- 场景。
- 章节。
- 时间线。
- 人物关系。
- 人物知识状态。
- 因果关系。

### 5.2 Draft Store：正文与版本

保存：

- 小说正文。
- 章节草稿。
- 场景草稿。
- 修订版本。
- 废稿。
- 作者批注。

推荐：SQLite/PostgreSQL + 文件系统。

### 5.3 Proposal Store：协作草稿与提案

保存所有尚未进入 Draft Store、Candidate Store 或 Graph Store 的协作产物：

- `scene_draft`：场景正文提案，可由 Agent 生成或作者导入/编辑。
- `fact_draft`：事实抽取提案，必须引用真实来源草稿后才能提交 CandidateFact。
- `scene_rebuild`：重建场景结构、节奏、冲突或视角的计划。
- `canon_patch`：对 canon 图谱的拟议修改，不能直接写入 Graph Store。
- `outline_draft`：大纲、章节或场景计划草稿。

Proposal Artifact 使用 `proposal_artifact_v1`，保存 `source_refs`、`target_refs`、`provenance`、`version`、`review_decision` 和 `derived_refs`。作者和 Agent 的每次修改都应产生新版本。

边界：

- Proposal Artifact 不是 canon，也不是当前场景草稿。
- 接受 Proposal Artifact 只表示作者接受该协作提案，不等于写入 canon。
- `scene_draft` 只有经过显式 promotion API 才能进入 Draft Store。
- `fact_draft` 只有在提供真实 Draft Store `source_draft_id` 时，才能通过 ReviewService 提交 pending CandidateFact。
- Rejected proposal 不能派生 Draft、CandidateFact 或 Graph 写入。

推荐：SQLite JSON payload store，主键为 `(id, version)`，列表默认只返回每个 proposal 的最新版本。

### 5.4 Vector Store：语义检索

保存：

- 风格样本 embedding。
- 场景摘要 embedding。
- 已完成正文片段 embedding。
- 人物口吻样本 embedding。
- 相似情绪/节奏片段 embedding。

注意：向量库只负责“相似性”，不负责 canon 判断。

MVP 可先使用本地确定性风格样本检索：将作者显式提供的风格片段保存到 SQLite，并用项目、POV、语气、对白风格、标签与词汇重叠做稳定排序。真实 embedding 后端（LanceDB / Chroma / pgvector）应作为后续可替换 adapter 接入，不应改变 graph canon 规则。

### 5.5 Event Log：可回滚变更流

保存每一次 canon 更新：

```json
{
  "event_id": "evt_001",
  "source": "scene_012_draft_v3",
  "operation": "CREATE_RELATION",
  "target": "Character:A -> KNOWS_SECRET -> Secret:X",
  "confidence": 0.91,
  "status": "pending_review",
  "created_at": "2026-06-10T12:00:00Z"
}
```

---

## 6. 图数据库模型

### 6.1 节点类型

#### Project

表示一部小说项目。

字段：

- id
- title
- genre
- language
- target_length
- narrative_pov
- style_profile_id

#### Character

人物。

字段：

- id
- name
- aliases
- gender
- age
- role
- personality
- desire
- fear
- wound
- public_identity
- hidden_identity
- current_status
- arc_stage

#### Organization

组织/势力。

字段：

- id
- name
- type
- goal
- ideology
- resources
- territory
- current_status

#### Location

地点。

字段：

- id
- name
- type
- parent_location_id
- description
- atmosphere
- current_status
- rules

#### Item

重要物品。

字段：

- id
- name
- type
- owner_id
- ability
- limitation
- current_location_id
- current_status

#### Event

故事事件。

字段：

- id
- name
- event_type
- timeline_position
- summary
- cause
- consequence
- visibility
- status

#### Scene

场景。

字段：

- id
- chapter_id
- scene_index
- title
- pov_character_id
- location_id
- timeline_position
- goal
- conflict
- outcome
- emotional_turn
- draft_id

#### Chapter

章节。

字段：

- id
- volume_index
- chapter_index
- title
- summary
- purpose
- status

#### Secret

秘密。

字段：

- id
- content
- holder_id
- truth_status
- reveal_plan
- revealed_at_scene_id

#### Foreshadowing

伏笔。

字段：

- id
- seed_scene_id
- payoff_scene_id
- clue_text
- hidden_meaning
- status
- importance

#### WorldRule

世界规则。

字段：

- id
- domain
- rule
- examples
- exceptions
- severity

#### StyleProfile

文风画像。

字段：

- id
- name
- pov
- tense
- sentence_rhythm
- diction
- metaphor_style
- dialogue_style
- banned_patterns

---

### 6.2 边类型

#### 人物关系

```text
(Character)-[:KNOWS]->(Character)
(Character)-[:LOVES]->(Character)
(Character)-[:HATES]->(Character)
(Character)-[:LOYAL_TO]->(Character|Organization)
(Character)-[:BETRAYED]->(Character|Organization)
(Character)-[:FAMILY_OF]->(Character)
(Character)-[:MENTOR_OF]->(Character)
(Character)-[:RIVAL_OF]->(Character)
```

边属性：

- strength: -1.0 到 1.0
- public_status
- private_status
- since_event_id
- last_changed_scene_id

#### 知识边界

```text
(Character)-[:KNOWS_SECRET]->(Secret)
(Character)-[:BELIEVES_FALSELY]->(Secret|Event)
(Character)-[:SUSPECTS]->(Secret|Character|Organization)
(Character)-[:HIDES_FROM]->(Secret|Character)
```

这是长篇小说最关键的图谱能力之一。

#### 空间与归属

```text
(Character)-[:LOCATED_AT]->(Location)
(Organization)-[:CONTROLS]->(Location)
(Item)-[:LOCATED_AT]->(Location)
(Item)-[:OWNED_BY]->(Character|Organization)
(Location)-[:PART_OF]->(Location)
```

#### 事件与因果

```text
(Event)-[:CAUSES]->(Event)
(Event)-[:CONSEQUENCE_OF]->(Event)
(Character)-[:PARTICIPATED_IN]->(Event)
(Event)-[:OCCURRED_AT]->(Location)
(Event)-[:OCCURRED_IN_SCENE]->(Scene)
```

#### 伏笔

```text
(Foreshadowing)-[:SEEDED_IN]->(Scene)
(Foreshadowing)-[:POINTS_TO]->(Secret|Event|Character|Item)
(Foreshadowing)-[:PAID_OFF_IN]->(Scene)
```

#### 章节结构

```text
(Project)-[:HAS_CHAPTER]->(Chapter)
(Chapter)-[:HAS_SCENE]->(Scene)
(Scene)-[:NEXT_SCENE]->(Scene)
```

---

## 7. 事实状态分类

为了防止记忆污染，所有事实必须有状态。

```text
CANON          已确认设定，可用于强约束
DRAFT_FACT     草稿事实，待确认
HYPOTHESIS     模型推测，不可作为强约束
CONFLICT       与现有 canon 冲突
DEPRECATED     已废弃设定
STYLE_SAMPLE   文风样本
```

任何自动抽取结果默认进入 `DRAFT_FACT`，必须经 Human Review 才能进入 `CANON`。

---

## 8. 单 Agent 能力模块设计

本项目只包含一个核心 Agent：**StoryGraph Writing Agent**。它是面向作者的长篇小说辅助写作 Agent，负责理解作者意图、调用工具、组织写作流程、生成文本、检查连贯性，并把候选状态变更提交给作者审阅。

下列内容都是 StoryGraph Writing Agent 在 LangGraph 中拆分出来的**能力模块 / 工作流节点 / 子流程**。每个模块都应有明确输入、输出 schema、可观察日志和可测试行为。

推荐将整体工作流拆成几个 LangGraph 子流程：

- `planning_flow`：故事圣经、卷/幕/章节/场景规划。
- `scene_generation_flow`：构建 Context Pack、生成场景、连贯性检查、修订。
- `state_review_flow`：状态抽取、候选事实生成、人工审阅、canon commit。
- `style_flow`：风格画像、风格样本检索、文风漂移检查。

### 8.1 Intent Router / Director Node

意图理解与任务编排节点。

职责：

- 接收作者意图。
- 判断当前任务类型：规划、写作、修订、检查、查询、审阅。
- 决定需要查询图谱、向量库、正文库还是调用 LLM。
- 选择进入哪个 LangGraph 子流程。
- 汇总输出给作者。

### 8.2 Plot Planning Module

剧情规划能力模块。

职责：

- 维护卷、幕、章节、场景结构。
- 设计冲突升级。
- 检查因果链。
- 规划高潮、反转、伏笔回收。

### 8.3 Character Consistency Module

人物一致性能力模块。

职责：

- 管理人物欲望、恐惧、创伤、弧光。
- 检查人物行为是否符合当前动机。
- 维护人物关系变化。
- 维护人物知道/不知道什么。

### 8.4 World Consistency Module

世界观一致性能力模块。

职责：

- 管理地点、势力、历史、规则。
- 检查世界规则冲突。
- 维护势力格局和资源分布。

### 8.5 Style Module

文风能力模块。

职责：

- 提取风格画像。
- 检查文风漂移。
- 提供场景写作风格提示。
- 维护人物对白口吻。

### 8.6 Scene Writing Module

场景写作能力模块。

职责：

- 只负责当前场景正文。
- 不直接更新 canon。
- 必须基于 Context Pack 写作。
- 输出正文和简短创作说明。

### 8.7 Continuity Check Module

连贯性检查能力模块。

职责：

- 检查时间线矛盾。
- 检查人物不可能知道的信息。
- 检查地点状态矛盾。
- 检查关系状态矛盾。
- 检查伏笔是否遗漏或误回收。

### 8.8 State Extraction Module

状态抽取能力模块。

职责：

- 从新草稿中抽取候选事实。
- 抽取关系变化。
- 抽取秘密揭露。
- 抽取地点/物品状态变化。
- 抽取新伏笔和已回收伏笔。
- 输出结构化 JSON。

### 8.9 Revision Module

修订能力模块。

职责：

- 根据连贯性检查报告修订正文。
- 根据文风检查报告统一文风。
- 根据作者反馈局部改写。

---

## 9. 写作流程

### 9.1 新建项目

```text
用户输入：小说类型、主题、目标字数、叙述视角、文风参考。
系统生成：Project、初始 StyleProfile、初始世界设定、主角设定。
```

### 9.2 创建故事圣经

系统帮助作者建立：

- 核心主题。
- 主线冲突。
- 主角欲望。
- 反派目标。
- 世界规则。
- 主要势力。
- 主要地点。
- 初始人物关系。

### 9.3 规划章节

Plot Planning Module 生成：

- 卷结构。
- 幕结构。
- 章节目标。
- 每章冲突与转折。
- 关键伏笔。
- 关键揭示点。

### 9.4 写作前构建 Context Pack

每次写场景前，系统生成一个紧凑上下文包。

示例：

```yaml
scene_id: scene_014
chapter: 第七章
pov: 林烬
location: 北境旧钟楼
timeline: 暴雨夜，王城政变后三日
scene_goal: 林烬寻找失踪的密信
conflict: 钟楼已被银鸦会控制
required_characters:
  - 林烬
  - 赫连鸦
active_relationships:
  - 林烬 distrusts 赫连鸦
  - 赫连鸦 secretly protects 林烬
knowledge_boundaries:
  林烬:
    knows:
      - 密信可能藏在钟楼
    does_not_know:
      - 赫连鸦是其母亲旧部
  赫连鸦:
    knows:
      - 密信内容指向王室血统秘密
must_include:
  - 钟声异常提前响起
  - 林烬发现半枚黑色火漆
must_not_violate:
  - 林烬此时不能知道自己的真实身世
  - 银鸦会不能公开暴露首领身份
style_constraints:
  pov: 第三人称有限视角
  tone: 冷峻、克制、带隐约诗性
  dialogue: 短句，含潜台词
```

### 9.5 生成场景草稿

Scene Writing Module 只根据 Context Pack 和必要的风格样本生成正文。

输出：

- 场景正文。
- 场景摘要。
- 情绪转折。
- 自检说明。

### 9.6 连贯性检查

Continuity Check Module 读取：

- Context Pack。
- 生成草稿。
- 相关 canon 图谱。
- 相关历史场景摘要。

输出：

```json
{
  "status": "needs_revision",
  "issues": [
    {
      "type": "knowledge_boundary_violation",
      "severity": "high",
      "description": "林烬在本场景中推断出赫连鸦与其母亲有关，但当前 canon 中他尚无足够线索。",
      "suggestion": "改为林烬只注意到赫连鸦对旧王徽记反应异常。"
    }
  ]
}
```

### 9.7 状态抽取

State Extraction Module 输出候选图更新：

```json
{
  "new_facts": [
    {
      "type": "ItemLocatedAt",
      "subject": "半枚黑色火漆",
      "relation": "LOCATED_AT",
      "object": "北境旧钟楼",
      "status": "DRAFT_FACT",
      "source_scene_id": "scene_014",
      "confidence": 0.95
    }
  ],
  "relationship_changes": [
    {
      "subject": "林烬",
      "relation": "SUSPECTS",
      "object": "赫连鸦",
      "delta": 0.2,
      "reason": "赫连鸦提前知道钟声异常。",
      "status": "DRAFT_FACT"
    }
  ],
  "foreshadowing": [
    {
      "clue": "钟声提前响起",
      "points_to": "王城地下钟阵被人启动",
      "status": "DRAFT_FACT"
    }
  ]
}
```

### 9.8 人工确认 Canon Commit

作者可选择：

- 接受。
- 修改后接受。
- 标记为废弃。
- 标记为伏笔但暂不解释。
- 回滚。

在 LangGraph 中，这一步应实现为 human-in-the-loop 节点：

```text
State Extraction Module -> interrupt(review_payload) -> ReviewService -> Canon Commit / Reject / Edit
```

`interrupt` 只暂停工作流，不改变 canon。只有 `ReviewService` 收到明确接受或编辑后的结果时，才允许写入 Graph Store 与 Event Log。

---

## 10. 检索策略

### 10.1 不推荐

```text
把最近 20 章全文塞进上下文。
把所有历史摘要都塞进上下文。
向量检索 top-k 后直接拼接。
让 LLM 自己判断哪些设定重要。
```

### 10.2 推荐

使用混合检索：

```text
Graph Traversal + Vector Retrieval + Rule Filter + Context Budgeting
```

检索步骤：

1. 根据当前场景确定核心节点：POV 人物、地点、章节、冲突对象。
2. 从图数据库查询 1-2 跳强相关 canon。
3. 查询人物知识边界。
4. 查询未回收伏笔。
5. 查询该地点近期状态变化。
6. 查询相关人物关系变化。
7. 从向量库检索风格相近片段和情绪相近片段。
8. 压缩为 Context Pack。
9. 按优先级裁剪上下文。

### 10.3 上下文优先级

```text
P0: 当前场景硬约束
P1: 人物知识边界
P2: 当前人物关系与目标
P3: 世界规则和地点状态
P4: 未回收伏笔
P5: 上一场景结果
P6: 风格样本
P7: 远期背景摘要
```

---

## 11. 推荐技术栈

### 11.1 MVP 推荐

```text
Python 3.11+
FastAPI
Pydantic
LangGraph
Neo4j Community / Neo4j Desktop
SQLite（本地 Draft Store / Event Log）
LanceDB / Chroma / pgvector
OpenAI / Claude / local LLM provider adapter
Typer CLI
React + Vite 简单前端
Tauri 桌面壳
pytest / Ruff
```

MVP 的架构取向：

- LangGraph 是正式的工作流运行时，负责长流程、状态、暂停、恢复、流式输出与人审节点。
- 自研部分集中在领域服务：`ContextPackBuilder`、`CanonService`、`ReviewService`、`DraftService`、`RetrievalService`。
- Graph Store 不依赖 LangGraph 的 memory store；小说 canon 应存入图数据库。
- LangGraph 的 state 只保存当前工作流状态、临时产物、运行轨迹和待审 payload。

### 11.2 图数据库选型

#### Neo4j

优点：

- 成熟。
- Cypher 查询生态好。
- 可视化工具好。
- 适合复杂关系建模。
- 近期已有 graph-native agent memory 方向的实验项目。

缺点：

- 需要服务。
- 部署略重。

#### Kuzu

优点：

- 嵌入式。
- 适合本地原型。
- Python 集成简单。
- 不需要单独数据库服务。

缺点：

- 生态和可视化弱于 Neo4j。

建议：

- 默认优先实现 `Neo4jGraphStore`。
- Kuzu 可作为可选实验 backend，用于纯本地、无服务依赖的原型。
- 不应把项目锁死在 Kuzu 上；其公开项目已出现归档和维护连续性风险，应通过 `GraphStore` 接口隔离。
- 若未来需要多人协作、图可视化、复杂查询、生态集成，Neo4j 更稳。

### 11.3 Agent 框架选型

#### LangGraph

适合：

- 多步骤工作流。
- 状态机式写作工作流。
- 长期记忆 namespace/store。
- 人工审阅节点。
- 持久化 checkpointer。
- 失败后恢复。
- 流式输出。
- 子流程拆分。
- time travel / replay 式调试。

注意：

- LangGraph 的长期记忆更偏 JSON store；本项目仍应将核心 canon 放入图数据库。
- 不建议把能力模块实现成彼此对话的独立自治体，而应做成 typed node、tool call、service call 和 schema 输出。
- 人工审阅、canon commit、危险写操作必须通过显式节点，不允许 LLM 直接调用底层写库接口。

#### 自研轻量 Orchestrator

适合：

- 早期避免框架复杂性。
- 精确控制写作流程。
- 更容易让 Codex 逐文件实现。

建议：

- 不再作为主编排层。
- 保留为领域服务与工具函数，而不是完整工作流引擎。
- 如果需要极小 POC，可以先用普通 Python 函数串起 `build_context -> write -> check -> extract`，但正式 MVP 应尽早迁入 LangGraph，避免后期重写工作流状态与人审逻辑。

### 11.4 桌面软件模块

桌面版应服务作者的实际写作流，而不是只做图谱管理器。建议使用：

```text
Tauri
React + Vite
FastAPI local backend
WebSocket / SSE 流式输出
Neo4j / SQLite / Vector Store 本地连接
```

核心界面模块：

- Project Workspace：项目、卷、章节、场景树；Web/桌面工作台必须从后端 `/projects` 读取真实项目树，不能把前端 fixture 或占位数据当成真实 workspace。
- Scene Editor：正文编辑器、版本切换、局部改写、批注。
- Proposal Workspace / 协作草稿箱：展示、编辑、审阅和提升 `proposal_artifact_v1`；该模块必须来自后端 Proposal Store，不得使用前端 fixture 冒充持久化数据。
- Context Pack Inspector：写作前上下文包，可查看、锁定、调整硬约束。
- Agent Run Panel：展示工作流当前节点、事件、检查结果和失败重试；场景工作流按钮应明确包含 `build_context`、`write_draft`、`check_continuity`、`extract_state`、`human_review`。
- Pending Facts Review：候选事实、关系变化、秘密揭露、伏笔状态的人审队列。
- Graph View：人物关系、知识边界、地点、事件因果、伏笔网络的可视化。
- Timeline View：章节、场景、事件、角色位置和秘密揭示时间线。
- Style Lab：风格样本、人物口吻样本、文风漂移报告。
- Settings：模型供应商、API key、本地模型、数据库路径、备份与导出；配置 API key 只表示保存凭据引用，不等于启用 LLM 写作，仍需选择 LLM 写作模式、保存设置、具备权限并拥有有效 context。

桌面进程不直接操作 canon。它通过 FastAPI 调用后端服务，后端服务再经 LangGraph、ReviewService、GraphStore 完成状态变更。

### 11.5 本地安装与桌面打包要求

当前状态：

- `apps/desktop` 已是可构建的 Tauri shell，包含 npm scripts、Rust crate、Windows icon、后端启动/停止/状态命令、系统托盘隐藏/退出生命周期、PyInstaller backend sidecar 和 NSIS bundle 配置。
- 当前可运行入口是 CLI、FastAPI + React/Vite Web 工作台、面向桌面宿主的持久化后端入口 `python -m apps.api.desktop_server`，以及源码构建的 Tauri 桌面应用。
- `apps.api.desktop_server` 启动 `apps.api.desktop:app`，使用 `STORYGRAPH_HOME` 或 Windows `%LOCALAPPDATA%\StoryGraph Agent\workspace` 下的持久化 workspace，并强制选择 JSON graph backend；它只创建 workspace，不会自动 seed demo canon。持久化或桌面空 workspace 应先显示项目创建；创建项目后，作者可以导入已有小说/资料，由 Agent 生成非正典 `project_structure_draft`，经作者接受并显式应用后才创建正式 Chapter/Scene 节点。需要默认 demo project 时，仍可调用 `POST /demo/seed`，该路径要求 full 权限并记录 reviewer、rationale 和 source_ref。已初始化的内置 demo 可以通过工作台或 `POST /demo/archive` 归档为非当前 canon 项目，以便回到空项目树。
- 默认 `apps.api.main:app` 开发入口可用于本地 demo；不传入 settings 时它使用 seeded in-memory stores，不应被描述为完整桌面产品或持久化作者项目入口。
- 当前 Tauri 构建脚本已验证：`npm --prefix apps/desktop run build:installer` 会重新构建 Web 资源、生成 PyInstaller sidecar，并产出本地 NSIS 安装器 `apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.6_x64-setup.exe` 及 Tauri updater 签名 `apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.6_x64-setup.exe.sig`。这些产物是本地源码构建输出，不是已发布签名 release channel。当前验证产物不包含 `nsis.zip`。
- 桌面壳只应复用健康且 `/health.workspace` 与配置工作区一致的本机后端；如果端口被其他工作区的旧后端占用，应在设置页报告冲突，而不是继续加载旧 workspace 的项目树。
- FastAPI 当前提供本地 agent permission level：`read_only`、`read_generate`、`full`。这是防误操作的本地操作者授权分级，不是身份认证；保存设置页或调用 `/settings/agent` 代表本地操作者显式授权，因此可升降权限并立即生效；CLI 当前不执行同一权限闸门。
- React/Vite 工作台当前支持本地 `.txt`、`.md`、`.markdown`、`.docx` 文件和文件夹导入到前端资料树/阅读器。默认导入内容只保存在浏览器内存，不写 Proposal Store、Draft Store、StyleSample Store、Candidate Store 或 Graph Store。作者可显式让 Agent 从导入小说生成 `project_structure_draft` 项目结构草稿；该草稿只包含章节/场景结构 JSON，不保存全文，且只有作者接受并应用后才创建 Chapter/Scene 节点。作者也可显式把 ready 文档保存为 Proposal Store 协作草稿、当前场景 Draft Store 草稿、StyleSample Store 风格样本，或让已配置的 OpenAI-compatible LLM 通读资料后生成 `fact_draft` 协作草稿和 CandidateFact 预览；LLM 资料抽取会保存来源 Draft 用作 provenance，但不会直接写 Candidate Store 或 Graph Store。CLI 文件输入仍只包括单个 UTF-8 文本作为风格样本或场景草稿。
- Web 工作台的项目树、当前场景选择、Graph 预览和 Timeline 预览必须来自后端项目/章节/场景数据；前端占位数据不得被 Context Pack、Draft Store、CandidateFact 或 Graph Store 当成真实 workspace 来源。
- 设置页保存 API key、base URL 或模型名称不应自动切换到 LLM writer。LLM 写作只有在 scene writer mode 选择 `llm`、设置已保存、权限至少为 `read_generate`、当前项目/场景有效且 Context Pack 可构建时才应运行。

可安装桌面版的目标：

- 提供普通作者可启动的本地软件入口，例如通过 Tauri/NSIS 生成的 Windows 安装包或免安装可执行目录。
- 启动时自动启动或连接 FastAPI 本地后端，并把 React 工作台作为主界面。
- 使用设置页管理本地 workspace、模型供应商、API key 引用、权限分级、图数据库连接和备份路径。
- 默认使用本地持久化工作区，避免作者误以为内存 demo 是正式项目存储。
- 保留 CLI 与 API 的可用性，桌面版只是更友好的宿主，不替代后端契约。
- 打包必须包含 Windows icon/bundle 资源，并记录 clean checkout 上的构建与 smoke test 结果。
- 文档或文件夹导入内容若进入后端处理，必须先落入 Proposal Store、Draft Store、StyleSample Store 或 pending CandidateFact；仅用于前端阅读器时可停留在浏览器内存，但不得绕过 ReviewService 直接写 Graph Store。Agent 从导入正文生成的章节/场景结构必须先表现为作者可编辑的 `project_structure_draft`，只有作者接受并显式应用后才可创建 Chapter/Scene 节点。LLM 从导入资料抽出的设定必须先表现为作者可编辑的 `fact_draft` 或 pending CandidateFact，不得自动提交 canon。

边界控制：

- 桌面层不得直接写 Graph Store、Draft Store、Candidate Store 或 Event Log。
- 所有 canon 变更仍必须通过后端 human seed API 或 CandidateFact review API。
- 桌面层不得把前端临时状态、占位数据、LLM 输出、Proposal Artifact、导入文本或用户未确认草稿写入 canon。
- 桌面层不得把 GitHub Release metadata、版本号、updater 状态、icon metadata、本地化 labels 或 release notes 写入 Graph Store、Draft Store、Context Pack 或 CandidateFact。
- 桌面层可以负责进程启动、健康检查、日志位置、workspace 选择和用户设置，但不能持有绕过 ReviewService 的 canon 写入口。
- 打包文档必须明确区分 PowerShell 命令与 Windows PowerShell 命令。

验收标准：

- 新用户能通过 README 的安装/启动步骤打开桌面或 Web 工作台。
- 持久化或桌面空 workspace 不显示内存 demo 作为真实项目；用户可创建项目，并通过导入已有小说生成可审阅的 `project_structure_draft` 后再应用为正式章节/场景。内置演示只能通过明确 full 权限 API seed 操作初始化，不应占据作者主工作流入口。
- 桌面启动后能显示 API 健康状态，并在后端不可用时给出可恢复错误。
- 场景生成、Proposal Workspace、Context Pack 检查、连续性报告和待审事实流程与 API/CLI 使用同一 contract。
- 工作台运行 Agent 工作流时清楚呈现 `build_context`、`write_draft`、`check_continuity`、`extract_state`、`human_review`。
- 接受、编辑接受、拒绝或延后 CandidateFact 后，workflow review pause 状态与 `workflow_run_v1` / `review_payload_v1` 保持一致。
- 重启软件后，配置为持久化的 workspace 不丢失图谱、协作草稿、草稿、候选事实、工作流运行记录和风格样本。

---

## 12. 目录结构建议

```text
storygraph-agent/
  README.md
  pyproject.toml
  .env.example
  /apps
    /api
      main.py
      routes/
    /cli
      main.py
    /web
      package.json
      src/
    /desktop
      src-tauri/
      src/
  /storygraph
    /core
      config.py
      ids.py
      errors.py
    /models
      project.py
      character.py
      organization.py
      location.py
      item.py
      event.py
      scene.py
      chapter.py
      secret.py
      foreshadowing.py
      style.py
      fact.py
    /stores
      graph_base.py
      graph_neo4j.py
      graph_kuzu.py
      draft_store.py
      vector_store.py
      event_log.py
    /workflows
      state.py
      planning_graph.py
      scene_generation_graph.py
      state_review_graph.py
      style_graph.py
    /agents
      director.py
      plot_architect.py
      character_keeper.py
      world_keeper.py
      style_keeper.py
      scene_writer.py
      continuity_checker.py
      state_extractor.py
      revision_editor.py
    /services
      context_pack_builder.py
      canon_service.py
      draft_service.py
      review_service.py
      retrieval_service.py
      style_service.py
      llm_service.py
    /prompts
      scene_writer.md
      state_extractor.md
      continuity_checker.md
      style_checker.md
    /schemas
      context_pack.schema.json
      extraction.schema.json
      continuity_report.schema.json
    /tests
      test_graph_store.py
      test_context_pack.py
      test_state_extraction.py
      test_continuity_checker.py
  /examples
    /fantasy_project
      seed.yaml
      chapters.yaml
      scenes/
  /docs
    architecture.md
    graph_schema.md
    api.md
    prompts.md
```

---

## 13. 核心数据结构

### 13.1 ContextPack

```python
from pydantic import BaseModel
from typing import list, dict, Optional

class KnowledgeBoundary(BaseModel):
    character_id: str
    knows: list[str]
    does_not_know: list[str]
    falsely_believes: list[str]
    suspects: list[str]

class StyleConstraints(BaseModel):
    pov: str
    tense: str | None = None
    tone: str
    sentence_rhythm: str | None = None
    dialogue_style: str | None = None
    banned_patterns: list[str] = []

class ContextPack(BaseModel):
    project_id: str
    scene_id: str
    chapter_id: str
    pov_character_id: str
    location_id: str
    timeline_position: str
    scene_goal: str
    conflict: str
    required_characters: list[str]
    active_relationships: list[str]
    knowledge_boundaries: list[KnowledgeBoundary]
    must_include: list[str]
    must_not_violate: list[str]
    unresolved_foreshadowing: list[str]
    relevant_world_rules: list[str]
    previous_scene_summary: str | None = None
    style_constraints: StyleConstraints
    retrieved_style_samples: list[str] = []
```

### 13.2 CandidateFact

```python
class CandidateFact(BaseModel):
    id: str
    fact_type: str
    subject_id: str
    relation: str
    object_id: str | None = None
    value: str | None = None
    source_scene_id: str
    source_draft_id: str
    confidence: float
    status: str  # DRAFT_FACT / CANON / CONFLICT / DEPRECATED
    rationale: str
```

### 13.3 ContinuityIssue

```python
class ContinuityIssue(BaseModel):
    issue_type: str
    severity: str  # low / medium / high / critical
    description: str
    violated_nodes: list[str]
    evidence: list[str]
    suggestion: str
```

---

## 14. API 草案

### 14.1 Project

```http
POST /projects
GET /projects/{project_id}
```

### 14.2 Canon Graph

```http
GET  /projects/{project_id}/characters
POST /projects/{project_id}/characters
GET  /projects/{project_id}/locations
POST /projects/{project_id}/locations
POST /projects/{project_id}/organizations
POST /projects/{project_id}/world-rules
GET  /projects/{project_id}/graph/query
```

### 14.3 Planning

```http
POST /projects/{project_id}/outline
POST /projects/{project_id}/chapters
PATCH /projects/{project_id}/chapters/{chapter_id}
POST /projects/{project_id}/chapters/{chapter_id}/scenes
PATCH /projects/{project_id}/scenes/{scene_id}
```

### 14.4 Writing

```http
POST /projects/{project_id}/scenes/{scene_id}/context-pack
POST /projects/{project_id}/scenes/{scene_id}/draft
POST /projects/{project_id}/scenes/{scene_id}/revise
POST /projects/{project_id}/scenes/{scene_id}/runs/scene-generation
POST /projects/{project_id}/scenes/{scene_id}/runs/scene-generation { "output_target": "proposal_workspace" }
POST /projects/{project_id}/scenes/{scene_id}/extract-document-facts
```

### 14.5 Proposal Workspace

```http
POST /projects/{project_id}/proposals
GET  /projects/{project_id}/proposals
GET  /projects/{project_id}/proposals/{proposal_id}
GET  /projects/{project_id}/proposals/{proposal_id}/versions
PATCH /projects/{project_id}/proposals/{proposal_id}
POST /projects/{project_id}/proposals/{proposal_id}/revise
POST /projects/{project_id}/proposals/{proposal_id}/submit-review
POST /projects/{project_id}/proposals/{proposal_id}/accept
POST /projects/{project_id}/proposals/{proposal_id}/reject
POST /projects/{project_id}/proposals/{proposal_id}/promote/draft
POST /projects/{project_id}/proposals/{proposal_id}/promote/candidate-facts
```

### 14.6 Checking

```http
POST /projects/{project_id}/scenes/{scene_id}/check-continuity
POST /projects/{project_id}/scenes/{scene_id}/extract-state
POST /demo/archive
```

### 14.7 Review

```http
GET  /projects/{project_id}/facts/pending
POST /projects/{project_id}/facts/{fact_id}/accept
POST /projects/{project_id}/facts/{fact_id}/reject
POST /projects/{project_id}/facts/{fact_id}/edit
```

---

## 15. Prompt 设计原则

### 15.1 Scene Writing Prompt

必须强调：

- 只写当前场景。
- 不擅自揭示秘密。
- 不改变 canon，除非 Context Pack 明确要求。
- 不引入重大新设定，除非被要求。
- 保持 POV 限制。
- 保持人物当前知识边界。
- 使用指定文风。

### 15.2 State Extraction Prompt

必须强调：

- 只抽取文本中明确发生的事实。
- 不推测作者意图。
- 区分事实、暗示、推测。
- 所有输出必须有 source span。
- 默认状态为 DRAFT_FACT。

### 15.3 Continuity Check Prompt

必须强调：

- 找出与 canon 不一致之处。
- 找出人物不应知道的信息。
- 找出世界规则冲突。
- 找出时间线冲突。
- 给出最小修改建议，不重写全文。

---

## 16. MVP 开发路线

### Phase 1：基础骨架

目标：能创建项目、人物、地点、章节、场景。

任务：

- 初始化 Python 项目。
- 定义 Pydantic models。
- 实现 Draft Store。
- 实现 Event Log。
- 实现 Graph Store 抽象接口。
- 实现 Neo4j backend。
- 建立 LangGraph workflow state 与 checkpointer。
- 实现最小 `scene_generation_graph` 骨架。
- 实现 CLI 创建项目。

验收：

- 可创建一个项目。
- 可添加人物、地点、关系。
- 可查询人物关系图。
- 可运行一次空流程：`build_context -> END`。

### Phase 2：Context Pack

目标：能根据场景自动构建上下文包。

任务：

- 实现 ContextPackBuilder。
- 实现图查询：人物关系、地点状态、知识边界、未回收伏笔。
- 实现上下文优先级裁剪。
- 将 ContextPackBuilder 接入 LangGraph 节点。

验收：

- 输入 scene_id，输出 YAML/JSON Context Pack。
- 通过 LangGraph 运行时可追踪 Context Pack 构建过程。

### Phase 3：场景生成

目标：能基于 Context Pack 生成场景草稿。

任务：

- 实现 LLM provider adapter。
- 编写 Scene Writing prompt。
- 保存 draft。
- 生成 scene summary。

验收：

- 输入 scene_id，生成 1000-3000 字中文场景草稿。

### Phase 4：状态抽取与人工确认

目标：草稿不直接污染 canon。

任务：

- 实现 State Extraction Module。
- 输出 CandidateFact。
- 实现 pending facts 列表。
- 实现 accept/reject/edit。
- accept 后写入图数据库。
- 使用 LangGraph interrupt 实现人工审阅暂停与恢复。

验收：

- 新草稿中的关系变化能被抽取为待确认事实。
- 人工确认后图谱更新。
- 被拒绝或编辑的候选事实不会污染 canon。

### Phase 5：连贯性检查

目标：发现基础矛盾。

任务：

- 实现 Continuity Check Module。
- 检查知识边界。
- 检查人物位置。
- 检查地点状态。
- 检查时间线。

验收：

- 故意让角色知道不该知道的秘密，系统能报错。

### Phase 6：风格维护

目标：降低文风漂移。

任务：

- 实现 StyleProfile。
- 从样本文本提取风格。
- 检索相似风格片段。
- 实现 Style Checker。

验收：

- 同一 POV 的多个场景文风更一致。

### Phase 7：Web UI 与可安装桌面壳

目标：让作者能以写作工作台方式使用。

任务：

- 项目页面。
- 人物/地点/组织管理页面。
- 场景写作页面。
- Pending facts 审阅页面。
- 简单图谱可视化。
- LangGraph run panel。
- Tauri 桌面壳。
- 完善并验证 Tauri/Rust 桌面工程文件。
- 本地 FastAPI 后端启动、健康检查、错误恢复和日志定位。
- 本地数据库路径与模型供应商设置。
- 持久化 workspace 选择与重启恢复。
- Windows 安装包、updater artifact 或可执行目录打包流程。
- 桌面窗口关闭时隐藏到系统托盘；托盘菜单的显式退出动作才停止受管后端并退出应用。
- 后端 sidecar 的无控制台启动、日志重定向和异常恢复。
- 程序内签名更新检查、安装前停止受管后端、安装后重启。
- 单一版本号同步、中文 UI 文案和桌面图标资源。
- 当前 CLI、API + Web、桌面入口的使用文档。

验收：

- CLI、本地 API + Web 工作台、桌面入口的用途和限制在 README 中清楚区分。
- 桌面版能启动同一 React 工作台，并通过 FastAPI 完成所有草稿、检查、抽取和审阅操作。
- 桌面层没有任何绕过 ReviewService 的 canon 写入路径。
- 打包产物可在没有开发服务器的情况下启动本地工作台。
- 打包版启动后不显示额外后端空终端窗口，后端输出进入日志。
- 设置页能显示当前版本，并在 Tauri runtime 中使用签名 updater 检查、安装和重启；浏览器 runtime 可降级为 release 下载提示。
- updater 需要明确区分本地源码构建 artifact 与已发布签名 release channel。

---

## 17. Codex 实施任务清单

可以按以下顺序交给 Codex：

### Task 1

创建 Python 项目骨架，使用 `uv` 或 `poetry`，安装 FastAPI、Pydantic、Typer、pytest。

### Task 2

实现 `/storygraph/models` 下所有核心 Pydantic model。

### Task 3

实现 `GraphStore` 抽象类，包含：

- create_node
- update_node
- create_relation
- query_neighbors
- query_scene_context
- get_character_knowledge
- get_unresolved_foreshadowing

### Task 4

实现 KuzuGraphStore 或 Neo4jGraphStore 的第一个版本。

### Task 5

实现 DraftStore，支持：

- create_draft
- update_draft
- get_draft
- list_versions
- mark_discarded

### Task 6

实现 ContextPackBuilder。

### Task 7

实现 LLMProvider 接口和 OpenAIProvider。

### Task 8

实现 Scene Writing Module。

### Task 9

实现 State Extraction Module，要求输出 JSON schema。

### Task 10

实现 ReviewService，将 CandidateFact 从 pending 提交为 canon。

### Task 11

实现 Continuity Check Module。

### Task 12

实现 Typer CLI：

```bash
storygraph init
storygraph add-character
storygraph add-location
storygraph add-relation
storygraph build-context --scene scene_001
storygraph write-scene --scene scene_001
storygraph extract-state --scene scene_001
storygraph review-facts
```

### Task 13

实现 FastAPI 路由。

### Task 14

增加测试用例。

### Task 15

创建一个 `examples/fantasy_project` 作为端到端 demo。

### Task 16

整理当前使用文档，明确 CLI、API + Web 工作台、Tauri 桌面壳三种入口的状态、启动方式和限制。

要求：

- README 必须区分 CLI、API + Web、源码构建桌面安装器和未签名 release artifact。
- Web 工作台启动文档必须包含 FastAPI 与 Vite 两个进程。
- CLI workspace 文档必须说明本地持久化路径。
- `apps/desktop/README.md` 必须说明桌面构建状态、安装器输出路径和桌面层 canon 边界。

### Task 17

实现可安装桌面工作台。

要求：

- 补齐或修正 Tauri/Rust crate、构建脚本、icon/bundle 资源。
- 使用中文优先 UI 文案，避免用户面向界面残留英文操作流。
- 桌面启动时自动启动或连接本地 FastAPI 后端。
- 桌面启动后端时不得弹出额外空控制台窗口；后端 stdout/stderr 应进入日志。
- 桌面主界面复用 React/Vite 工作台。
- 设置页管理 workspace、后端状态、模型供应商、API key、权限、版本号和程序内更新。
- 版本号以根目录 `VERSION` 为源，必须同步 `pyproject.toml`、`apps/web/package.json`、`apps/web/src/version.ts`、`apps/desktop/package.json`、`apps/desktop/src-tauri/Cargo.toml` 和 `apps/desktop/src-tauri/tauri.conf.json`。
- Tauri updater 必须使用签名 artifact、公钥和明确 endpoint；安装更新前应停止受管后端，安装后重启应用。
- 普通浏览器工作台只能提供 release 下载提示，不能伪装成已具备程序内安装能力。
- 图标资源应保存在 `apps/desktop/src-tauri/icons/`，生成脚本应可复现本地 `.ico`。
- 打包为 Windows 可运行产物。
- 本地源码构建输出、Tauri updater artifact（NSIS setup exe + `setup.exe.sig`）、GitHub Release 下载 fallback、已发布签名 release channel 和 Windows Authenticode 代码签名必须在文档中明确区分。
- GitHub 同步只指软件发布/更新通道，不能描述为小说 workspace、canon、草稿、导入文档或审阅状态同步。
- 所有 canon 变更仍走后端 human seed 或 CandidateFact review API。

---

## 18. 关键风险与解决方案

### 18.1 风险：图谱过度复杂

解决：

- MVP 只保留 8 类节点和 15 类边。
- 不要一开始建模所有细节。
- 用 JSON 字段承载低频属性。

### 18.2 风险：LLM 抽取事实不稳定

解决：

- 使用严格 JSON schema。
- 要求 source span。
- 默认 DRAFT_FACT。
- 人工确认后才进入 CANON。

### 18.3 风险：写作变得机械

解决：

- 图谱只约束事实，不约束文学表达。
- Scene Writing Module 应保留创作自由。
- Style Module 只给软约束。

### 18.4 风险：上下文包太长

解决：

- 设定 token budget。
- 按 P0-P7 优先级裁剪。
- 图谱查询限制 hop 数。
- 长背景用摘要，不用全文。

### 18.5 风险：向量库召回垃圾

解决：

- 向量库结果必须经过类型过滤。
- 正文片段、风格样本、摘要分 collection。
- 不允许向量库结果覆盖 canon。

---

## 19. 评估指标

### 19.1 连贯性指标

- 人物知识边界违规次数。
- 时间线冲突次数。
- 地点状态冲突次数。
- 关系状态冲突次数。

### 19.2 创作质量指标

- 作者接受率。
- 每章人工修改比例。
- 文风漂移评分。
- 人物口吻一致性评分。
- 伏笔回收完整率。

### 19.3 系统指标

- Context Pack 平均 token 数。
- 检索耗时。
- 图查询耗时。
- 草稿生成耗时。
- Pending fact 接受率。

---

## 20. 最小 Demo 场景

建议用一个小型奇幻项目测试：

- 3 个主要人物。
- 2 个组织。
- 3 个地点。
- 1 个秘密。
- 2 个伏笔。
- 5 个场景。

测试目标：

1. 主角不知道自己的真实身世。
2. 反派知道但不能公开说。
3. 某个物品从地点 A 移动到地点 B。
4. 一个伏笔在第 2 场景埋下，第 5 场景回收。
5. 系统能发现主角在第 3 场景提前知道秘密的错误。

---

## 21. 参考资料

- Neo4j Agent Memory / graph-native memory：
  - https://github.com/neo4j-labs/agent-memory
  - https://neo4j.com/blog/developer/meet-lennys-memory-building-context-graphs-for-ai-agents/
- LangGraph long-term memory：
  - https://docs.langchain.com/oss/python/concepts/memory
  - https://docs.langchain.com/oss/python/langchain/long-term-memory
- Kuzu embedded graph database：
  - https://kuzudb.github.io/docs
  - https://github.com/kuzudb/kuzu
- LlamaIndex / RAG orchestration：
  - https://github.com/run-llama/llama_index

---

## 22. 总结

StoryGraph Agent 的核心不是“更长上下文”，而是：

```text
结构化 canon + 可控草稿 + 人工确认 + 图检索 + 风格样本 + 连贯性检查
```

长篇小说写作最需要维护的不是文字本身，而是叙事状态：

- 谁是谁。
- 谁知道什么。
- 谁和谁是什么关系。
- 哪个秘密何时被揭示。
- 哪个伏笔何时回收。
- 哪个地点处于什么状态。
- 哪条世界规则不能被破坏。
- 当前场景应该推动什么变化。

图数据库适合成为这个系统的核心，因为小说世界本质上就是一个动态变化的关系网络。
