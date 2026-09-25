# Localization and writing language

## Separate language resources

The Web/Tauri workbench loads exactly the requested UI catalog through dynamic imports in `apps/web/src/localization/index.ts`. `zh-CN.ts` and `en-US.ts` compile into separate production chunks, cached after loading. Bootstrap waits for a complete catalog before mounting the app. A failed switch retains the previous complete language; development hot reload preserves initialized labels.

To add a display language, copy a catalog, satisfy `LocaleCatalog` from `schema.ts`, and add its dynamic loader and native display name to `localeRegistry`. Run `npm --prefix apps/web test` and `npm --prefix apps/web run build`. Catalog tests compare complete key paths and interpolation/function shape; author prose, custom preset names and prompts must remain verbatim. Project output languages are separately versioned by `language_policy_v1` and do not expand merely by adding a UI catalog.

Native desktop window titles, tray commands, and native error messages live in `apps/desktop/src-tauri/localization/zh-CN.json` and `en-US.json`. `src/localization.rs` parses and caches the selected catalog on demand; assets are embedded for offline packaging. Add a locale registry case there when extending desktop support. Rust tests compare all message keys and placeholders. Dynamic paths and error details are inserted once, preventing placeholder text inside an author path from being interpreted again.

Built-in preset names and descriptions use UI catalogs. System prompt content remains visible in its authored form and is never silently translated. A Chinese preset contains conditional Chinese-writing guidance; it cannot change an English project's output language.

## 本地化与正文语言

Web 与桌面工作台的 `zh-CN.ts`、`en-US.ts` 分别打包，按需加载。首次启动先载入完整语言包再显示应用；切换失败时保留当前语言。新增界面语言只需新增符合 `LocaleCatalog` 的文件并注册加载入口，再运行目录完整性测试与构建。

桌面原生窗口、托盘与错误消息另存为 `src-tauri/localization/` 下的 JSON 文件，运行时只解析所选语言，打包后可离线使用。新增原生语言需同步 `src/localization.rs` 注册项；Rust 测试检查消息与占位符对应关系。

界面语言是本机偏好，小说输出语言由项目决定，来源资料语言则描述原文。自定义预设名称、System prompt、小说、资料和历史提案不会因界面切换被翻译。新增界面语言不会自动扩大后端允许的项目输出语言；后者需独立更新语言合同和校验。


## Outline language and historical content

Known project genre identifiers are localized only for display. Unknown genre values and author titles are preserved. A chapter/scene title is persisted project content, not a UI catalog key. Switching the interface or upgrading the application does not translate old outlines. Authors can edit chapter/scene metadata through explicit save actions.

Structure generation and first application validate authored title/summary fields against the frozen project output language, including obvious short foreign-language headings. This is a conservative heuristic, not general language identification; proper-name labels and verified completed applications retain their compatibility boundaries. No rejected output triggers an automatic paid retry.

已保存的英文目录属于历史作品内容，升级不会自动翻译；可通过章节/场景信息明确改名并保存。新结构会校验标题与摘要的项目语言，减少短英文标题漏检；AI、人物和地点专名仍允许保留原样。
