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

## 当前 MVP 能力

- 用 Pydantic 定义 graph state、Context Pack、CandidateFact、Draft、WorkflowRun、ReviewPayload、StyleSample 和 ContinuityReport 等契约模型。
- 提供 canon-safe 的图存储，包含本地 JSON graph backend 和可选 Neo4j backend；canon 写入带来源、理由、审阅人和事件日志。
- 使用 SQLite 保存草稿、候选事实、工作流运行记录和本地确定性风格样本。
- Context Pack Builder 支持 P0-P7 优先级预算、图谱与草稿来源、风格样本检索和 `missing_context` 缺口报告。
- 提供规则式场景写作器、可选 OpenAI-compatible LLM 场景写作器、规则式连续性检查器和规则式候选事实抽取器。
- ReviewService 会让生成的 `CandidateFact` 保持 pending，直到人工执行 accept、edit-accept、reject 或 defer。
- 提供显式故事圣经 seed 路径，可写入 Character、Location 和关系；只有用户提供 reviewer、rationale、source reference 和 provenance 时才允许直接写 canon。
- 提供只读图查询 API 和 CLI，用于查看 canon 邻居和关系。
- 提供 CLI 本地工作区命令，可构建 Context Pack、写场景草稿、做连续性检查、抽取状态、运行场景工作流和审阅待定事实。
- 提供工作流运行记录、事件查看、review-pause resume、持久化 store，以及可选 LangGraph runtime/checkpointer。
- 提供 FastAPI 写作工作流接口，并支持持久化 agent settings：模型供应商、API key 引用、JSON mode、scene writer mode 和 API 权限级别。
- 提供 React/Vite 作者工作台，可通过 API 做场景草稿、Context Pack 检查、连续性 QA、工作流事件查看、图/时间线预览、待审事实处理、本地 txt/md/docx 文件或文件夹导入，以及 agent settings 管理。
- 提供桌面目标 FastAPI 入口 `apps.api.desktop_server`，用于持久化本地 workspace 和 JSON graph backend。
- `apps/desktop` 下已有可构建的 Tauri 桌面包，包括 npm scripts、Rust 入口、PyInstaller 后端 sidecar、后端启动/停止/状态命令、Tauri capability 和 NSIS 安装器配置。
- 提供 fantasy demo fixture 和回归测试，覆盖 canon 安全闭环。

## 当前运行状态

当前 MVP 可以通过 CLI、浏览器工作台或本地构建出的 Windows 桌面包使用。仓库不会提交已签名 release 二进制，但 `apps/desktop` 可以在本机生成 Tauri 可执行文件和 NSIS 安装器。

可用入口：

- CLI workspace：适合持久化本地 MVP。状态保存在 `.storygraph`、`STORYGRAPH_HOME` 或 `--workspace` 指定目录下，包含 JSON graph 和 SQLite store。
- 持久化 FastAPI + React/Vite 工作台：适合在浏览器里本地写作。需要分别启动 API 后端和 Web dev server。
- Seeded demo FastAPI + React/Vite 工作台：适合快速试 UI。默认 `apps.api.main:app` uvicorn 入口使用内存 demo store，除非显式传入 settings。
- Tauri 桌面应用：适合源码构建后的直接本地使用。它承载同一个 React 工作台，并启动或连接本地 FastAPI 后端。

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

这些命令在同一个 PowerShell 终端运行即可。如果没有设置 `STORYGRAPH_HOME`，桌面目标后端会优先使用 Windows 的 `%LOCALAPPDATA%\StoryGraph Agent\workspace`，否则退回用户 home 目录。它会创建 workspace 目录并使用 JSON graph backend。它不会静默 seed demo canon；需要初始化内置 fantasy demo 时，在工作台点击 `Seed Demo`，或调用 `POST /demo/seed`。

如果只想启动快速内存 demo API，可以运行：

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
- `apps/desktop/src-tauri/Cargo.toml` 和 `src/main.rs`：Rust 桌面壳，包含 desktop settings、backend status、backend start、backend stop 和本地路径查询命令。
- `apps/desktop/src-tauri/capabilities/default.json`：Tauri v2 主窗口 capability 边界。
- `apps/desktop/src-tauri/tauri.conf.json`：指向 `apps/web`，并配置 NSIS bundle target。

本地构建并运行：

```powershell
npm --prefix apps/desktop install
npm --prefix apps/desktop run build:installer
```

生成的安装器路径是：

```text
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.0_x64-setup.exe
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
apps/desktop/src-tauri/target/release/bundle/nsis/StoryGraph Agent_0.1.0_x64-setup.exe
```

完整安装器构建会重新生成 PyInstaller 后端 sidecar，重新构建 React/Vite 工作台，并运行 `tauri build`。这些安装器和 release exe 是本地输出，不会提交到仓库，也还不是签名 release。

仍缺失或未验证：

- 仓库外发布的签名 release 安装器。
- 自动化桌面 smoke tests：安装、卸载、后端 health、工作台加载和 workspace 持久化。
- 后端 sidecar 的生产级加固，包括版本管理和代码签名。

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

React/Vite 工作台可以导入本地 `.txt`、`.md`、`.markdown` 和 `.docx` 文件，也支持浏览器提供的文件夹选择。导入内容会显示在可展开的本地资料树和阅读器中。它只保存在浏览器内存里，不会写入草稿、事实或 canon。

CLI 文件输入仍然非常窄：

```powershell
python -m apps.cli.main add-style-sample --workspace .storygraph-demo --project project_fantasy_demo --text-file .\samples\style.txt --source-ref author_style:style_txt
python -m apps.cli.main write-scene --workspace .storygraph-demo --project project_fantasy_demo --scene scene_003 --text-file .\drafts\scene_003.txt --summary "Author-provided draft."
```

这些 CLI 命令只读取单个 UTF-8 文本文件。它们不会导入目录树，不会自动切分章节，不会解析富文档格式，也不会把导入内容提升为 canon。未来如果导入器创建草稿、风格样本或待审候选事实，也必须保留同一条安全规则：导入材料不能在没有人工 review 和 provenance 的情况下写入 canon。

## API 权限分级

FastAPI runtime 在 `/settings/agent` 提供一个本地安全开关。它不是身份认证，而是开发者本地的权限分级，用来避免 API 误触发生成或 canon 写入。

- `read_only`：允许 health、settings read、graph query、context building、continuity read 和 pending fact listing 等读向操作；阻止草稿生成、状态抽取、工作流运行、故事圣经 seed 写入和 review 决策。
- `read_generate`：允许生成或保存草稿、插入风格样本、抽取状态和运行场景工作流；阻止 canon seed 写入和 CandidateFact review 决策。
- `full`：允许完整本地 API，包括人工 seed 写入和 accept/edit-accept/reject/defer review 决策。

API 可以把当前权限降到更低级别，但不能再通过 API 自行升权。需要重新升权时，应有意编辑本地 `agent_config.json` 或做本地 reset。

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

LLM writer 会读取 `storygraph/prompts/scene_writer.md`，要求模型返回 JSON，只把结果保存到 Draft Store，并在本地拒绝遗漏 `must_include` 或直接包含 `must_not_violate` 字面约束的草稿。它不会拿到 Graph Store handle；生成内容中的状态变化仍必须经过 CandidateFact 抽取和人工 review。

## Graph Backend

本地 CLI 默认使用 JSON graph backend。Seeded demo API 默认使用内存 store，除非通过持久化 settings 启动。若要让 API 或 CLI graph 操作指向 Neo4j，请安装可选依赖并设置环境变量：

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

如需把同一个 `scene_generation` 流程放到真实 LangGraph `StateGraph` 和 SQLite checkpoint 上运行，安装可选依赖并设置：

```powershell
python -m pip install -e ".[langgraph]"
$env:STORYGRAPH_WORKFLOW_RUNTIME="langgraph"
```

LangGraph checkpoint 会保存在 StoryGraph workspace 下的 `langgraph_checkpoints.sqlite`。公开 API/CLI run panel 仍读取稳定的 `workflow_run_v1` 投影，即 `workflows.sqlite`；canon 写入仍然只由明确的 ReviewService 决策触发。

## Canon 安全规则

- Graph Store 是 canon 状态的唯一真相源。
- 草稿文本、生成摘要、导入文本、风格样本、UI sample data 和模型推测都不能直接改变 canon。
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
