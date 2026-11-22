# StoryGraph Agent

<a href="#user-content-readme-zh"><kbd>　简体中文　</kbd></a>　<a href="#user-content-readme-en"><kbd>　English　</kbd></a>　·　<a href="https://github.com/CZ0012/novelagent/releases/tag/v0.4.0">Windows v0.4.0</a>

<details name="readme-language" open>
<summary><strong>中文 · 点击展开 / 切换语言</strong></summary>

<a id="readme-zh"></a>
<a name="中文"></a>

[English ↓](#user-content-readme-en)

## 用一句灵感，开始一部长篇

StoryGraph Agent 是中文优先的本地小说写作工作台：**上方读写作品，下方与常驻主 Agent 对话**。主 Agent 把灵感、素材和反馈组织成待审设计，再协助规划、写作、修订与连续性检查。结构化图谱保存正典，草稿和推测保持隔离，作者决定什么进入作品与正典。

**Windows v0.4.0**：[下载与发布说明](https://github.com/CZ0012/novelagent/releases/tag/v0.4.0) · [最新发布](https://github.com/CZ0012/novelagent/releases/latest)。桌面版在 **设置 → 版本与更新** 检查和安装签名更新；浏览器版提供安装器下载入口。安装器、`setup.exe.sig` 和 `latest.json` 构成 Windows updater 通道。Tauri 更新签名与 Windows Authenticode 签名不同；本项目尚未提供后者。更新困难时参阅[Windows 更新恢复](docs/windows-update-recovery.md)。

### 回到写作现场

左侧在章节与会话间切换，支持按标题或消息搜索。新会话只需发送第一句话。启用自动命名时，系统会用同一连接上已知可用的轻量模型处理首句片段，额外发出一次短请求。没有合适模型或请求失败时保留首句标题，手动重命名优先。可在模型连接设置里关闭命名或指定标题模型。

在 **作品资料 → 项目笔记** 写下长期协作指令。主 Agent 可在正常对话中记录偏好、作者决定和待定灵感。每条记忆能查看原消息、修改或撤回。重新打开作品可恢复上次章场和会话，角色与 Writer 仍按本场授权获取信息。

### 从灵感到已审草稿

1. 在 Windows 模型设置中选 **Continue with ChatGPT**，在 OpenAI 官方页批准套餐使用，获取可用模型后，直接点 **保存并用于主 Agent**。只希望备用时选 **仅保存连接**。也可以继续使用 API Key 连接。套餐和 API 分别计量，ChatGPT 用量可在账号设置中管理。[官方用量说明](https://help.openai.com/en/articles/20001542-using-your-chatgpt-plan-in-other-apps-and-sites)
2. 在空工作台输入灵感，选择作品语言并发送；或打开已有项目，显式选择资料。界面语言与作品语言独立，切换界面不会翻译原稿。
3. 与主 Agent 讨论人物、情节和信息披露，比较方案后明确采用设计。正文下的对话持续跟随当前作品；分隔线可拖动或用方向键调整。
4. 让主 Agent 按本场需要从已配置的连接中选 Writer。进入写作时会显示所选模型与理由，可直接沿用或覆盖。核对 Writer 获准读取的内容后生成正文提案，由作者审阅。
5. 比较差异、修改并采用草稿；需要时核对保存稿精确版本和引文。候选事实仍须独立人工审阅才能进入 Graph canon。

主 Agent 按需要发现和读取六项内置写作 skills。这些是产品内的方法，不要求作者手动编排多个 Agent：

| Skill | 帮助作者完成 |
| --- | --- |
| [author-collaboration](storygraph/skills/author-collaboration/SKILL.md) | 从灵感开始对话、比较备选并形成待审设计 |
| [project-navigation](storygraph/skills/project-navigation/SKILL.md) | 找到当前章节、场景和相关工作区 |
| [character-perspective](storygraph/skills/character-perspective/SKILL.md) | 从角色有限认知推演行动、控制披露 |
| [review-and-revision](storygraph/skills/review-and-revision/SKILL.md) | 解释问题、区分证据与推断、追溯修订 |
| [exact-draft-evidence](storygraph/skills/exact-draft-evidence/SKILL.md) | 讨论获准选段，核对保存稿实际建立的内容 |
| [writer-and-canon](storygraph/skills/writer-and-canon/SKILL.md) | 从已批准设计走到正文提案与独立事实审阅 |

### 选择运行方式

| 入口 | 用途与边界 |
| --- | --- |
| Windows 桌面版 | 下载安装器即可使用；托管本地后端，后台控制台隐藏，关闭窗口后驻留托盘。支持签名程序内更新。 |
| API + Web | 开发者在本机分别启动持久后端与 React/Vite；与桌面共用工作流。 |
| CLI | 脚本式工作区、Context Pack、写作、检查和事实审阅；不提供完整主 Agent 会话界面。 |
| 源码构建桌面 | 本机 Tauri 构建产物；构建成功与发布、安装、程序内升级是不同证据。 |

以下命令在仓库根目录的 **PowerShell** 中执行（PowerShell 与 Windows PowerShell 是不同运行时）。Python 与 Node/npm 需先安装；桌面构建额外依赖见[桌面指南](apps/desktop/README.md)。

```powershell
python -m pip install -e ".[dev]"
npm --prefix apps/web install
```

持久化 API + Web：先在一个终端启动后端，再在另一个终端启动前端：

```powershell
$env:STORYGRAPH_HOME="D:\storygraph-workspaces\my-novel"
python -m apps.api.desktop_server
```

```powershell
npm --prefix apps/web run dev
```

打开 <http://127.0.0.1:5173>，API 地址使用 `http://127.0.0.1:8000`。后端使用持久 JSON graph 与 SQLite；未指定 `STORYGRAPH_HOME` 时，Windows 默认使用 `%LOCALAPPDATA%\StoryGraph Agent\workspace`。`apps.api.main:app` 默认是内存 seeded demo，不能替代持久写作入口。

CLI 创建空项目并查看命令（使用新的工作区路径）：

```powershell
python -m apps.cli.main init --workspace .storygraph-my-novel --empty --title "我的小说" --language zh-CN
python -m apps.cli.main --help
```

源码构建 Windows 桌面安装器：

```powershell
npm --prefix apps/desktop install
npm --prefix apps/desktop run build:installer
```

### 数据、隐私与正典边界

小说工作区、草稿、导入资料、项目设置、模型连接与审阅状态保存在本机；GitHub **仅分发软件发布与更新**，不同步小说。使用模型时，所选资料与获准上下文会发送到配置的模型服务商；“本地工作区”不表示模型调用离线。作者应核对发送前输入清单与所选服务商。

Graph Store 是正典真相源。生成正文、摘要、导入文档和模型假设不能直接改写正典；自动抽取只产生候选事实或提案。正式写入必须有明确人工决定、来源与事件日志。内置 skills 来自程序包，稿件或导入资料不能注册工具、替换 skill 或提升权限。

### 验收与进一步阅读

0.3.0 的真实作者试用覆盖两张已审场景卡、一份 **659 字符**保存稿及精确引文与后续设计变更复核；这不等于已验证所有长篇的一致性，也不等于五十万字正文生成验收。源码工作台集成、桌面打包、发布与实际升级另有各自证据。

- [0.4.0 工作台验收](docs/acceptance-0.4.0.md) · [0.3.1 登录与 Writer 交接验收](docs/acceptance-0.3.1.md) · [0.3.0 作者协作验收](docs/acceptance-0.3.0.md) · [0.2.0 框架验收](docs/acceptance-0.2.0.md)
- [架构与运行边界](docs/architecture.md) · [作者会话与主 Agent 合同](contracts/authoring_session_v1.md) · [全部版本化合同](contracts/)
- [桌面安装、构建与更新](apps/desktop/README.md) · [本地化](docs/localization.md) · [文档目录](docs/)
- [历史英文操作详解](docs/archive/readme-before-bilingual-en.md) · [历史中文操作详解](docs/archive/readme-before-bilingual-zh-CN.md)（旧版本快照，不代表当前发布状态）

开发验证：`python -m pytest`、`npm --prefix apps/web run build`。项目采用 [MIT License](LICENSE)。

</details>

<details name="readme-language">
<summary><strong>English · Expand / switch language</strong></summary>

<a id="readme-en"></a>

[中文 ↑](#user-content-readme-zh)

## Start a long story with one idea

StoryGraph Agent is a Chinese-first local fiction workbench: **read and write above, talk to the persistent Main Agent below**. The Main Agent turns ideas, selected materials and feedback into reviewable designs, then helps with planning, prose, revision and continuity checks. A structured graph holds canon; drafts and hypotheses stay separate, and the author decides what enters the manuscript and canon.

**Windows v0.4.0**: [Downloads and release notes](https://github.com/CZ0012/novelagent/releases/tag/v0.4.0) · [Latest release](https://github.com/CZ0012/novelagent/releases/latest). In the desktop app, use **Settings → Version & Updates** to check and install signed updates; browsers offer an installer download. The installer, `setup.exe.sig` and `latest.json` form the Windows updater channel. Tauri updater signing is separate from Windows Authenticode signing; the latter is not provided. See [Windows update recovery](docs/windows-update-recovery.md) if an update fails.

### Resume your writing desk

Switch between chapters and conversations in the sidebar. Search titles or messages to return to the original exchange. Start a conversation with one message. When enabled, automatic naming can use one short request on a known lightweight model on the same connection. The opening text remains the title if a model is unavailable, and manual renames take precedence. Model connection settings let you disable naming or specify a title model.

Open the project notebook to edit instructions and see the preferences, decisions and tentative ideas retained during your conversations. Follow a memory to its original message, edit it or withdraw it. Returning to a project restores the scene and conversation. The Writer and individual characters receive only their own permitted context.

### From idea to reviewed draft

1. In Windows model settings, choose **Continue with ChatGPT**, authorize plan usage on OpenAI's site, discover the available models, then choose **Save and use for Main Agent** or **Save connection only**. API-key connections are also available. Plan usage and API billing are separate, and ChatGPT account settings provide usage controls. [OpenAI usage guide](https://help.openai.com/en/articles/20001542-using-your-chatgpt-plan-in-other-apps-and-sites)
2. Enter an idea in the empty workbench, select the story language and send; or open an existing project and explicitly select materials. UI and story languages are independent; switching the UI never translates the manuscript.
3. Discuss characters, plot and disclosure with the Main Agent, compare alternatives and explicitly adopt a design. The conversation follows the current project below the manuscript; drag the divider or use arrow keys to adjust it.
4. Ask the Main Agent to pick a Writer for the scene from your configured connections. The writing action shows its choice and reason. Keep it or override it, preview the permitted inputs and generate a separate prose proposal for review.
5. Compare changes, edit and adopt a draft; reconcile the exact saved version and quotations when needed. Candidate facts still need independent human review before entering Graph canon.

The Main Agent discovers and reads six built-in writing skills as needed. These are product methods; authors do not need to orchestrate multiple agents manually:

| Skill | Helps the author |
| --- | --- |
| [author-collaboration](storygraph/skills/author-collaboration/SKILL.md) | Start from an idea, compare alternatives and prepare a pending design |
| [project-navigation](storygraph/skills/project-navigation/SKILL.md) | Find the current chapter, scene and relevant workspace |
| [character-perspective](storygraph/skills/character-perspective/SKILL.md) | Plan actions from limited character knowledge and control disclosure |
| [review-and-revision](storygraph/skills/review-and-revision/SKILL.md) | Explain findings, separate evidence from inference and trace revisions |
| [exact-draft-evidence](storygraph/skills/exact-draft-evidence/SKILL.md) | Discuss authorized passages and reconcile what saved prose establishes |
| [writer-and-canon](storygraph/skills/writer-and-canon/SKILL.md) | Move from approved design to prose proposals and independent fact review |

### Choose how to run

| Entry point | Purpose and boundary |
| --- | --- |
| Windows desktop | Install from the release; manages a local backend with a hidden console and stays in the tray when the window closes. Supports signed in-app updates. |
| API + Web | Developers start the persistent backend and React/Vite separately; shares the desktop workflow. |
| CLI | Scripted workspaces, Context Packs, writing, checks and fact review; does not expose the complete Main Agent session UI. |
| Source-built desktop | Local Tauri output; a successful build, publication, installation and in-app upgrade are distinct evidence. |

Run these commands from the repository root in **PowerShell** (a different runtime from Windows PowerShell). Install Python and Node/npm first; see the [desktop guide](apps/desktop/README.md) for additional desktop prerequisites.

```powershell
python -m pip install -e ".[dev]"
npm --prefix apps/web install
```

For persistent API + Web, start the backend in one terminal and the frontend in another:

```powershell
$env:STORYGRAPH_HOME="D:\storygraph-workspaces\my-novel"
python -m apps.api.desktop_server
```

```powershell
npm --prefix apps/web run dev
```

Open <http://127.0.0.1:5173> with API address `http://127.0.0.1:8000`. The backend uses a persistent JSON graph and SQLite; without `STORYGRAPH_HOME`, Windows defaults to `%LOCALAPPDATA%\StoryGraph Agent\workspace`. `apps.api.main:app` defaults to an in-memory seeded demo and is not the persistent authoring entry point.

Create an empty CLI project and inspect commands (use a new workspace path):

```powershell
python -m apps.cli.main init --workspace .storygraph-my-novel --empty --title "My Novel" --language en-US
python -m apps.cli.main --help
```

Build the Windows desktop installer from source:

```powershell
npm --prefix apps/desktop install
npm --prefix apps/desktop run build:installer
```

### Data, privacy and canon boundaries

Novel workspaces, drafts, imported materials, project settings, model connections and review state stay local. GitHub **distributes software releases and updates only**; it does not synchronize novels. Model calls send selected materials and authorized context to the configured provider: a local workspace does not make those calls offline. Check the input manifest and chosen provider before sending.

The Graph Store is the source of truth for canon. Generated prose, summaries, imports and model hypotheses cannot directly change canon; automated extraction produces candidates or proposals only. Canon writes require an explicit human decision, provenance and event logs. Built-in skills come from the application package; manuscripts and imported materials cannot register tools, replace skills or elevate permissions.

### Acceptance and further reading

The 0.3.0 real author trial covered two reviewed scene cards, one **659-character** saved prose sample, exact quotations and review after a later design change. It does not establish consistency for every novel or acceptance of 500,000 characters of generated prose. Source workbench integration, desktop packaging, publication and actual upgrades have separate evidence.

- [0.4.0 workbench checks](docs/acceptance-0.4.0.md) · [0.3.1 sign-in and Writer checks](docs/acceptance-0.3.1.md) · [0.3.0 author-collaboration acceptance](docs/acceptance-0.3.0.md) · [0.2.0 framework acceptance](docs/acceptance-0.2.0.md)
- [Architecture and runtime boundaries](docs/architecture.md) · [Author session and Main Agent contract](contracts/authoring_session_v1.md) · [All versioned contracts](contracts/)
- [Desktop installation, builds and updates](apps/desktop/README.md) · [Localization](docs/localization.md) · [Documentation directory](docs/)
- [Historical English operating guide](docs/archive/readme-before-bilingual-en.md) · [Historical Chinese operating guide](docs/archive/readme-before-bilingual-zh-CN.md) (older snapshots, not current release status)

Development checks: `python -m pytest`, `npm --prefix apps/web run build`. Licensed under the [MIT License](LICENSE).

</details>
