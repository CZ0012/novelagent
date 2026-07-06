# StoryGraph Agent 中文说明

StoryGraph Agent 是一个面向长篇小说创作的本地 MVP。它围绕结构化 canon、草稿隔离、人工审阅、图检索和连续性检查来组织写作流程。

英文说明见 [README.md](README.md)。

当前实现遵循：

- `docs/architecture.md`
- `contracts/graph_store_v1.md`
- `contracts/context_pack_v1.md`
- `contracts/candidate_fact_v1.md`
- `contracts/continuity_report_v1.md`
- `contracts/workflow_run_v1.md`
- `contracts/review_payload_v1.md`
- `contracts/style_sample_store_v1.md`
- `contracts/proposal_artifact_v1.md`

## 当前 MVP 能力

- 用 Pydantic 定义 graph state、Context Pack、CandidateFact、Draft、WorkflowRun、ReviewPayload、StyleSample 和 ContinuityReport 等契约模型。
- 提供 canon-safe 的图存储，包含本地 JSON graph backend 和可选 Neo4j backend；canon 写入带来源、理由、审阅人和事件日志。
- 使用 SQLite 保存草稿、协作提案、候选事实、工作流运行记录和本地确定性风格样本。
- Context Pack Builder 支持 P0-P7 优先级预算、图谱与草稿来源、风格样本检索和 `missing_context` 缺口报告。
- 提供规则式场景写作器、可选 OpenAI-compatible LLM 场景写作器、规则式连续性检查器和规则式候选事实抽取器。
- ReviewService 会让生成的 `CandidateFact` 保持 pending，直到人工执行 accept、edit-accept、reject 或 defer。
- 提供显式故事圣经 seed 路径和项目内只读选项列表，可处理 Character、Location 和关系；只有用户提供 reviewer、rationale、source reference 和 provenance 时才允许直接写 canon。
- 提供只读图查询 API 和 CLI，用于查看 canon 邻居和关系。
- 提供 CLI 本地工作区命令，可构建 Context Pack、写场景草稿、做连续性检查、抽取状态、运行场景工作流和审阅待定事实。
- 提供工作流运行记录、事件查看、review-pause resume、proposal 输出运行、持久化 store，以及可选 LangGraph runtime/checkpointer。
- 提供 FastAPI 写作工作流接口，并支持持久化 agent settings：模型供应商、API key 引用、JSON mode、scene writer mode 和 API 权限级别。
- 提供中文本地化的 React/Vite 作者工作台，可显示真实 API 项目树、空 workspace 引导、章节/场景元数据编辑、场景草稿、选中文本 Agent 讨论/修订提案、协作草稿箱、Context Pack 检查、连续性 QA、工作流事件查看、图/时间线预览、待审事实处理、本地 txt/md/docx 文件或文件夹导入、agent settings 管理和更新检查。
- 提供桌面目标 FastAPI 入口 `apps.api.desktop_server`，用于持久化本地 workspace 和 JSON graph backend。
- `apps/desktop` 下已有可构建的 Tauri 桌面包，包括 npm scripts、Rust 入口、隐藏控制台的 PyInstaller 后端 sidecar、后端启动/停止/状态命令、系统托盘生命周期处理、Tauri capability、签名 updater 配置、科幻应用图标和 NSIS 安装器配置。
- 提供 fantasy demo fixture 和回归测试，覆盖 canon 安全闭环。

## 中文优先与本地化入口

React/Vite 工作台的用户界面文案集中在 `apps/web/src/localization/zh-CN.ts`，并通过 `apps/web/src/localization/index.ts` 导出显示函数和中文资源。界面层只翻译标签、按钮、状态、权限、提案类型、工作流步骤、审阅动作、常见后端消息和技术术语展示；底层 contract 枚举值、API payload、Graph Store / Draft Store / CandidateFact / Proposal Artifact 的协议字段保持原值。

内置 demo 数据的本地化资源仍在 `storygraph/localization/demo.zh-CN.json`，用于生成中文 fixture 数据。它和前端 UI localization 是两层资源：demo 数据可以进入后端 fixture，前端本地化文案只属于显示层，不写入 Graph Store、Draft Store、Context Pack 或 CandidateFact。

桌面版复用同一个 React 工作台。Tauri 窗口标题、托盘菜单和更新/后端设置页保持中文优先；`StoryGraph Agent`、`FastAPI`、`Tauri`、`GitHub Release`、`CandidateFact` 等名称在 UI 中作为品牌或协议名保留，并在中文文案中解释其含义。

## 当前运行状态

当前 MVP 可以通过 CLI、浏览器工作台或本地构建出的 Windows 桌面包使用。仓库不会提交已签名 release 二进制，但 `apps/desktop` 可以在本机生成 Tauri 可执行文件和 NSIS 安装器。桌面包已经配置 Tauri 签名 updater artifact；真正的自动更新交付仍依赖 GitHub Release 中发布安装器、签名文件和 `latest.json`。

可用入口：

- CLI workspace：适合持久化本地 MVP。状态保存在 `.storygraph`、`STORYGRAPH_HOME` 或 `--workspace` 指定目录下，包含 JSON graph 和 SQLite store。
- 持久化 FastAPI + React/Vite 工作台：适合在浏览器里本地写作和真实 API 演示。需要分别启动 API 后端和 Web dev server。它从 `/projects` 读取真实项目树；前端 fixture 不会被当成 workspace。
- 显式 seeded demo 模式：只适合快速试 UI 或回归检查。默认 `apps.api.main:app` uvicorn 入口使用内存 store 和内置 fantasy seed，除非显式传入 settings，因此它不是真实本地写作入口。
- Tauri 桌面应用：适合源码构建后的直接本地使用。它承载同一个 React 工作台，启动或连接本地 FastAPI 后端时不会显示额外后端控制台窗口，关闭主窗口后会继续在系统托盘运行，并可从配置好的 release 通道检查签名桌面更新。

下面所有命令都是 PowerShell 命令；在 Windows PowerShell 中通常也可运行，但可能受本机执行策略、Python launcher 或 Node 安装影响。

## 本地开发安装

安装 Python 包和开发依赖：

```powershell
python -m pip install -e ".[dev]"
```

安装 Web 依赖：

```powershell
npm --prefix apps/web install
```

可选扩展：

```powershell
python -m pip install -e ".[neo4j]"
python -m pip install -e ".[langgraph]"
```

安装后可以运行 `python -m apps.cli.main ...`，也可以使用 `storygraph` console script。

## 启动 Web 工作台

用于持久化本地写作时，启动桌面目标后端：

```powershell
$env:STORYGRAPH_HOME="D:\storygraph-workspaces\demo"
python -m apps.api.desktop_server
```

这些命令在同一个 PowerShell 终端运行即可。如果没有设置 `STORYGRAPH_HOME`，桌面目标后端会优先使用 Windows 的 `%LOCALAPPDATA%\StoryGraph Agent\workspace`，否则退回用户 home 目录。它会创建 workspace 目录并使用 JSON graph backend。它不会静默 seed demo canon；持久化或桌面空 workspace 应先显示项目创建，然后允许作者导入已有小说并生成非正典的 `project_structure_draft` 项目结构草稿，作者确认后才应用为正式章节/场景。内置 fantasy demo 仍可通过 `POST /demo/seed` 用于开发/上手测试；如已初始化，可调用 `POST /demo/archive` 把旧钟塔/钟塔搜寻从当前项目树归档掉。

如果只想启动用于开发实验的快速内存 demo API，可以运行：

```powershell
python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

在另一个 PowerShell 终端启动 React/Vite 工作台：

```powershell
npm --prefix apps/web run dev
```

打开 `http://127.0.0.1:5173`，把页面里的 API 地址设为 `http://127.0.0.1:8000`。

构建 Web 工作台静态资源：

```powershell
npm --prefix apps/web run build
```

## 桌面安装与构建

当前桌面相关文件是：

- `apps/api/desktop.py`：面向桌面宿主的持久化 FastAPI app 入口。它选择本地 workspace 和 JSON graph backend，但不会自动 seed canon。
- `apps/api/desktop_server.py`：启动该持久化 API 的本地 server 入口。
- `apps/desktop/package.json`：Tauri 开发、后端 sidecar 生成和构建 npm scripts。
- `apps/desktop/scripts/build-backend-sidecar.ps1`：用 Windows PowerShell 和 PyInstaller 打包 `apps.api.desktop_server` 的后端 sidecar。
- `apps/desktop/scripts/build-installer.ps1`：用 Windows PowerShell 重建 Web 资源、重建后端 sidecar，并运行带 updater 签名产物的 Tauri 安装器构建。
- `apps/desktop/scripts/prepare-release-assets.ps1`：用 Windows PowerShell 复制无空格的 GitHub Release 资产名，并写入当前版本的 `latest.json`。
- `apps/desktop/scripts/generate-icon.py`：无第三方依赖的科幻应用图标生成脚本，会生成源 PNG 和 `.ico`。
- `apps/desktop/src-tauri/Cargo.toml` 和 `src/main.rs`：Rust 桌面壳，包含 desktop settings、backend status、backend start、backend stop、本地路径查询命令，以及托盘最小化/退出生命周期。
- `apps/desktop/src-tauri/capabilities/default.json`：Tauri v2 主窗口 capability 边界。
- `apps/desktop/src-tauri/tauri.conf.json`：指向 `apps/web`，并配置 NSIS bundle target 和签名 updater endpoint。

本地构建并运行：

```powershell
npm --prefix apps/desktop install
npm --prefix apps/desktop run build:installer
```

`build:installer` 会创建 updater artifact，因此需要 Tauri updater 签名私钥。本工作区把本地私钥放在 `apps/desktop/.tauri/storygraph-agent.key`，该目录已被 git 忽略。新的 release 机器应通过 `TAURI_SIGNING_PRIVATE_KEY` 或 `TAURI_SIGNING_PRIVATE_KEY_PATH` 提供与 `apps/desktop/src-tauri/tauri.conf.json` 中公钥匹配的私钥。如果确实要轮换 updater key，必须同步更新已提交的公钥和发布流程。

生成的安装器路径是：

```text
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.7_x64-setup.exe
```

其他常用桌面命令：

```powershell
npm --prefix apps/desktop run build:backend
npm --prefix apps/desktop run build:installer
npm --prefix apps/desktop run build:tauri-only
npm --prefix apps/desktop run build:web
npm --prefix apps/desktop run build:with-web
npm --prefix apps/desktop run dev
```

`npm --prefix apps/desktop run build:installer` 已在本工作区验证，可生成：

```text
apps/desktop/src-tauri/binaries/storygraph-backend-x86_64-pc-windows-msvc.exe
apps/desktop/src-tauri/target/release/storygraph-backend.exe
apps/desktop/src-tauri/target/release/storygraph-agent-desktop.exe
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.7_x64-setup.exe
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.7_x64-setup.exe.sig
```

完整安装器构建会用 `--noconsole` 重新生成 PyInstaller 后端 sidecar，重新构建 React/Vite 工作台，并运行 `tauri build`。Tauri 壳启动 sidecar 时也会使用 Windows `CREATE_NO_WINDOW`，所以打包版不应再出现额外的空后端终端窗口。关闭桌面主窗口会隐藏到系统托盘；使用托盘菜单里的 `退出 StoryGraph Agent` 才会停止受管后端进程树并退出应用。如果 8000 端口上已有健康后端但工作区不同，桌面设置页会提示冲突，不再把该进程当作当前桌面 workspace。这些安装器、`setup.exe.sig` updater 签名、后端 sidecar 和 release exe 是本地输出，不会提交到仓库，也还不是已发布 release。

工作台设置页包含“版本与更新”。在 Tauri 桌面运行时，它使用 `tauri-plugin-updater` 检查签名 endpoint `https://github.com/CZ0012/novelagent/releases/latest/download/latest.json`，安装时会先停止受管后端，再安装更新并重启应用。在普通浏览器运行时，它会降级为 GitHub Release 检查；如果发现新版，会提供 Windows 安装器下载链接。

版本更新必须保持 `VERSION`、`pyproject.toml`、`apps/web/package.json`、`apps/web/src/version.ts`、`apps/desktop/package.json`、`apps/desktop/src-tauri/Cargo.toml` 和 `apps/desktop/src-tauri/tauri.conf.json` 同步。这里的 GitHub 只作为软件发布/更新通道；本地小说 workspace、canon、草稿、导入文档、项目设置和审阅状态不会自动同步到 GitHub。

当前已验证的 Windows 构建中，与 updater 相关的本地产物是 NSIS setup 可执行文件及其 Tauri updater 签名 `StoryGraph Agent_0.1.7_x64-setup.exe.sig`。除非构建输出实际改变，不要再写 `nsis.zip` updater artifact。Tauri updater 签名只用于程序内更新校验，和 Windows Authenticode 代码签名不同；后端 sidecar 与安装器的生产级 Authenticode 签名仍是单独发布步骤。

仍缺失或未验证：

- 自动化桌面 smoke tests：安装、卸载、后端 health、工作台加载和 workspace 持久化。
- 后端 sidecar 与安装器的生产级 Authenticode 代码签名。

桌面运行时必须承载同一个 React 工作台，启动或连接本地 FastAPI 后端，持久化 workspace 设置，并继续通过后端 review API 完成所有 canon 变更。桌面层不能直接写 canon。

## 本地 CLI Workspace

初始化持久化 workspace。默认情况下 CLI 会使用当前目录下的 `.storygraph`；也可以设置 `STORYGRAPH_HOME` 或传入 `--workspace` 来隔离运行。

```powershell
python -m apps.cli.main init --workspace .storygraph-demo --force
```

常用 CLI 命令：

```powershell
python -m apps.cli.main add-character --workspace .storygraph-demo --project project_fantasy_demo --id character_mara --name "Mara" --properties-json '{"role":"scout"}' --reviewer editor --rationale "Seeded from story bible." --source-ref author_seed:story_bible_v1
python -m apps.cli.main add-location --workspace .storygraph-demo --project project_fantasy_demo --id location_harbor --name "Harbor" --properties-json '{"type":"port"}' --reviewer editor --rationale "Seeded from story bible." --source-ref author_seed:story_bible_v1
python -m apps.cli.main add-relation --workspace .storygraph-demo --project project_fantasy_demo --id rel_mara_located_at_harbor --type LOCATED_AT --source character_mara --target location_harbor --properties-json '{"scene_id":"scene_seed"}' --reviewer editor --rationale "Author placed Mara at the harbor." --source-ref author_seed:story_bible_v1
python -m apps.cli.main add-style-sample --workspace .storygraph-demo --project project_fantasy_demo --id style_tower --text "Cold restrained tower prose with short lines and subtext." --source-ref author_style:chapter_001 --pov "third-person limited" --tone "cold and restrained" --dialogue-style "short lines with subtext" --tags tower,clue
python -m apps.cli.main get-node --workspace .storygraph-demo --project project_fantasy_demo --id character_mara
python -m apps.cli.main query-graph --workspace .storygraph-demo --project project_fantasy_demo --source character_mara --hop-limit 1 --edge-labels LOCATED_AT --statuses CANON
python -m apps.cli.main build-context --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003
python -m apps.cli.main write-scene --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003
python -m apps.cli.main check-continuity --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003
python -m apps.cli.main extract-state --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003
python -m apps.cli.main run-scene --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003
python -m apps.cli.main review-facts --workspace .storygraph-demo --project project_fantasy_demo
```

`extract-state` 只会创建 pending 的 `CandidateFact` 记录。真正写入 canon 仍然需要明确的人工审阅决定：

```powershell
python -m apps.cli.main review-facts --workspace .storygraph-demo --project project_fantasy_demo --fact fact_id --action accept --reviewer editor --note "approved"
python -m apps.cli.main review-facts --workspace .storygraph-demo --project project_fantasy_demo --fact fact_id --action edit-accept --reviewer editor --patch-json '{"confidence":0.8}' --note "accepted with edit"
python -m apps.cli.main review-facts --workspace .storygraph-demo --project project_fantasy_demo --fact fact_id --action reject --reviewer editor --note "not canon"
python -m apps.cli.main review-facts --workspace .storygraph-demo --project project_fantasy_demo --fact fact_id --action defer --reviewer editor --note "decide later"
```

`add-character`、`add-location` 和 `add-relation` 是单独的显式 story-bible seed 路径。它们之所以能直接写 canon，是因为人类命令提供了 `--reviewer`、`--rationale` 和 `--source-ref`；由草稿生成或抽取出的事实仍必须经过 `extract-state` 和 review。

`get-node` 和 `query-graph` 是只读命令。默认只返回 canon 状态；如需查看非 canon 状态，需要显式传入 `--statuses` 或 `--include-non-canon`。

`add-style-sample` 会写入本地风格样本库 `style_samples.sqlite`。检索到的风格样本只是 P6 软上下文，永远不会改变 graph canon。

## 文档与文件夹导入

React/Vite 工作台可以导入本地 `.txt`、`.md`、`.markdown` 和 `.docx` 文件，也支持浏览器提供的文件夹选择。导入内容会显示在可展开的本地资料树和阅读器中。默认情况下，这仍然只是浏览器内存阅读器：导入内容不会写入草稿、事实或 canon。

作者可以从阅读器中显式把 ready 文档送入后端 store：

- 保存为当前场景的 Draft Store 草稿。
- 保存为 Proposal Store 中的 `proposal_artifact_v1` 协作草稿。
- 保存为 StyleSample Store 风格样本，作为 P6 软风格参考。
- 使用已配置的 OpenAI-compatible LLM 读取导入资料，生成可编辑的 `fact_draft` 协作草稿和 CandidateFact 预览；这一步会保存一个来源 Draft 作为 provenance，但不会写 canon。
- 先保存为当前场景草稿，再运行状态抽取，生成 pending `CandidateFact`。

Proposal artifact 是非 canon 的协作记录。已接受的 `scene_draft` proposal 可以显式提升为 Draft Store 草稿；已接受的 `fact_draft` proposal 只有在提供真实 Draft Store `source_draft_id` 时，才能提交 pending CandidateFact。提交 `fact_draft` 时，后端读取作者可编辑过的显式 fact 标记，而不是绕过 proposal 正文。这些路径仍然需要正常的后端项目/场景与权限检查。它们都不会直接写 Graph Store canon；抽取出的候选事实必须保持 pending，直到人工 review 执行 accept 或 edit-accept，并带上 provenance。

## Agent 对话与选中文本修订

Web 工作台和桌面宿主工作台提供 `Agent` 标签页，用于和已配置的 OpenAI-compatible LLM 讨论当前场景。作者可以高亮草稿片段、手动粘贴标注段落、提出局部问题，请求 Agent 讨论、改写选中段落，或改写整场草稿。请求可以带上当前 Context Pack、当前草稿编辑器文本、已经导入到本地资料树的文件片段，以及作者显式打开的联网搜索片段。

`POST /projects/{project_id}/scenes/{scene_id}/agent-discussion` 需要 `read_generate` 权限和 LLM 凭据。它只会在 Proposal Store 创建非 canon 的 `scene_rebuild` 或 `scene_draft` 协作提案，并返回 Agent 回复、搜索片段和是否成功把选中段落替换为完整提案正文。它不会覆盖 Draft Store，不会创建 CandidateFact，也不会写 Graph Store canon。作者仍需在 `协作草稿箱` 中审阅；只有显式接受并提升后，已接受的 `scene_draft` proposal 才能成为 Draft Store 草稿。

CLI 文件输入仍然非常窄：

```powershell
python -m apps.cli.main add-style-sample --workspace .storygraph-demo --project project_fantasy_demo --text-file .\samples\style.txt --source-ref author_style:style_txt
python -m apps.cli.main write-scene --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003 --text-file .\drafts\scene_003.txt --summary "Author-provided draft."
```

这些 CLI 命令只读取单个 UTF-8 文本文件。它们不会导入目录树，不会自动切分章节，不会解析富文档格式，也不会把导入内容提升为 canon。任何创建草稿、风格样本或待审候选事实的导入路径，都必须保留同一条安全规则：导入材料不能在没有人工 review 和 provenance 的情况下写入 canon。

## API 权限分级

FastAPI runtime 在 `/settings/agent` 提供一个本地操作者授权开关。它不是身份认证，而是本地权限分级，用来避免 API 误触发生成或 canon 写入。

- `read_only`：允许 health、settings read、graph query、proposal listing、context building、continuity read 和 pending fact listing 等读向操作；阻止草稿生成、proposal 创建、状态抽取、工作流运行、故事圣经 seed 写入和 review 决策。
- `read_generate`：允许生成或保存草稿、创建/修订 proposal、插入风格样本、抽取状态和运行场景工作流；阻止 canon seed 写入、proposal accept/reject、promotion 操作和 CandidateFact review 决策。
- `full`：允许完整本地 API，包括人工 seed 写入、proposal 决策/promotion 和 accept/edit-accept/reject/defer review 决策。

保存 `/settings/agent` 被视为本地操作者的显式授权。Web 或桌面设置面板以及同一个本地 API 都可以降低或升高 `permission_level`，新权限会立即生效。这不会让生成草稿、导入文档或模型输出绕过 CandidateFact 审阅；改变 canon 的路由仍然需要 `full` 权限，并带上 reviewer、rationale、source reference 和正常的后端审阅/来源路径。

用 PowerShell 设置权限级别：

```powershell
Invoke-RestMethod -Method Put -Uri "http://127.0.0.1:8000/settings/agent" -ContentType "application/json" -Body '{"scene_writer":"rule_based","permission_level":"read_generate"}'
```

只有在 API 以持久化 settings 启动时，agent settings 才会写入 `agent_config.json`，例如通过 `python -m apps.api.desktop_server` 或 `create_app(StoryGraphSettings(...))` 启动。

## LLM 场景写作器

默认场景草稿由确定性的规则式 writer 生成。如需使用第三方 OpenAI-compatible API，可以通过本地环境变量注入凭据：

```powershell
$env:STORYGRAPH_SCENE_WRITER="llm"
$env:STORYGRAPH_LLM_BASE_URL="https://your-provider.example/v1"
$env:STORYGRAPH_LLM_API_KEY="<your provider key>"
$env:STORYGRAPH_LLM_MODEL="deepseek-chat"
```

在 Web 或桌面设置面板里，输入 API key 只表示保存了凭据引用，并不等于启用 LLM 写作。作者还需要选择 OpenAI-compatible LLM 写作模式、保存设置、具备 `read_generate` 或 `full` 权限，并且当前项目、场景和 Context Pack 有效。

LLM writer 会读取 `storygraph/prompts/scene_writer.md`，要求模型返回 JSON，只把结果保存到 Draft Store，并在本地拒绝遗漏 `must_include` 或直接包含 `must_not_violate` 字面约束的草稿。桌面 sidecar 构建会把 `storygraph/prompts` 和 `storygraph/localization` 作为数据文件打包。它不会拿到 Graph Store handle；生成内容中的状态变化仍必须经过 CandidateFact 抽取和人工 review。

## Graph Backend

本地 CLI 默认使用 JSON graph backend。真实浏览器/桌面写作路径应使用上面的桌面目标持久化后端；seeded in-memory API 只是快速开发/demo 表面。若要让 API 或 CLI graph 操作指向 Neo4j，请安装可选依赖并设置环境变量：

```powershell
python -m pip install -e ".[neo4j]"
$env:STORYGRAPH_GRAPH_BACKEND="neo4j"
$env:STORYGRAPH_NEO4J_URI="bolt://localhost:7687"
$env:STORYGRAPH_NEO4J_USER="neo4j"
$env:STORYGRAPH_NEO4J_PASSWORD="password"
$env:STORYGRAPH_NEO4J_DATABASE="neo4j"
```

Neo4j backend smoke test 需要本机已有 Neo4j 服务，因此默认不运行：

```powershell
$env:STORYGRAPH_RUN_NEO4J_TESTS="1"
$env:STORYGRAPH_NEO4J_URI="bolt://localhost:7687"
$env:STORYGRAPH_NEO4J_USER="neo4j"
$env:STORYGRAPH_NEO4J_PASSWORD="password"
python -m pytest tests/test_graph_neo4j_integration.py
```

## Workflow Runtime

场景工作流默认使用无额外依赖的本地 runtime：

```powershell
$env:STORYGRAPH_WORKFLOW_RUNTIME="local"
```

工作台的“运行”Agent 工作流按钮遵循 `workflow_run_v1` 的 `scene_generation` 步骤：`build_context`、`write_draft`、`check_continuity`、`extract_state` 和 `human_review`。`human_review` 是围绕 pending 候选事实的暂停点，本身不是 canon 写入。

API 也可以用 `output_target=proposal_workspace` 运行 `scene_generation`。该模式会调用当前写作器，把结果保存为 `scene_draft` proposal artifact，并跳过连续性检查、状态抽取和人工审阅，因为此时还没有 Draft Store 草稿。默认 `draft_store` 模式仍保持现有 CLI/API 行为。

如需把同一个 `scene_generation` 流程放到真实 LangGraph `StateGraph` 和 SQLite checkpoint 上运行，安装可选依赖并设置：

```powershell
python -m pip install -e ".[langgraph]"
$env:STORYGRAPH_WORKFLOW_RUNTIME="langgraph"
```

LangGraph checkpoint 会保存在 StoryGraph workspace 下的 `langgraph_checkpoints.sqlite`。公开 API/CLI run panel 仍读取稳定的 `workflow_run_v1` 投影，即 `workflows.sqlite`；canon 写入仍然只由明确的 ReviewService 决策触发。

## Canon 安全规则

- Graph Store 是 canon 状态的唯一真相源。
- 草稿文本、生成摘要、导入文本、风格样本、前端占位数据和模型推测都不能直接改变 canon。
- Proposal artifact 是非 canon 协作记录；接受 proposal 不等于写入 canon，提升到草稿或候选事实必须走单独后端动作。
- 自动抽取只能生成 `CandidateFact` 或 proposed graph patch。
- CandidateFact 只有经过明确人工 review 后才能成为 canon。
- 每次 canon 写入都必须有 provenance：来源场景、来源草稿或 author seed、理由、审阅决定和事件日志。
- 向量或风格检索可以辅助构建上下文，但永远不能覆盖 graph canon。
- 桌面层不能绕过后端 `ReviewService`、`GraphStore` 或 `contracts/` 下的版本化契约。

## Demo CLI

```powershell
python -m apps.cli.main demo
python -m apps.cli.main review-demo --action accept --reviewer editor --note "approved via cli"
```

如果安装了 Typer，CLI 会使用 Typer；没有 Typer 时，核心本地命令会 fallback 到 `argparse`。

## 本地验证

运行 Python 测试：

```powershell
python -m pytest
```

运行 Web build 检查：

```powershell
npm --prefix apps/web run build
```

常用聚焦测试：

```powershell
python -m pytest tests/test_api_agent_settings.py tests/test_api_workflow_runs.py tests/test_cli_task12.py
```

## License

StoryGraph Agent 使用 MIT License 授权。详见 [LICENSE](LICENSE)。
