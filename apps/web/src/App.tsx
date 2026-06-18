import { invoke } from "@tauri-apps/api/core";
import {
  check as checkTauriUpdate,
  type Update as TauriUpdate
} from "@tauri-apps/plugin-updater";
import {
  Activity,
  AlertTriangle,
  BookOpen,
  Boxes,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  Database,
  Download,
  Eye,
  File as FileIcon,
  FileText,
  FileUp,
  Folder,
  FolderOpen,
  GitBranch,
  KeyRound,
  Library,
  Lock,
  Network,
  Play,
  RefreshCw,
  Save,
  Settings,
  ShieldCheck,
  SplitSquareVertical,
  Wand2,
  X
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AgentPermissionLevel,
  AgentSettings,
  AgentSettingsUpdate,
  CandidateFact,
  ContextPack,
  ContinuityReport,
  DemoSeedResult,
  Draft,
  SceneRunResult,
  WorkflowRun,
  WorkflowStep,
  apiGet,
  apiPost,
  apiPut
} from "./api";
import { demoProject } from "./sampleData";
import { APP_VERSION, GITHUB_LATEST_RELEASE_API } from "./version";
import "./styles.css";

const defaultDraft = `雨停之后，林瑾登上了旧钟楼。

钟提前响了。那声音太干净，也太刻意，像有人把信号送进石头深处。

他在钟架下方发现半枚黑色火漆，压在灰尘里。赫连雅看过来之前，他已经把它攥进掌心，也把骤然变重的怀疑藏了起来。`;

type InspectorTab = "context" | "continuity" | "facts" | "settings";
type LibraryDocumentKind = "txt" | "md" | "docx";
type LibraryDocumentStatus = "ready" | "error";

type LibraryDocument = {
  id: string;
  name: string;
  path: string;
  kind: LibraryDocumentKind;
  size: number;
  lastModified: number;
  content: string;
  status: LibraryDocumentStatus;
  error?: string;
  warnings: string[];
};

type LibraryTreeNode = {
  id: string;
  name: string;
  path: string;
  type: "folder" | "document";
  children: LibraryTreeNode[];
  document?: LibraryDocument;
};

type ImportSummary = {
  documents: LibraryDocument[];
  skipped: number;
  failed: number;
};

type UpdateStatus = {
  state: "idle" | "checking" | "current" | "available" | "installing" | "error";
  message: string;
  channel?: "desktop" | "github";
  latestVersion?: string;
  releaseUrl?: string;
  installerUrl?: string;
  publishedAt?: string;
  canInstall?: boolean;
};

type GitHubRelease = {
  tag_name?: string;
  html_url?: string;
  body?: string;
  published_at?: string;
  assets?: Array<{
    name: string;
    browser_download_url: string;
  }>;
};

type DirectoryInputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  directory?: string;
  webkitdirectory?: string;
};

const defaultAgentForm: AgentSettingsUpdate = {
  scene_writer: "rule_based",
  provider_label: "OpenAI 兼容",
  llm_base_url: "",
  llm_model: "deepseek-chat",
  llm_json_mode: true,
  permission_level: "full"
};

export default function App() {
  const [apiBase, setApiBase] = useState("http://127.0.0.1:8000");
  const [projectId, setProjectId] = useState(demoProject.projectId);
  const [sceneId, setSceneId] = useState(demoProject.sceneId);
  const [activeTab, setActiveTab] = useState<InspectorTab>("context");
  const [contextPack, setContextPack] = useState<ContextPack | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [draftText, setDraftText] = useState(defaultDraft);
  const [draftSummary, setDraftSummary] = useState("林瑾发现钟楼线索，但尚未得知血脉秘密。");
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [runEvents, setRunEvents] = useState<WorkflowStep[]>([]);
  const [continuityReport, setContinuityReport] = useState<ContinuityReport | null>(null);
  const [facts, setFacts] = useState<CandidateFact[]>([]);
  const [agentSettings, setAgentSettings] = useState<AgentSettings | null>(null);
  const [agentForm, setAgentForm] = useState<AgentSettingsUpdate>(defaultAgentForm);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [desktopUpdate, setDesktopUpdate] = useState<TauriUpdate | null>(null);
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus>({
    state: "idle",
    message: "尚未检查更新。"
  });
  const [libraryDocuments, setLibraryDocuments] = useState<LibraryDocument[]>([]);
  const [selectedLibraryDocumentId, setSelectedLibraryDocumentId] = useState<string | null>(null);
  const [expandedLibraryPaths, setExpandedLibraryPaths] = useState<Set<string>>(
    () => new Set(["library"])
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const endpoint = useMemo(
    () => `/projects/${projectId}/scenes/${sceneId}`,
    [projectId, sceneId]
  );
  const libraryTree = useMemo(
    () => buildLibraryTree(libraryDocuments),
    [libraryDocuments]
  );
  const selectedLibraryDocument = useMemo(
    () => libraryDocuments.find((document) => document.id === selectedLibraryDocumentId) ?? null,
    [libraryDocuments, selectedLibraryDocumentId]
  );

  const runAction = useCallback(async (label: string, action: () => Promise<void>) => {
    setBusy(label);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
    } finally {
      setBusy(null);
    }
  }, []);

  const addLibraryFiles = useCallback(async (files: File[]) => {
    const summary = await readLibraryFiles(files);
    if (!summary.documents.length) {
      setNotice(
        summary.skipped
          ? `没有找到支持的文档，已跳过 ${summary.skipped} 个文件。`
          : "没有选择文档。"
      );
      return;
    }

    setLibraryDocuments((current) => mergeLibraryDocuments(current, summary.documents));
    setExpandedLibraryPaths((current) => {
      const next = new Set(current);
      for (const document of summary.documents) {
        for (const path of getAncestorFolderPaths(document.path)) {
          next.add(path);
        }
      }
      return next;
    });

    const firstImported = summary.documents[0];
    setSelectedLibraryDocumentId(firstImported.id);

    const importedCount = summary.documents.length;
    const parts = [
      `已导入 ${importedCount} 个文档。`
    ];
    if (summary.failed) parts.push(`${summary.failed} 个需要检查。`);
    if (summary.skipped) parts.push(`已跳过 ${summary.skipped} 个不支持的文件。`);
    setNotice(parts.join(" "));
  }, []);

  const handleLibraryInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(event.currentTarget.files ?? []);
      event.currentTarget.value = "";
      if (!files.length) return;
      void runAction("import", () => addLibraryFiles(files));
    },
    [addLibraryFiles, runAction]
  );

  const toggleLibraryPath = useCallback((path: string) => {
    setExpandedLibraryPaths((current) => {
      const next = new Set(current);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  const clearLibrary = useCallback(async () => {
    setLibraryDocuments([]);
    setSelectedLibraryDocumentId(null);
    setExpandedLibraryPaths(new Set(["library"]));
    setNotice("本地资料已清空，canon（正典）未改变。");
  }, []);

  const refreshFacts = useCallback(async () => {
    const payload = await apiGet<{ facts: CandidateFact[] }>(
      apiBase,
      `/projects/${projectId}/facts/pending`
    );
    setFacts(payload.facts);
  }, [apiBase, projectId]);

  const refreshAgentSettings = useCallback(async () => {
    const settings = await apiGet<AgentSettings>(apiBase, "/settings/agent");
    setAgentSettings(settings);
    setAgentForm({
      scene_writer: settings.scene_writer,
      provider_label: settings.provider_label,
      llm_base_url: settings.llm_base_url,
      llm_model: settings.llm_model,
      llm_json_mode: settings.llm_json_mode,
      permission_level: settings.permission_level
    });
    setApiKeyInput("");
    setClearApiKey(false);
  }, [apiBase]);

  const saveAgentSettings = useCallback(async () => {
    const payload: AgentSettingsUpdate = {
      ...agentForm,
      llm_api_key: apiKeyInput ? apiKeyInput : null,
      clear_api_key: clearApiKey
    };
    const settings = await apiPut<AgentSettings>(apiBase, "/settings/agent", payload);
    setAgentSettings(settings);
    setAgentForm({
      scene_writer: settings.scene_writer,
      provider_label: settings.provider_label,
      llm_base_url: settings.llm_base_url,
      llm_model: settings.llm_model,
      llm_json_mode: settings.llm_json_mode,
      permission_level: settings.permission_level
    });
    setApiKeyInput("");
    setClearApiKey(false);
    setNotice("智能体设置已保存。");
  }, [agentForm, apiBase, apiKeyInput, clearApiKey]);

  const checkForUpdates = useCallback(async (silent = false) => {
    setDesktopUpdate(null);
    if (!silent) {
      setUpdateStatus({ state: "checking", message: "正在检查更新..." });
    }
    if (isDesktopRuntime()) {
      try {
        const update = await checkTauriUpdate();
        if (update) {
          setDesktopUpdate(update);
          setUpdateStatus({
            state: "available",
            channel: "desktop",
            message: `发现新版本 ${update.version}，可在程序内安装并重启。`,
            latestVersion: update.version,
            publishedAt: update.date,
            canInstall: true
          });
          return;
        }
        setUpdateStatus({
          state: "current",
          channel: "desktop",
          message: `当前已是最新版本 ${APP_VERSION}。`
        });
      } catch (exc) {
        setUpdateStatus({
          state: "error",
          channel: "desktop",
          message: `桌面更新通道暂不可用：${toErrorMessage(exc)}`
        });
      }
      return;
    }

    try {
      const response = await fetch(GITHUB_LATEST_RELEASE_API, {
        headers: { Accept: "application/vnd.github+json" }
      });
      if (response.status === 404) {
        setUpdateStatus({
          state: "current",
          channel: "github",
          message: "暂未发布 GitHub Release（发布版本），当前版本可继续使用。"
        });
        return;
      }
      if (!response.ok) {
        throw new Error(`GitHub 返回 ${response.status}`);
      }
      const release = (await response.json()) as GitHubRelease;
      const latestVersion = normalizeVersion(release.tag_name ?? "");
      if (!latestVersion) {
        throw new Error("最新 GitHub Release（发布版本）没有有效版本号");
      }
      const installer = release.assets?.find((asset) =>
        /StoryGraph Agent_.*_x64-setup\.exe$/i.test(asset.name)
      );
      const comparison = compareVersions(latestVersion, APP_VERSION);
      if (comparison > 0) {
        setUpdateStatus({
          state: "available",
          channel: "github",
          message: `发现新版本 ${latestVersion}，可直接下载 Windows 安装器。`,
          latestVersion,
          releaseUrl: release.html_url,
          installerUrl: installer?.browser_download_url,
          publishedAt: release.published_at
        });
        return;
      }
      setUpdateStatus({
        state: "current",
        channel: "github",
        message: `当前已是最新版本 ${APP_VERSION}。`,
        latestVersion,
        releaseUrl: release.html_url,
        publishedAt: release.published_at
      });
    } catch (exc) {
      setUpdateStatus({
        state: "error",
        channel: "github",
        message: `暂时无法检查更新：${toErrorMessage(exc)}`
      });
    }
  }, []);

  const installAvailableUpdate = useCallback(async () => {
    if (!desktopUpdate) {
      setUpdateStatus({
        state: "error",
        channel: "desktop",
        message: "没有可安装的桌面更新，请先检查更新。"
      });
      return;
    }

    setUpdateStatus({
      state: "installing",
      channel: "desktop",
      message: `正在下载并安装 v${desktopUpdate.version}，完成后会重启应用。`,
      latestVersion: desktopUpdate.version,
      publishedAt: desktopUpdate.date,
      canInstall: false
    });

    try {
      await invoke("stop_backend").catch(() => undefined);
      await desktopUpdate.downloadAndInstall();
      setUpdateStatus({
        state: "installing",
        channel: "desktop",
        message: "更新已安装，应用正在重启。",
        latestVersion: desktopUpdate.version,
        publishedAt: desktopUpdate.date
      });
    } catch (exc) {
      setUpdateStatus({
        state: "error",
        channel: "desktop",
        message: `安装更新失败：${toErrorMessage(exc)}`,
        latestVersion: desktopUpdate.version,
        publishedAt: desktopUpdate.date,
        canInstall: true
      });
    }
  }, [desktopUpdate]);

  const seedDemo = useCallback(async () => {
    const result = await apiPost<DemoSeedResult>(apiBase, "/demo/seed", {
      reviewer: "author",
      rationale: "作者从工作台明确初始化内置奇幻演示项目。",
      source_ref: "demo:workbench_seed"
    });
    setProjectId(result.project_id);
    setSceneId(result.scene_id);
    const pack = await apiPost<ContextPack>(
      apiBase,
      `/projects/${result.project_id}/scenes/${result.scene_id}/context-pack`
    );
    setContextPack(pack);
    setActiveTab("context");
    await refreshFacts();
    setNotice(
      `演示项目已就绪：写入 ${result.nodes_created} 个节点、${result.relationships_created} 条关系。`
    );
  }, [apiBase, refreshFacts]);

  const buildContext = useCallback(async () => {
    const pack = await apiPost<ContextPack>(apiBase, `${endpoint}/context-pack`);
    setContextPack(pack);
    setActiveTab("context");
    setNotice("上下文包已刷新。");
  }, [apiBase, endpoint]);

  const saveDraft = useCallback(async () => {
    const saved = await apiPost<Draft>(apiBase, `${endpoint}/draft`, {
      text: draftText,
      summary: draftSummary
    });
    setDraft(saved);
    setNotice(`草稿 v${saved.version} 已保存。`);
  }, [apiBase, draftSummary, draftText, endpoint]);

  const generateDraft = useCallback(async () => {
    const saved = await apiPost<Draft>(apiBase, `${endpoint}/draft`);
    setDraft(saved);
    setDraftText(saved.text);
    setDraftSummary(saved.summary ?? "");
    setNotice(`草稿 v${saved.version} 已生成。`);
  }, [apiBase, endpoint]);

  const runScene = useCallback(async () => {
    const result = await apiPost<SceneRunResult>(
      apiBase,
      `${endpoint}/runs/scene-generation`
    );
    setContextPack(result.context_pack);
    setDraft(result.draft);
    setDraftText(result.draft.text);
    setDraftSummary(result.draft.summary ?? "");
    setRun(result.workflow_run);
    setContinuityReport(result.continuity_report);
    setActiveTab(result.continuity_report.issues.length > 0 ? "continuity" : "context");
    const events = await apiGet<{ events: WorkflowStep[] }>(
      apiBase,
      `/runs/${result.workflow_run.id}/events`
    );
    setRunEvents(events.events);
    await refreshFacts();
    setNotice(`工作流状态：${formatStatus(result.workflow_run.status)}。`);
  }, [apiBase, endpoint, refreshFacts]);

  const reviewFact = useCallback(
    async (factId: string, action: "accept" | "reject" | "defer") => {
      await apiPost<CandidateFact>(
        apiBase,
        `/projects/${projectId}/facts/${factId}/${action}`,
        { reviewer: "author", note: `工作台执行：${reviewActionLabels[action]}` }
      );
      await refreshFacts();
      setNotice(`候选事实已${reviewActionLabels[action]}。`);
    },
    [apiBase, projectId, refreshFacts]
  );

  useEffect(() => {
    refreshFacts().catch(() => undefined);
  }, [refreshFacts]);

  useEffect(() => {
    refreshAgentSettings().catch(() => undefined);
  }, [refreshAgentSettings]);

  useEffect(() => {
    checkForUpdates(true).catch(() => undefined);
  }, [checkForUpdates]);

  const missingCritical = contextPack?.missing_context.some((gap) => gap.severity === "critical");
  const permission = agentSettings?.permission_level ?? "full";
  const canGenerate = permission === "read_generate" || permission === "full";
  const canReview = permission === "full";

  return (
    <div className="workbench">
      <header className="topbar">
        <div className="brand">
          <div className="mark"><GitBranch size={18} /></div>
          <div>
            <strong>StoryGraph Agent</strong>
            <span>长篇小说安全写作台</span>
          </div>
        </div>
        <label className="api-control">
          <Database size={15} />
          <input
            value={apiBase}
            onChange={(event) => setApiBase(event.target.value)}
            aria-label="API 地址"
          />
        </label>
        <div className="top-actions">
          <StatusDot label="FastAPI" tone="good" />
          <StatusDot label={permissionLabels[agentSettings?.permission_level ?? "full"]} tone={permissionTone(agentSettings?.permission_level)} />
          <StatusDot label={`v${APP_VERSION}`} tone="neutral" />
          <button className="icon-button" title="设置" type="button" onClick={() => setActiveTab("settings")}>
            <Settings size={17} />
          </button>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-section">
            <div className="section-title">项目</div>
            <div className="project-title">{demoProject.title}</div>
            <div className="project-id">{projectId}</div>
            <button
              className="sidebar-action"
              disabled={!canReview || busy !== null}
              onClick={() => runAction("seed-demo", seedDemo)}
              title={canReview ? "初始化内置演示项目" : "需要完全权限"}
              type="button"
            >
              <Database size={15} /> 初始化演示
            </button>
          </div>
          <nav className="scene-tree" aria-label="场景树">
            {demoProject.chapters.map((chapter) => (
              <div key={chapter.id} className="chapter">
                <div className="chapter-row">
                  <BookOpen size={15} />
                  <span>{chapter.title}</span>
                </div>
                {chapter.scenes.map((scene) => (
                  <button
                    key={scene.id}
                    className={`scene-row ${scene.id === sceneId ? "selected" : ""}`}
                    onClick={() => setSceneId(scene.id)}
                    type="button"
                  >
                    <ChevronRight size={14} />
                    <span>{scene.title}</span>
                    <small>{scene.status}</small>
                  </button>
                ))}
              </div>
            ))}
          </nav>
          <div className="sidebar-footer">
            <ShieldCheck size={16} />
            草稿不会直接改写 canon（正典）。
          </div>
        </aside>

        <main className="editor">
          <section className="scene-toolbar">
            <div>
              <h1>钟楼搜寻</h1>
              <p>{sceneId} / 视角 {contextPack?.pov_character_id ?? "character_linj"}</p>
            </div>
            <div className="toolbar-actions">
              <button onClick={() => runAction("context", buildContext)} type="button">
                <RefreshCw size={16} /> 上下文
              </button>
              <button onClick={() => runAction("save", saveDraft)} type="button" disabled={!canGenerate}>
                <Save size={16} /> 保存
              </button>
              <button
                onClick={() => runAction("draft", generateDraft)}
                type="button"
                disabled={missingCritical || !canGenerate}
              >
                <FileText size={16} /> 生成草稿
              </button>
              <button
                className="primary"
                onClick={() => runAction("run", runScene)}
                type="button"
                disabled={!canGenerate}
              >
                <Play size={16} /> 运行
              </button>
            </div>
          </section>

          {(error || notice) && (
            <div className={`message ${error ? "error" : "notice"}`}>
              {error ? <AlertTriangle size={16} /> : <Check size={16} />}
              <span>{error ?? notice}</span>
            </div>
          )}

          <section className="meta-grid" aria-label="场景元数据">
            <Meta label="目标" value={contextPack?.scene_goal ?? "寻找失踪的封印信"} />
            <Meta label="冲突" value={contextPack?.conflict ?? "钟楼由敌对势力控制"} />
            <Meta label="时间线" value={contextPack?.timeline_position ?? "王都政变三天后"} />
            <Meta label="地点" value={contextPack?.location_id ?? "location_old_bell_tower"} />
          </section>

          <section className="library-panel" aria-label="本地资料库">
            <div className="library-header">
              <div>
                <span><Library size={15} /> 本地资料 / 导入</span>
                <small>{libraryDocuments.length} 个本地文档 / 非 canon（正典）</small>
              </div>
              <div className="library-actions">
                <label className="import-button">
                  <FileUp size={15} />
                  文件
                  <input
                    accept=".txt,.md,.markdown,.docx"
                    multiple
                    onChange={handleLibraryInputChange}
                    type="file"
                  />
                </label>
                <label className="import-button">
                  <FolderOpen size={15} />
                  文件夹
                  <DirectoryInput
                    accept=".txt,.md,.markdown,.docx"
                    directory=""
                    multiple
                    onChange={handleLibraryInputChange}
                    type="file"
                    webkitdirectory=""
                  />
                </label>
                <button
                  onClick={() => runAction("clear-library", clearLibrary)}
                  type="button"
                  disabled={!libraryDocuments.length || busy === "import"}
                >
                  <X size={15} /> 清空
                </button>
              </div>
            </div>
            <div className="library-grid">
              <div className="library-tree-panel">
                {libraryDocuments.length ? (
                  <LibraryTree
                    expandedPaths={expandedLibraryPaths}
                    node={libraryTree}
                    onSelectDocument={setSelectedLibraryDocumentId}
                    onToggleFolder={toggleLibraryPath}
                    selectedDocumentId={selectedLibraryDocumentId}
                  />
                ) : (
                  <EmptyState
                    icon={<FolderOpen />}
                    title="还没有导入文档"
                    text="使用“文件”或“文件夹”把 txt、md、docx 加载到本地阅读器。"
                  />
                )}
              </div>
              <DocumentReader document={selectedLibraryDocument} />
            </div>
          </section>

          <section className="draft-surface">
            <div className="draft-header">
              <span>场景草稿</span>
              <small>{draft ? `v${draft.version} / ${draft.id}` : "本地未保存草稿"}</small>
            </div>
            <textarea
              value={draftText}
              onChange={(event) => setDraftText(event.target.value)}
              spellCheck={false}
              aria-label="场景草稿正文"
            />
            <input
              className="summary-input"
              value={draftSummary}
              onChange={(event) => setDraftSummary(event.target.value)}
              aria-label="草稿摘要"
            />
          </section>

          <section className="run-panel">
            <div className="run-head">
              <div>
                <span>智能体运行</span>
                <small>{run?.id ?? "尚未运行"}</small>
              </div>
              <StatusDot label={formatStatus(run?.status ?? "idle")} tone={statusTone(run?.status)} />
            </div>
            <div className="step-track">
              {(runEvents.length ? runEvents : fallbackSteps).map((step) => (
                <div key={step.name} className={`step ${step.status}`}>
                  <span>{stepLabels[step.name] ?? step.name}</span>
                  <small>{formatStatus(step.status)}</small>
                </div>
              ))}
            </div>
          </section>
        </main>

        <aside className="inspector">
          <div className="tabs" role="tablist">
            <TabButton active={activeTab === "context"} onClick={() => setActiveTab("context")} icon={<Boxes size={15} />} label="上下文" />
            <TabButton active={activeTab === "continuity"} onClick={() => setActiveTab("continuity")} icon={<Activity size={15} />} label="质检" />
            <TabButton active={activeTab === "facts"} onClick={() => setActiveTab("facts")} icon={<ShieldCheck size={15} />} label="事实" />
            <TabButton active={activeTab === "settings"} onClick={() => setActiveTab("settings")} icon={<Settings size={15} />} label="设置" />
          </div>
          {activeTab === "context" && <ContextInspector pack={contextPack} />}
          {activeTab === "continuity" && <ContinuityInspector run={run} report={continuityReport} />}
          {activeTab === "facts" && (
            <FactsInspector
              facts={facts}
              busy={busy}
              canReview={canReview}
              onReview={(factId, action) => runAction(action, () => reviewFact(factId, action))}
            />
          )}
          {activeTab === "settings" && (
            <AgentSettingsInspector
              apiKeyInput={apiKeyInput}
              busy={busy}
              clearApiKey={clearApiKey}
              form={agentForm}
              onApiKeyChange={setApiKeyInput}
              onClearApiKeyChange={setClearApiKey}
              onFormChange={setAgentForm}
              onRefresh={() => runAction("settings", refreshAgentSettings)}
              onSave={() => runAction("settings", saveAgentSettings)}
              onInstallUpdate={() => runAction("update-install", installAvailableUpdate)}
              onUpdateCheck={() => runAction("update-check", () => checkForUpdates(false))}
              settings={agentSettings}
              updateStatus={updateStatus}
            />
          )}
          <GraphPreview />
        </aside>
      </div>
    </div>
  );
}

function DirectoryInput(props: DirectoryInputProps) {
  return <input {...props} />;
}

function LibraryTree({
  expandedPaths,
  node,
  onSelectDocument,
  onToggleFolder,
  selectedDocumentId
}: {
  expandedPaths: Set<string>;
  node: LibraryTreeNode;
  onSelectDocument: (documentId: string) => void;
  onToggleFolder: (path: string) => void;
  selectedDocumentId: string | null;
}) {
  return (
    <div className="library-tree">
      {node.children.map((child) => (
        <LibraryTreeItem
          expandedPaths={expandedPaths}
          key={child.id}
          level={0}
          node={child}
          onSelectDocument={onSelectDocument}
          onToggleFolder={onToggleFolder}
          selectedDocumentId={selectedDocumentId}
        />
      ))}
    </div>
  );
}

function LibraryTreeItem({
  expandedPaths,
  level,
  node,
  onSelectDocument,
  onToggleFolder,
  selectedDocumentId
}: {
  expandedPaths: Set<string>;
  level: number;
  node: LibraryTreeNode;
  onSelectDocument: (documentId: string) => void;
  onToggleFolder: (path: string) => void;
  selectedDocumentId: string | null;
}) {
  const indent = { paddingLeft: `${8 + level * 14}px` };

  if (node.type === "folder") {
    const isExpanded = expandedPaths.has(node.path);
    return (
      <div className="library-node-group">
        <button
          aria-expanded={isExpanded}
          className="library-node folder"
          onClick={() => onToggleFolder(node.path)}
          style={indent}
          title={node.path}
          type="button"
        >
          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          {isExpanded ? <FolderOpen size={15} /> : <Folder size={15} />}
          <span>{node.name}</span>
          <small>{countDocuments(node)}</small>
        </button>
        {isExpanded && (
          <div>
            {node.children.map((child) => (
              <LibraryTreeItem
                expandedPaths={expandedPaths}
                key={child.id}
                level={level + 1}
                node={child}
                onSelectDocument={onSelectDocument}
                onToggleFolder={onToggleFolder}
                selectedDocumentId={selectedDocumentId}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  const document = node.document;
  if (!document) return null;

  return (
    <button
      className={`library-node document ${document.id === selectedDocumentId ? "selected" : ""} ${document.status}`}
      onClick={() => onSelectDocument(document.id)}
      style={indent}
      title={document.path}
      type="button"
    >
      {document.kind === "docx" ? <FileText size={15} /> : <FileIcon size={15} />}
      <span>{document.name}</span>
      <small>{document.kind.toUpperCase()}</small>
    </button>
  );
}

function DocumentReader({ document: doc }: { document: LibraryDocument | null }) {
  if (!doc) {
    return (
      <div className="document-reader empty">
        <EmptyState
          icon={<Library />}
          title="选择一个文档"
          text="导入内容只保存在浏览器内存中。"
        />
      </div>
    );
  }

  return (
    <div className="document-reader">
      <div className="reader-head">
        <div>
          <strong>{doc.name}</strong>
          <span>{doc.path}</span>
        </div>
        <div className="reader-tags">
          <span>{doc.kind.toUpperCase()}</span>
          <span>{formatFileSize(doc.size)}</span>
        </div>
      </div>
      {doc.status === "error" ? (
        <div className="reader-error">
          <AlertTriangle size={17} />
          <strong>无法读取这个文档。</strong>
          <span>{doc.error}</span>
        </div>
      ) : (
        <>
          {doc.warnings.length > 0 && (
            <div className="reader-warning">
              <AlertTriangle size={15} />
              <span>{doc.warnings.slice(0, 2).join(" ")}</span>
            </div>
          )}
          <pre>{doc.content}</pre>
        </>
      )}
    </div>
  );
}

function AgentSettingsInspector({
  apiKeyInput,
  busy,
  clearApiKey,
  form,
  onApiKeyChange,
  onClearApiKeyChange,
  onFormChange,
  onRefresh,
  onSave,
  onInstallUpdate,
  onUpdateCheck,
  settings,
  updateStatus
}: {
  apiKeyInput: string;
  busy: string | null;
  clearApiKey: boolean;
  form: AgentSettingsUpdate;
  onApiKeyChange: (value: string) => void;
  onClearApiKeyChange: (value: boolean) => void;
  onFormChange: React.Dispatch<React.SetStateAction<AgentSettingsUpdate>>;
  onRefresh: () => void;
  onSave: () => void;
  onInstallUpdate: () => void;
  onUpdateCheck: () => void;
  settings: AgentSettings | null;
  updateStatus: UpdateStatus;
}) {
  const descriptions = settings?.permission_descriptions ?? defaultPermissionDescriptions;
  const apiKeyStatus = settings?.api_key_configured
    ? `已配置（${settings.api_key_preview ?? "隐藏"}）`
    : "未配置";
  const updateTarget = updateStatus.installerUrl ?? updateStatus.releaseUrl;

  return (
    <div className="settings-panel">
      <section className="settings-block">
        <div className="settings-title"><Wand2 size={15} /> 核心模型</div>
        <label>
          <span>写作模式</span>
          <select
            value={form.scene_writer}
            onChange={(event) =>
              onFormChange((current) => ({
                ...current,
                scene_writer: event.target.value as AgentSettingsUpdate["scene_writer"]
              }))
            }
          >
            <option value="rule_based">本地规则模式</option>
            <option value="llm">OpenAI 兼容 LLM</option>
          </select>
        </label>
        <label>
          <span>供应商名称</span>
          <input
            value={form.provider_label}
            onChange={(event) =>
              onFormChange((current) => ({ ...current, provider_label: event.target.value }))
            }
          />
        </label>
        <label>
          <span>基础 URL</span>
          <input
            placeholder="https://provider.example/v1"
            value={form.llm_base_url}
            onChange={(event) =>
              onFormChange((current) => ({ ...current, llm_base_url: event.target.value }))
            }
          />
        </label>
        <label>
          <span>模型</span>
          <input
            value={form.llm_model}
            onChange={(event) =>
              onFormChange((current) => ({ ...current, llm_model: event.target.value }))
            }
          />
        </label>
        <label className="checkbox-row">
          <input
            checked={form.llm_json_mode}
            onChange={(event) =>
              onFormChange((current) => ({ ...current, llm_json_mode: event.target.checked }))
            }
            type="checkbox"
          />
          <span>请求 JSON 模式</span>
        </label>
      </section>

      <section className="settings-block">
        <div className="settings-title"><KeyRound size={15} /> API 密钥</div>
        <MetricRow label="当前密钥" value={apiKeyStatus} />
        <label>
          <span>替换密钥</span>
          <input
            autoComplete="off"
            placeholder="留空表示保留现有密钥"
            type="password"
            value={apiKeyInput}
            onChange={(event) => onApiKeyChange(event.target.value)}
          />
        </label>
        <label className="checkbox-row">
          <input
            checked={clearApiKey}
            onChange={(event) => onClearApiKeyChange(event.target.checked)}
            type="checkbox"
          />
          <span>清除已保存密钥</span>
        </label>
      </section>

      <section className="settings-block">
        <div className="settings-title"><Lock size={15} /> 权限级别</div>
        <div className="permission-stack">
          {permissionLevels.map((level) => (
            <label className={`permission-option ${form.permission_level === level ? "selected" : ""}`} key={level}>
              <input
                checked={form.permission_level === level}
                name="permission"
                onChange={() =>
                  onFormChange((current) => ({ ...current, permission_level: level }))
                }
                type="radio"
              />
              {permissionIcon(level)}
              <span>
                <strong>{permissionLabels[level]}</strong>
                <small>{descriptions[level]}</small>
              </span>
            </label>
          ))}
        </div>
        {settings && !canRaisePermission(settings.permission_level, form.permission_level) && (
          <div className="reader-warning">
            <AlertTriangle size={15} />
            <span>API 会阻止自行升权；如需重新升权，请有意编辑本地配置。</span>
          </div>
        )}
      </section>

      <section className="settings-block">
        <div className="settings-title"><Download size={15} /> 版本与更新</div>
        <MetricRow label="当前版本" value={`v${APP_VERSION}`} />
        <div className={`update-card ${updateStatus.state}`}>
          <span>{updateStatus.message}</span>
          {updateStatus.publishedAt && (
            <small>发布时间：{formatDateTime(updateStatus.publishedAt)}</small>
          )}
          {updateStatus.channel === "desktop" && (
            <small>桌面版使用 Tauri 签名更新；网页版只提供 GitHub Release（发布版本）下载提示。</small>
          )}
          {updateStatus.state === "available" && updateStatus.canInstall && (
            <button
              className="inline-update-button"
              onClick={onInstallUpdate}
              type="button"
              disabled={busy === "update-install"}
            >
              <Download size={14} /> 安装更新并重启
            </button>
          )}
          {updateStatus.state === "available" && !updateStatus.canInstall && updateTarget && (
            <a href={updateTarget} target="_blank" rel="noreferrer">
              <Download size={14} /> 下载新版安装器
            </a>
          )}
        </div>
      </section>

      <div className="settings-actions">
        <button onClick={onRefresh} type="button" disabled={busy === "settings"}>
          <RefreshCw size={15} /> 刷新
        </button>
        <button onClick={onUpdateCheck} type="button" disabled={busy === "update-check"}>
          <RefreshCw size={15} /> 检查更新
        </button>
        <button className="primary" onClick={onSave} type="button" disabled={busy === "settings"}>
          <Save size={15} /> 保存设置
        </button>
      </div>
    </div>
  );
}

function ContextInspector({ pack }: { pack: ContextPack | null }) {
  if (!pack) {
    return <EmptyState icon={<SplitSquareVertical />} title="暂无上下文包" text="构建上下文后可检查 canon（正典）、预算和缺口。" />;
  }
  return (
    <div className="inspector-body">
      <MetricRow label="预算" value={`${pack.budget.estimated_tokens}/${pack.budget.target_tokens}`} />
      <MetricRow label="图查询" value={String(pack.provenance.graph_query_ids.length)} />
      <ListBlock title="必须包含" items={pack.must_include} />
      <ListBlock title="禁止违反" items={pack.must_not_violate} tone="danger" />
      <ListBlock title="关系" items={pack.active_relationships} />
      <ListBlock title="伏笔" items={pack.unresolved_foreshadowing} />
      <ListBlock title="缺失上下文" items={pack.missing_context.map((gap) => `${formatSeverity(gap.severity)}: ${gap.ref} - ${formatKnownMessage(gap.message)}`)} tone="warning" />
      <ListBlock title="已丢弃项目" items={pack.budget.dropped_items} />
    </div>
  );
}

function ContinuityInspector({ run, report }: { run: WorkflowRun | null; report: ContinuityReport | null }) {
  const blockingCount = report?.issues.filter((issue) => issue.blocking).length ?? 0;
  return (
    <div className="inspector-body">
      <MetricRow label="当前步骤" value={stepLabels[run?.current_step ?? ""] ?? "无"} />
      <MetricRow label="审阅载荷" value={formatStatus(run?.review_payload.status ?? "none")} />
      <MetricRow label="连续性" value={formatStatus(report?.status ?? "not checked")} />
      <MetricRow label="阻塞问题" value={String(blockingCount)} />
      {report ? (
        <>
          <ListBlock title="摘要" items={[report.summary]} />
          <ListBlock title="检查维度" items={report.checked_dimensions.map(formatDimension)} />
          <ListBlock
            title="问题"
            items={report.issues.map((issue) => `${formatSeverity(issue.severity)}: ${formatIssueType(issue.issue_type)} - ${formatKnownMessage(issue.description)} 建议：${formatKnownMessage(issue.suggestion)}`)}
            tone={blockingCount > 0 ? "danger" : "warning"}
          />
        </>
      ) : (
        <EmptyState icon={<Activity />} title="暂无质检报告" text="运行场景工作流后可查看连续性检查结果。" />
      )}
      <ListBlock
        title="运行步骤"
        items={(run?.steps ?? fallbackSteps).map((step) => `${stepLabels[step.name] ?? step.name}: ${formatStatus(step.status)}${step.message ? ` - ${formatKnownMessage(step.message)}` : ""}`)}
      />
    </div>
  );
}

function FactsInspector({
  canReview,
  facts,
  busy,
  onReview
}: {
  canReview: boolean;
  facts: CandidateFact[];
  busy: string | null;
  onReview: (factId: string, action: "accept" | "reject" | "defer") => void;
}) {
  if (!facts.length) {
    return <EmptyState icon={<ShieldCheck />} title="暂无待审事实" text="抽取出的状态变化会在这里等待人工审阅。" />;
  }
  return (
    <div className="fact-list">
      {facts.map((fact) => (
        <div className="fact-row" key={fact.id}>
          <div>
            <strong>{fact.fact_type}</strong>
            <span>{fact.subject_id} {fact.relation} {fact.object_id ?? ""}</span>
          </div>
          <p>{fact.rationale}</p>
          <div className="fact-actions">
            <button onClick={() => onReview(fact.id, "accept")} disabled={busy !== null || !canReview} type="button"><Check size={14} />接受</button>
            <button onClick={() => onReview(fact.id, "defer")} disabled={busy !== null || !canReview} type="button"><Clock3 size={14} />稍后</button>
            <button onClick={() => onReview(fact.id, "reject")} disabled={busy !== null || !canReview} type="button"><X size={14} />拒绝</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function GraphPreview() {
  return (
    <div className="graph-preview">
      <div className="preview-title"><Network size={15} /> 图谱 / 时间线</div>
      <div className="graph-lines">
        {demoProject.graphPreview.map((edge) => (
          <div key={`${edge.source}-${edge.edge}-${edge.target}`}>
            <span>{edge.source}</span><b>{edge.edge}</b><span>{edge.target}</span>
          </div>
        ))}
      </div>
      <div className="timeline">
        {demoProject.timeline.map((item) => (
          <div key={item.label} className={item.state}>{item.label}</div>
        ))}
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return <div className="meta"><span>{label}</span><strong>{value || "缺失"}</strong></div>;
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return <div className="metric-row"><span>{label}</span><strong>{value}</strong></div>;
}

function ListBlock({ title, items, tone }: { title: string; items: string[]; tone?: "danger" | "warning" }) {
  return (
    <section className={`list-block ${tone ?? ""}`}>
      <div className="list-title">{title}</div>
      {items.length ? items.map((item) => <p key={item}>{item}</p>) : <p className="muted">无</p>}
    </section>
  );
}

function TabButton({ active, onClick, icon, label }: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string }) {
  return <button className={active ? "active" : ""} onClick={onClick} type="button">{icon}{label}</button>;
}

function StatusDot({ label, tone }: { label: string; tone: "good" | "warning" | "danger" | "neutral" }) {
  return <span className={`status-dot ${tone}`}><i />{label}</span>;
}

function EmptyState({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return <div className="empty-state">{icon}<strong>{title}</strong><span>{text}</span></div>;
}

function statusTone(status?: string | null): "good" | "warning" | "danger" | "neutral" {
  if (status === "completed") return "good";
  if (status === "awaiting_review" || status === "needs_revision") return "warning";
  if (status === "blocked" || status === "failed") return "danger";
  return "neutral";
}

function permissionTone(permission?: AgentPermissionLevel | null): "good" | "warning" | "danger" | "neutral" {
  if (permission === "full") return "good";
  if (permission === "read_generate") return "warning";
  if (permission === "read_only") return "neutral";
  return "neutral";
}

function permissionIcon(level: AgentPermissionLevel) {
  if (level === "read_only") return <Eye size={16} />;
  if (level === "read_generate") return <Wand2 size={16} />;
  return <ShieldCheck size={16} />;
}

function canRaisePermission(
  current: AgentPermissionLevel,
  next: AgentPermissionLevel
): boolean {
  return permissionRank[next] <= permissionRank[current];
}

const permissionLevels: AgentPermissionLevel[] = ["read_only", "read_generate", "full"];

const permissionRank: Record<AgentPermissionLevel, number> = {
  read_only: 0,
  read_generate: 1,
  full: 2
};

const permissionLabels: Record<AgentPermissionLevel, string> = {
  read_only: "仅读取",
  read_generate: "可读取生成",
  full: "完全权限"
};

const defaultPermissionDescriptions: Record<AgentPermissionLevel, string> = {
  read_only: "只能读取 canon（正典）、草稿、上下文包、运行记录和待审事实。",
  read_generate: "可读取并生成草稿、检查结果、候选事实和风格样本。",
  full: "允许完整本地作者操作，包括人工初始化（seed）和 CandidateFact（候选事实）审阅决策。"
};

const stepLabels: Record<string, string> = {
  build_context: "构建上下文",
  write_draft: "写作草稿",
  check_continuity: "连续性检查",
  extract_state: "抽取状态",
  human_review: "人工审阅"
};

const statusLabels: Record<string, string> = {
  idle: "空闲",
  pending: "等待中",
  running: "运行中",
  completed: "已完成",
  pass: "通过",
  awaiting_review: "等待审阅",
  needs_revision: "需要修订",
  blocked: "已阻塞",
  failed: "失败",
  skipped: "已跳过",
  inconclusive: "未定",
  none: "无",
  "not checked": "未检查"
};

const severityLabels: Record<string, string> = {
  critical: "严重",
  high: "高",
  medium: "中",
  low: "低"
};

const dimensionLabels: Record<string, string> = {
  knowledge_boundary: "人物知识边界",
  timeline: "时间线",
  location_state: "地点状态",
  relationship_state: "关系状态",
  world_rule: "世界规则"
};

const issueTypeLabels: Record<string, string> = {
  knowledge_boundary_violation: "人物知识边界违规",
  timeline_conflict: "时间线冲突",
  location_conflict: "地点冲突",
  relationship_conflict: "关系冲突",
  world_rule_conflict: "世界规则冲突",
  missing_required_element: "缺少必要元素",
  unsupported_new_fact: "未支持的新事实",
  style_drift: "文风漂移",
  foreshadowing_mismatch: "伏笔不匹配",
  causal_gap: "因果缺口",
  pov_leak: "视角泄露"
};

const knownMessageLabels: Record<string, string> = {
  "Human review completed.": "人工审阅已完成。"
};

const reviewActionLabels = {
  accept: "接受",
  reject: "拒绝",
  defer: "延后"
} as const;

async function readLibraryFiles(files: File[]): Promise<ImportSummary> {
  let skipped = 0;
  const candidates: Array<{ file: File; index: number }> = [];

  files.forEach((file, index) => {
    if (getDocumentKind(file.name)) {
      candidates.push({ file, index });
    } else {
      skipped += 1;
    }
  });

  const documents = await Promise.all(
    candidates.map(({ file, index }) => readLibraryDocument(file, index))
  );

  return {
    documents,
    skipped,
    failed: documents.filter((document) => document.status === "error").length
  };
}

async function readLibraryDocument(file: File, index: number): Promise<LibraryDocument> {
  const kind = getDocumentKind(file.name) ?? "txt";
  const path = getImportPath(file);
  const base = {
    id: createDocumentId(path, file, index),
    name: file.name,
    path,
    kind,
    size: file.size,
    lastModified: file.lastModified,
    warnings: []
  };

  try {
    if (kind === "docx") {
      const result = await readDocxText(file);
      return {
        ...base,
        content: normalizeImportedText(result.text),
        status: "ready",
        warnings: result.warnings
      };
    }

    return {
      ...base,
      content: normalizeImportedText(await file.text()),
      status: "ready"
    };
  } catch (exc) {
    return {
      ...base,
      content: "",
      status: "error",
      error:
        kind === "docx"
          ? `DOCX 文本抽取不可用或失败：${toErrorMessage(exc)}`
          : toErrorMessage(exc)
    };
  }
}

async function readDocxText(file: File): Promise<{ text: string; warnings: string[] }> {
  type MammothApi = {
    extractRawText: (input: { arrayBuffer: ArrayBuffer }) => Promise<{
      value: string;
      messages: Array<{ message: string }>;
    }>;
  };

  const mammothModule = await import("mammoth/lib/index");
  const mammoth =
    (mammothModule as unknown as { default?: MammothApi }).default ??
    (mammothModule as unknown as MammothApi);
  const result = await mammoth.extractRawText({ arrayBuffer: await file.arrayBuffer() });

  return {
    text: result.value,
    warnings: result.messages.map((message) => message.message)
  };
}

function buildLibraryTree(documents: LibraryDocument[]): LibraryTreeNode {
  const root: LibraryTreeNode = {
    id: "library",
    name: "本地资料",
    path: "library",
    type: "folder",
    children: []
  };

  for (const document of documents) {
    const parts = document.path.split("/").filter(Boolean);
    let current = root;

    parts.slice(0, -1).forEach((part, index) => {
      const folderPath = `library/${parts.slice(0, index + 1).join("/")}`;
      let folder = current.children.find(
        (child) => child.type === "folder" && child.path === folderPath
      );
      if (!folder) {
        folder = {
          id: `folder:${folderPath}`,
          name: part,
          path: folderPath,
          type: "folder",
          children: []
        };
        current.children.push(folder);
      }
      current = folder;
    });

    current.children.push({
      id: `document:${document.id}`,
      name: document.name,
      path: document.path,
      type: "document",
      children: [],
      document
    });
  }

  sortLibraryNode(root);
  return root;
}

function sortLibraryNode(node: LibraryTreeNode) {
  node.children.sort((a, b) => {
    if (a.type !== b.type) return a.type === "folder" ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  node.children.forEach(sortLibraryNode);
}

function mergeLibraryDocuments(
  current: LibraryDocument[],
  incoming: LibraryDocument[]
): LibraryDocument[] {
  const documents = new Map(current.map((document) => [document.id, document]));
  incoming.forEach((document) => documents.set(document.id, document));
  return Array.from(documents.values());
}

function getAncestorFolderPaths(path: string): string[] {
  const parts = path.split("/").filter(Boolean);
  const ancestors = ["library"];
  for (let index = 0; index < parts.length - 1; index += 1) {
    ancestors.push(`library/${parts.slice(0, index + 1).join("/")}`);
  }
  return ancestors;
}

function getImportPath(file: File): string {
  const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath;
  return normalizeImportPath(relativePath || file.name);
}

function normalizeImportPath(path: string): string {
  return path.replace(/\\/g, "/").split("/").filter(Boolean).join("/");
}

function createDocumentId(path: string, file: File, index: number): string {
  return `${path}::${file.size}::${file.lastModified}::${index}`;
}

function getDocumentKind(fileName: string): LibraryDocumentKind | null {
  const normalizedName = fileName.toLowerCase();
  if (normalizedName.endsWith(".txt")) return "txt";
  if (normalizedName.endsWith(".md") || normalizedName.endsWith(".markdown")) return "md";
  if (normalizedName.endsWith(".docx")) return "docx";
  return null;
}

function normalizeImportedText(text: string): string {
  const normalized = text.replace(/\r\n?/g, "\n").trim();
  return normalized || "这个文档中没有可读取文本。";
}

function countDocuments(node: LibraryTreeNode): number {
  if (node.type === "document") return 1;
  return node.children.reduce((total, child) => total + countDocuments(child), 0);
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function toErrorMessage(exc: unknown): string {
  return exc instanceof Error ? exc.message : String(exc);
}

function isDesktopRuntime(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function normalizeVersion(version: string): string {
  return version.trim().replace(/^v/i, "");
}

function compareVersions(a: string, b: string): number {
  const left = normalizeVersion(a).split(".").map((part) => Number.parseInt(part, 10) || 0);
  const right = normalizeVersion(b).split(".").map((part) => Number.parseInt(part, 10) || 0);
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    const delta = (left[index] ?? 0) - (right[index] ?? 0);
    if (delta !== 0) return delta;
  }
  return 0;
}

function formatDateTime(value: string): string {
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      dateStyle: "medium",
      timeStyle: "short"
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function formatStatus(status: string | null | undefined): string {
  if (!status) return "无";
  return statusLabels[status] ?? status;
}

function formatSeverity(severity: string): string {
  return severityLabels[severity] ?? severity;
}

function formatDimension(dimension: string): string {
  return dimensionLabels[dimension] ?? dimension;
}

function formatIssueType(issueType: string): string {
  return issueTypeLabels[issueType] ?? issueType;
}

function formatKnownMessage(message: string): string {
  return knownMessageLabels[message] ?? message;
}

const fallbackSteps: WorkflowStep[] = [
  { name: "build_context", status: "pending", artifact_refs: {} },
  { name: "write_draft", status: "pending", artifact_refs: {} },
  { name: "check_continuity", status: "pending", artifact_refs: {} },
  { name: "extract_state", status: "pending", artifact_refs: {} },
  { name: "human_review", status: "pending", artifact_refs: {} }
];
