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
  Redo2,
  RefreshCw,
  Save,
  Settings,
  ShieldCheck,
  SplitSquareVertical,
  Undo2,
  Wand2,
  X
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AgentPermissionLevel,
  AgentSettings,
  AgentSettingsUpdate,
  CandidateFact,
  ChapterOutline,
  ContextPack,
  ContinuityReport,
  DemoArchiveResult,
  DocumentFactExtractionResult,
  Draft,
  GraphNodePayload,
  ProposalArtifact,
  ProposalArtifactType,
  ProposalCandidatePromotionResult,
  ProposalDraftPromotionResult,
  ProjectStructureApplyResult,
  ProjectStructureDraftResult,
  ProposalStatus,
  ProjectGraphPreview,
  ProjectOutline,
  SceneOutline,
  SceneRunResult,
  WorkflowRun,
  WorkflowStep,
  apiGet,
  apiPatch,
  apiPost,
  apiPut
} from "./api";
import { localizeStatus, localizeText } from "./localization";
import { APP_VERSION, GITHUB_LATEST_RELEASE_API } from "./version";
import "./styles.css";

type InspectorTab = "context" | "continuity" | "facts" | "settings";
type WorkspaceTab = "write" | "sources" | "proposals" | "workflow";
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

type ProjectForm = {
  title: string;
  genre: string;
  language: string;
  target_length: string;
  narrative_pov: string;
};

type ChapterForm = {
  title: string;
  chapter_index: string;
  summary: string;
};

type SceneForm = {
  chapter_id: string;
  title: string;
  scene_index: string;
  pov_character_id: string;
  location_id: string;
  timeline_position: string;
  goal: string;
  conflict: string;
  must_include: string;
  must_not_violate: string;
};

type CharacterForm = {
  name: string;
  role: string;
};

type LocationForm = {
  name: string;
  type: string;
};

type WorldRuleForm = {
  domain: string;
  rule: string;
  severity: string;
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

type DesktopSettings = {
  backendUrl: string;
  workspacePath: string;
  autoStartBackend: boolean;
  pythonExecutable: string;
  backendModule: string;
};

type DesktopBackendStatus = {
  backendUrl: string;
  reachable: boolean;
  workspaceCompatible: boolean;
  managed: boolean;
  pid?: number | null;
  workspacePath: string;
  healthWorkspacePath?: string | null;
  health?: Record<string, unknown> | null;
  error?: string | null;
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

const defaultProjectForm: ProjectForm = {
  title: "",
  genre: "fantasy",
  language: "zh-CN",
  target_length: "",
  narrative_pov: "第三人称有限视角"
};

const defaultChapterForm: ChapterForm = {
  title: "",
  chapter_index: "1",
  summary: ""
};

const defaultSceneForm: SceneForm = {
  chapter_id: "",
  title: "",
  scene_index: "1",
  pov_character_id: "",
  location_id: "",
  timeline_position: "",
  goal: "",
  conflict: "",
  must_include: "",
  must_not_violate: ""
};

const defaultCharacterForm: CharacterForm = {
  name: "",
  role: ""
};

const defaultLocationForm: LocationForm = {
  name: "",
  type: ""
};

const defaultWorldRuleForm: WorldRuleForm = {
  domain: "",
  rule: "",
  severity: "medium"
};

export default function App() {
  const [apiBase, setApiBase] = useState("http://127.0.0.1:8000");
  const [projects, setProjects] = useState<ProjectOutline[]>([]);
  const [workspaceLoaded, setWorkspaceLoaded] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [sceneId, setSceneId] = useState("");
  const [activeTab, setActiveTab] = useState<InspectorTab>("context");
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("write");
  const [contextPack, setContextPack] = useState<ContextPack | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [draftText, setDraftText] = useState("");
  const [draftSummary, setDraftSummary] = useState("");
  const [proposals, setProposals] = useState<ProposalArtifact[]>([]);
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null);
  const [proposalTitle, setProposalTitle] = useState("");
  const [proposalText, setProposalText] = useState("");
  const [proposalArtifactType, setProposalArtifactType] =
    useState<ProposalArtifactType>("scene_draft");
  const [proposalStatusFilter, setProposalStatusFilter] = useState<ProposalStatus | "all">("all");
  const [proposalSourceDraftId, setProposalSourceDraftId] = useState("");
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [runEvents, setRunEvents] = useState<WorkflowStep[]>([]);
  const [continuityReport, setContinuityReport] = useState<ContinuityReport | null>(null);
  const [facts, setFacts] = useState<CandidateFact[]>([]);
  const [graphPreview, setGraphPreview] = useState<ProjectGraphPreview | null>(null);
  const [agentSettings, setAgentSettings] = useState<AgentSettings | null>(null);
  const [agentForm, setAgentForm] = useState<AgentSettingsUpdate>(defaultAgentForm);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [projectForm, setProjectForm] = useState<ProjectForm>(defaultProjectForm);
  const [chapterForm, setChapterForm] = useState<ChapterForm>(defaultChapterForm);
  const [sceneForm, setSceneForm] = useState<SceneForm>(defaultSceneForm);
  const [characterForm, setCharacterForm] = useState<CharacterForm>(defaultCharacterForm);
  const [locationForm, setLocationForm] = useState<LocationForm>(defaultLocationForm);
  const [worldRuleForm, setWorldRuleForm] = useState<WorldRuleForm>(defaultWorldRuleForm);
  const [desktopUpdate, setDesktopUpdate] = useState<TauriUpdate | null>(null);
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus>({
    state: "idle",
    message: "尚未检查更新。"
  });
  const [desktopSettings, setDesktopSettings] = useState<DesktopSettings | null>(null);
  const [desktopBackend, setDesktopBackend] = useState<DesktopBackendStatus | null>(null);
  const [desktopBackendChecked, setDesktopBackendChecked] = useState(() => !isDesktopRuntime());
  const [libraryDocuments, setLibraryDocuments] = useState<LibraryDocument[]>([]);
  const [selectedLibraryDocumentId, setSelectedLibraryDocumentId] = useState<string | null>(null);
  const [expandedLibraryPaths, setExpandedLibraryPaths] = useState<Set<string>>(
    () => new Set(["library"])
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === projectId) ?? null,
    [projectId, projects]
  );
  const selectedScene = useMemo(
    () => findScene(projects, projectId, sceneId),
    [projectId, projects, sceneId]
  );
  const hasWorkspace = projects.length > 0;
  const hasScene = Boolean(projectId && sceneId);
  const endpoint = useMemo(
    () => (projectId && sceneId ? `/projects/${projectId}/scenes/${sceneId}` : ""),
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
  const selectedProposal = useMemo(
    () => proposals.find((proposal) => proposal.id === selectedProposalId) ?? null,
    [proposals, selectedProposalId]
  );
  const visibleProposals = useMemo(
    () =>
      proposalStatusFilter === "all"
        ? proposals
        : proposals.filter((proposal) => proposal.status === proposalStatusFilter),
    [proposalStatusFilter, proposals]
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

  const refreshDesktopBackend = useCallback(async (mode: "status" | "start" = "status") => {
    if (!isDesktopRuntime()) {
      setDesktopBackendChecked(true);
      return null;
    }

    const settings = await invoke<DesktopSettings>("load_desktop_settings");
    setDesktopSettings(settings);
    setApiBase(settings.backendUrl);

    const status = await invoke<DesktopBackendStatus>(
      mode === "start" ? "start_backend" : "backend_status"
    );
    setDesktopBackend(status);
    setDesktopBackendChecked(true);
    if (status.error && (!status.reachable || !status.workspaceCompatible)) {
      setError(status.error);
    }
    return status;
  }, []);

  const stopDesktopBackend = useCallback(async () => {
    if (!isDesktopRuntime()) return;
    const status = await invoke<DesktopBackendStatus>("stop_backend");
    setDesktopBackend(status);
    setDesktopBackendChecked(true);
    setNotice(status.reachable ? "已请求停止受管后端；仍检测到外部后端在运行。" : "受管后端已停止。");
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

  const refreshWorkspace = useCallback(
    async (preferredProjectId?: string, preferredSceneId?: string) => {
      const payload = await apiGet<{ projects: ProjectOutline[] }>(apiBase, "/projects");
      const nextProjects = payload.projects;
      setProjects(nextProjects);
      setWorkspaceLoaded(true);

      if (!nextProjects.length) {
        setProjectId("");
        setSceneId("");
        setContextPack(null);
        setDraft(null);
        setDraftText("");
        setDraftSummary("");
        setProposals([]);
        setSelectedProposalId(null);
        setProposalTitle("");
        setProposalText("");
        setRun(null);
        setRunEvents([]);
        setContinuityReport(null);
        setGraphPreview(null);
        return { projectId: "", sceneId: "" };
      }

      const nextProject =
        nextProjects.find((project) => project.id === preferredProjectId) ?? nextProjects[0];
      const availableScenes = flattenScenes(nextProject);
      const nextScene =
        availableScenes.find((scene) => scene.id === preferredSceneId) ?? availableScenes[0] ?? null;
      setProjectId(nextProject.id);
      setSceneId(nextScene?.id ?? "");
      return { projectId: nextProject.id, sceneId: nextScene?.id ?? "" };
    },
    [apiBase]
  );

  const refreshGraphPreview = useCallback(
    async (targetProjectId = projectId) => {
      if (!targetProjectId) {
        setGraphPreview(null);
        return;
      }
      const preview = await apiGet<ProjectGraphPreview>(
        apiBase,
        `/projects/${targetProjectId}/graph/preview`
      );
      setGraphPreview(preview);
    },
    [apiBase, projectId]
  );

  const refreshLatestDraft = useCallback(
    async (targetProjectId = projectId, targetSceneId = sceneId) => {
      if (!targetProjectId || !targetSceneId) {
        setDraft(null);
        setDraftText("");
        setDraftSummary("");
        return;
      }
      const payload = await apiGet<{ draft: Draft | null }>(
        apiBase,
        `/projects/${targetProjectId}/scenes/${targetSceneId}/draft`
      );
      setDraft(payload.draft);
      setDraftText(payload.draft?.text ?? "");
      setDraftSummary(payload.draft?.summary ?? "");
    },
    [apiBase, projectId, sceneId]
  );

  const refreshProposals = useCallback(
    async (targetProjectId = projectId) => {
      if (!targetProjectId) {
        setProposals([]);
        setSelectedProposalId(null);
        return [];
      }
      const payload = await apiGet<{ proposals: ProposalArtifact[] }>(
        apiBase,
        `/projects/${targetProjectId}/proposals`
      );
      setProposals(payload.proposals);
      if (!payload.proposals.length) {
        setSelectedProposalId(null);
        setProposalTitle("");
        setProposalText("");
      }
      return payload.proposals;
    },
    [apiBase, projectId]
  );

  const refreshFacts = useCallback(async () => {
    if (!projectId) {
      setFacts([]);
      return [];
    }
    const payload = await apiGet<{ facts: CandidateFact[] }>(
      apiBase,
      `/projects/${projectId}/facts/pending`
    );
    setFacts(payload.facts);
    return payload.facts;
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
        /StoryGraph[ .]Agent_.*_x64-setup\.exe$/i.test(asset.name)
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

  const createProject = useCallback(async () => {
    if (!projectForm.title.trim()) {
      throw new Error("请先填写小说项目名称。");
    }
    const result = await apiPost<{ project_id: string }>(apiBase, "/projects", {
      title: projectForm.title.trim(),
      genre: projectForm.genre.trim() || "fiction",
      language: projectForm.language.trim() || "zh-CN",
      target_length: projectForm.target_length.trim() || null,
      narrative_pov: projectForm.narrative_pov.trim() || null
    });
    setProjectForm(defaultProjectForm);
    await refreshWorkspace(result.project_id);
    await refreshGraphPreview(result.project_id);
    setWorkspaceTab("sources");
    setNotice("项目已创建。可以先导入已有小说，并生成章节/场景结构草稿。");
  }, [apiBase, projectForm, refreshGraphPreview, refreshWorkspace]);

  const updateProject = useCallback(async () => {
    if (!projectId) throw new Error("请先选择项目。");
    if (!projectForm.title.trim()) {
      throw new Error("项目名称不能为空。");
    }
    await apiPatch<GraphNodePayload>(apiBase, `/projects/${projectId}`, {
      title: projectForm.title.trim(),
      genre: projectForm.genre.trim() || null,
      language: projectForm.language.trim() || null,
      target_length: projectForm.target_length.trim() || null,
      narrative_pov: projectForm.narrative_pov.trim() || null,
      reviewer: "author",
      rationale: "作者从工作台编辑项目信息。",
      source_ref: "author_seed:workbench_project"
    });
    await refreshWorkspace(projectId, sceneId);
    await refreshGraphPreview(projectId);
    setNotice("项目信息已更新。");
  }, [apiBase, projectForm, projectId, refreshGraphPreview, refreshWorkspace, sceneId]);

  const createChapter = useCallback(async () => {
    if (!projectId) throw new Error("请先选择或创建项目。");
    if (!chapterForm.title.trim()) throw new Error("请填写章节标题。");
    await apiPost<GraphNodePayload>(apiBase, `/projects/${projectId}/chapters`, {
      title: chapterForm.title.trim(),
      chapter_index: toPositiveInteger(chapterForm.chapter_index, 1),
      summary: chapterForm.summary.trim() || null,
      reviewer: "author",
      rationale: "作者从工作台创建章节。",
      source_ref: "author_seed:workbench_outline"
    });
    setChapterForm((current) => ({
      ...defaultChapterForm,
      chapter_index: String(toPositiveInteger(current.chapter_index, 1) + 1)
    }));
    await refreshWorkspace(projectId, sceneId);
    await refreshGraphPreview(projectId);
    setNotice("章节已写入 canon seed。");
  }, [apiBase, chapterForm, projectId, refreshGraphPreview, refreshWorkspace, sceneId]);

  const createScene = useCallback(async () => {
    if (!projectId) throw new Error("请先选择或创建项目。");
    const targetChapterId = sceneForm.chapter_id || selectedProject?.chapters[0]?.id || "";
    if (!targetChapterId) throw new Error("请先选择章节。");
    if (!sceneForm.title.trim()) throw new Error("请填写场景标题。");
    const result = await apiPost<GraphNodePayload>(
      apiBase,
      `/projects/${projectId}/chapters/${targetChapterId}/scenes`,
      {
        title: sceneForm.title.trim(),
        scene_index: toPositiveInteger(sceneForm.scene_index, 1),
        pov_character_id: sceneForm.pov_character_id.trim() || null,
        location_id: sceneForm.location_id.trim() || null,
        timeline_position: sceneForm.timeline_position.trim() || null,
        goal: sceneForm.goal.trim() || null,
        conflict: sceneForm.conflict.trim() || null,
        required_characters: splitLines(sceneForm.pov_character_id),
        must_include: splitLines(sceneForm.must_include),
        must_not_violate: splitLines(sceneForm.must_not_violate),
        status: "planned",
        reviewer: "author",
        rationale: "作者从工作台创建场景。",
        source_ref: "author_seed:workbench_outline"
      }
    );
    setSceneForm((current) => ({
      ...defaultSceneForm,
      chapter_id: current.chapter_id,
      scene_index: String(toPositiveInteger(current.scene_index, 1) + 1)
    }));
    await refreshWorkspace(projectId, result.id);
    await refreshGraphPreview(projectId);
    setNotice("场景已创建，可保存草稿或运行 Agent 工作流。");
  }, [apiBase, projectId, refreshGraphPreview, refreshWorkspace, sceneForm, selectedProject]);

  const createCharacter = useCallback(async () => {
    if (!projectId) throw new Error("请先选择或创建项目。");
    if (!characterForm.name.trim()) throw new Error("请填写人物名称。");
    await apiPost<GraphNodePayload>(apiBase, `/projects/${projectId}/characters`, {
      name: characterForm.name.trim(),
      properties: { role: characterForm.role.trim() || undefined },
      reviewer: "author",
      rationale: "作者从工作台创建人物。",
      source_ref: "author_seed:workbench_story_bible"
    });
    setCharacterForm(defaultCharacterForm);
    await refreshGraphPreview(projectId);
    setNotice("人物已写入 canon seed。可把生成的 character_id 填到场景视角中。");
  }, [apiBase, characterForm, projectId, refreshGraphPreview]);

  const createLocation = useCallback(async () => {
    if (!projectId) throw new Error("请先选择或创建项目。");
    if (!locationForm.name.trim()) throw new Error("请填写地点名称。");
    await apiPost<GraphNodePayload>(apiBase, `/projects/${projectId}/locations`, {
      name: locationForm.name.trim(),
      properties: { type: locationForm.type.trim() || undefined },
      reviewer: "author",
      rationale: "作者从工作台创建地点。",
      source_ref: "author_seed:workbench_story_bible"
    });
    setLocationForm(defaultLocationForm);
    await refreshGraphPreview(projectId);
    setNotice("地点已写入 canon seed。");
  }, [apiBase, locationForm, projectId, refreshGraphPreview]);

  const createWorldRule = useCallback(async () => {
    if (!projectId) throw new Error("请先选择或创建项目。");
    if (!worldRuleForm.domain.trim() || !worldRuleForm.rule.trim()) {
      throw new Error("请填写规则领域和规则内容。");
    }
    await apiPost<GraphNodePayload>(apiBase, `/projects/${projectId}/world-rules`, {
      domain: worldRuleForm.domain.trim(),
      rule: worldRuleForm.rule.trim(),
      severity: worldRuleForm.severity,
      reviewer: "author",
      rationale: "作者从工作台创建世界规则。",
      source_ref: "author_seed:workbench_story_bible"
    });
    setWorldRuleForm(defaultWorldRuleForm);
    await refreshGraphPreview(projectId);
    setNotice("世界规则已写入 canon seed。");
  }, [apiBase, projectId, refreshGraphPreview, worldRuleForm]);

  const saveDocumentAsDraft = useCallback(
    async (document: LibraryDocument) => {
      if (!endpoint) throw new Error("请先创建并选择一个场景。");
      if (document.status !== "ready") throw new Error("这个文档还不能保存为草稿。");
      const saved = await apiPost<Draft>(apiBase, `${endpoint}/draft`, {
        text: document.content,
        summary: `从本地导入文档“${document.name}”设为当前场景草稿。`
      });
      setDraft(saved);
      setDraftText(saved.text);
      setDraftSummary(saved.summary ?? "");
      setWorkspaceTab("write");
      setNotice(`已把“${document.name}”保存为草稿 v${saved.version}；canon 未改变。`);
      return saved;
    },
    [apiBase, endpoint]
  );

  const saveDocumentAsStyleSample = useCallback(
    async (document: LibraryDocument) => {
      if (!projectId) throw new Error("请先创建并选择项目。");
      if (document.status !== "ready") throw new Error("这个文档还不能保存为风格样本。");
      await apiPost(apiBase, `/projects/${projectId}/style-samples`, {
        text: document.content,
        source_ref: `import:${document.path}::${document.id}`,
        pov: contextPack?.style_constraints.pov ?? null,
        tone: contextPack?.style_constraints.tone ?? null,
        dialogue_style: contextPack?.style_constraints.dialogue_style ?? null,
        tags: ["import"],
        summary: `本地导入风格样本：${document.name}`
      });
      setNotice(`“${document.name}”已保存为风格样本；它只会作为 P6 软参考。`);
    },
    [apiBase, contextPack, projectId]
  );

  const analyzeDocumentStructure = useCallback(
    async (document: LibraryDocument) => {
      if (!projectId) throw new Error("请先创建并选择项目。");
      if (document.status !== "ready") throw new Error("这个文档还不能生成结构草稿。");
      const result = await apiPost<ProjectStructureDraftResult>(
        apiBase,
        `/projects/${projectId}/imports/structure-draft`,
        {
          title: document.name,
          text: document.content,
          source_ref: `import:${document.path}::${document.id}`,
          max_chapters: 24,
          max_scenes_per_chapter: 12
        }
      );
      await refreshProposals(projectId);
      setSelectedProposalId(result.proposal.id);
      setWorkspaceTab("proposals");
      const sceneCount = result.outline.chapters.reduce(
        (total, chapter) => total + chapter.scenes.length,
        0
      );
      const suffix = result.truncated ? " 源文档较长，本次只读取前部片段。" : "";
      setNotice(
        `已生成项目结构草稿：${result.outline.chapters.length} 章、${sceneCount} 个场景；请在协作草稿箱确认后再应用。${suffix}`
      );
    },
    [apiBase, projectId, refreshProposals]
  );

  const saveDocumentAsProposal = useCallback(
    async (document: LibraryDocument) => {
      if (!projectId || !sceneId) throw new Error("请先创建并选择一个场景。");
      if (document.status !== "ready") throw new Error("这个文档还不能保存为协作草稿。");
      const proposal = await apiPost<ProposalArtifact>(
        apiBase,
        `/projects/${projectId}/proposals`,
        {
          artifact_type: "scene_draft",
          title: `导入提案：${document.name}`,
          body: document.content,
          target_refs: [{ kind: "scene", ref: sceneId }],
          source_refs: [{ kind: "imported_document", ref: `import:${document.path}::${document.id}` }],
          created_by: "author",
          created_via: "import",
          provenance_note: `本地导入文档：${document.name}`
        }
      );
      await refreshProposals(projectId);
      setSelectedProposalId(proposal.id);
      setWorkspaceTab("proposals");
      setNotice(`“${document.name}”已保存到协作草稿箱；当前场景草稿和 canon 未改变。`);
    },
    [apiBase, projectId, refreshProposals, sceneId]
  );

  const extractDocumentFacts = useCallback(
    async (document: LibraryDocument) => {
      if (!endpoint || !projectId) throw new Error("请先创建并选择一个项目和场景。");
      if (document.status !== "ready") throw new Error("这个文档还不能抽取设定。");
      const result = await apiPost<DocumentFactExtractionResult>(
        apiBase,
        `${endpoint}/extract-document-facts`,
        {
          title: document.name,
          text: document.content,
          source_ref: `import:${document.path}::${document.id}`,
          max_facts: 16
        }
      );
      setDraft(result.source_draft);
      setDraftText(result.source_draft.text);
      setDraftSummary(result.source_draft.summary ?? "");
      await refreshProposals(projectId);
      setSelectedProposalId(result.proposal.id);
      setProposalSourceDraftId(result.source_draft.id);
      setWorkspaceTab("proposals");
      setActiveTab("facts");
      const suffix = result.truncated ? " 源文档较长，本次只读取前部片段。" : "";
      setNotice(
        result.candidate_previews.length
          ? `已生成 fact_draft 设定草稿，包含 ${result.candidate_previews.length} 条候选预览；canon 未改变。${suffix}`
          : `已生成 fact_draft 设定草稿，但未发现可抽取事实；canon 未改变。${suffix}`
      );
    },
    [apiBase, endpoint, projectId, refreshProposals]
  );

  const saveDocumentAsDraftAndExtract = useCallback(
    async (document: LibraryDocument) => {
      await saveDocumentAsDraft(document);
      const payload = await apiPost<{ candidates: CandidateFact[] }>(
        apiBase,
        `${endpoint}/extract-state`
      );
      await refreshFacts();
      setActiveTab("facts");
      setNotice(
        payload.candidates.length
          ? `已生成 ${payload.candidates.length} 条待审候选事实；canon 尚未改变。`
          : "草稿已保存，未抽取到候选事实；canon 未改变。"
      );
    },
    [apiBase, endpoint, refreshFacts, saveDocumentAsDraft]
  );

  const archiveDemo = useCallback(async () => {
    const result = await apiPost<DemoArchiveResult>(apiBase, "/demo/archive");
    await refreshWorkspace();
    setContextPack(null);
    setDraft(null);
    setDraftText("");
    setDraftSummary("");
    setRun(null);
    setRunEvents([]);
    setContinuityReport(null);
    await refreshFacts();
    setNotice(
      `内置演示已从工作区移除：归档 ${result.nodes_archived} 个节点、${result.relationships_archived} 条关系。`
    );
  }, [apiBase, refreshFacts, refreshWorkspace]);

  const buildContext = useCallback(async () => {
    if (!endpoint) throw new Error("请先选择场景。");
    const pack = await apiPost<ContextPack>(apiBase, `${endpoint}/context-pack`);
    setContextPack(pack);
    setWorkspaceTab("write");
    setActiveTab("context");
    setNotice("上下文包已刷新。");
  }, [apiBase, endpoint]);

  const saveDraft = useCallback(async () => {
    if (!endpoint) throw new Error("请先选择场景。");
    const saved = await apiPost<Draft>(apiBase, `${endpoint}/draft`, {
      text: draftText,
      summary: draftSummary
    });
    setDraft(saved);
    setNotice(`草稿 v${saved.version} 已保存。`);
    setWorkspaceTab("write");
  }, [apiBase, draftSummary, draftText, endpoint]);

  const generateDraft = useCallback(async () => {
    if (!endpoint) throw new Error("请先选择场景。");
    const saved = await apiPost<Draft>(apiBase, `${endpoint}/draft`);
    const pack = await apiPost<ContextPack>(apiBase, `${endpoint}/context-pack`);
    setContextPack(pack);
    setDraft(saved);
    setDraftText(saved.text);
    setDraftSummary(saved.summary ?? "");
    setNotice(`草稿 v${saved.version} 已生成。`);
    setWorkspaceTab("write");
  }, [apiBase, endpoint]);

  const runScene = useCallback(async () => {
    if (!endpoint) throw new Error("请先选择场景。");
    const result = await apiPost<SceneRunResult>(
      apiBase,
      `${endpoint}/runs/scene-generation`
    );
    if (!result.draft || !result.continuity_report) {
      throw new Error("工作流未返回 Draft Store 草稿。");
    }
    setContextPack(result.context_pack);
    setDraft(result.draft);
    setDraftText(result.draft.text);
    setDraftSummary(result.draft.summary ?? "");
    setRun(result.workflow_run);
    setContinuityReport(result.continuity_report);
    setWorkspaceTab("workflow");
    setActiveTab(result.continuity_report.issues.length > 0 ? "continuity" : "context");
    const events = await apiGet<{ events: WorkflowStep[] }>(
      apiBase,
      `/runs/${result.workflow_run.id}/events`
    );
    setRunEvents(events.events);
    await refreshFacts();
    setNotice(`工作流状态：${formatStatus(result.workflow_run.status)}。`);
  }, [apiBase, endpoint, refreshFacts]);

  const startNewProposal = useCallback(() => {
    setSelectedProposalId(null);
    setProposalArtifactType("scene_draft");
    setProposalTitle(selectedScene ? `${localizeText(selectedScene.title)} 协作草稿` : "");
    setProposalText("");
    setProposalSourceDraftId(draft?.id ?? "");
  }, [draft, selectedScene]);

  const saveProposal = useCallback(async () => {
    if (!projectId) throw new Error("请先选择或创建项目。");
    const title = proposalTitle.trim() || "未命名协作草稿";
    const body = proposalText;
    if (selectedProposal) {
      const saved = await apiPatch<ProposalArtifact>(
        apiBase,
        `/projects/${projectId}/proposals/${selectedProposal.id}`,
        {
          title,
          body,
          expected_version: selectedProposal.version
        }
      );
      await refreshProposals(projectId);
      setSelectedProposalId(saved.id);
      setNotice(`协作草稿已保存为 v${saved.version}；Draft/Candidate/Canon 未改变。`);
      return;
    }
    const targetRefs =
      proposalArtifactType === "fact_draft" && proposalSourceDraftId.trim()
        ? [{ kind: "draft", ref: proposalSourceDraftId.trim() }]
        : sceneId
          ? [{ kind: "scene", ref: sceneId }]
          : [];
    const saved = await apiPost<ProposalArtifact>(
      apiBase,
      `/projects/${projectId}/proposals`,
      {
        artifact_type: proposalArtifactType,
        title,
        body,
        target_refs: targetRefs,
        source_refs: [{ kind: "author_instruction", ref: "workbench:proposal_editor" }],
        created_by: "author",
        created_via: "manual",
        provenance_note: "作者从协作草稿箱创建。"
      }
    );
    await refreshProposals(projectId);
    setSelectedProposalId(saved.id);
    setNotice(`协作草稿已创建为 v${saved.version}；尚未进入 Draft/Candidate/Canon。`);
  }, [
    apiBase,
    projectId,
    proposalArtifactType,
    proposalSourceDraftId,
    proposalText,
    proposalTitle,
    refreshProposals,
    sceneId,
    selectedProposal
  ]);

  const requestAgentProposal = useCallback(async () => {
    if (!endpoint) throw new Error("请先选择场景。");
    if (
      selectedProposal &&
      selectedProposal.status !== "accepted" &&
      selectedProposal.status !== "rejected"
    ) {
      const revised = await apiPost<ProposalArtifact>(
        apiBase,
        `/projects/${projectId}/proposals/${selectedProposal.id}/revise`,
        {
          actor: "agent",
          created_via: "workflow",
          expected_version: selectedProposal.version,
          note: "Agent 从当前 Context Pack 生成新的协作草稿版本。"
        }
      );
      await refreshProposals(projectId);
      setSelectedProposalId(revised.id);
      setWorkspaceTab("proposals");
      setNotice(`Agent 已修订协作草稿为 v${revised.version}；当前场景草稿未被覆盖。`);
      return;
    }
    const result = await apiPost<SceneRunResult>(
      apiBase,
      `${endpoint}/runs/scene-generation`,
      { output_target: "proposal_workspace" }
    );
    setContextPack(result.context_pack);
    setRun(result.workflow_run);
    setContinuityReport(result.continuity_report);
    const events = await apiGet<{ events: WorkflowStep[] }>(
      apiBase,
      `/runs/${result.workflow_run.id}/events`
    );
    setRunEvents(events.events);
    const refreshed = await refreshProposals(projectId);
    if (result.proposal) {
      setSelectedProposalId(result.proposal.id);
    } else if (refreshed[0]) {
      setSelectedProposalId(refreshed[0].id);
    }
    setWorkspaceTab("proposals");
    setNotice("Agent 已生成 scene_draft 协作草稿；当前场景草稿未被覆盖。");
  }, [apiBase, endpoint, projectId, refreshProposals, selectedProposal]);

  const extractStateToProposal = useCallback(async () => {
    if (!endpoint) throw new Error("请先选择场景。");
    const result = await apiPost<{
      proposal: ProposalArtifact;
      candidate_previews: CandidateFact[];
      candidates: CandidateFact[];
    }>(apiBase, `${endpoint}/extract-state`, { output_target: "proposal_workspace" });
    await refreshProposals(projectId);
    setSelectedProposalId(result.proposal.id);
    setWorkspaceTab("proposals");
    setNotice(
      result.candidate_previews.length
        ? `已生成 fact_draft 协作草稿，包含 ${result.candidate_previews.length} 条候选预览。`
        : "已生成 fact_draft 协作草稿，当前草稿未发现候选事实。"
    );
  }, [apiBase, endpoint, projectId, refreshProposals]);

  const submitProposalReview = useCallback(async () => {
    if (!selectedProposal || !projectId) throw new Error("请先选择协作草稿。");
    const saved = await apiPost<ProposalArtifact>(
      apiBase,
      `/projects/${projectId}/proposals/${selectedProposal.id}/submit-review`,
      { expected_version: selectedProposal.version }
    );
    await refreshProposals(projectId);
    setSelectedProposalId(saved.id);
    setNotice(`协作草稿 ${saved.id} 已标记为待审。`);
  }, [apiBase, projectId, refreshProposals, selectedProposal]);

  const reviewProposal = useCallback(
    async (decision: "accept" | "reject") => {
      if (!selectedProposal || !projectId) throw new Error("请先选择协作草稿。");
      const saved = await apiPost<ProposalArtifact>(
        apiBase,
        `/projects/${projectId}/proposals/${selectedProposal.id}/${decision}`,
        { reviewer: "author", expected_version: selectedProposal.version }
      );
      await refreshProposals(projectId);
      setSelectedProposalId(saved.id);
      setNotice(`协作草稿已${decision === "accept" ? "接受" : "拒绝"}；canon 未改变。`);
    },
    [apiBase, projectId, refreshProposals, selectedProposal]
  );

  const promoteProposalToDraft = useCallback(async () => {
    if (!selectedProposal || !projectId || !sceneId) throw new Error("请先选择场景和协作草稿。");
    const result = await apiPost<ProposalDraftPromotionResult>(
      apiBase,
      `/projects/${projectId}/proposals/${selectedProposal.id}/promote/draft`,
      { scene_id: sceneId, expected_version: selectedProposal.version }
    );
    setDraft(result.draft);
    setDraftText(result.draft.text);
    setDraftSummary(result.draft.summary ?? "");
    await refreshProposals(projectId);
    setSelectedProposalId(result.proposal.id);
    setNotice(`已转为当前场景草稿 v${result.draft.version}；canon 未改变。`);
  }, [apiBase, projectId, refreshProposals, sceneId, selectedProposal]);

  const applyProjectStructureProposal = useCallback(async () => {
    if (!selectedProposal || !projectId) throw new Error("请先选择项目结构草稿。");
    const result = await apiPost<ProjectStructureApplyResult>(
      apiBase,
      `/projects/${projectId}/proposals/${selectedProposal.id}/apply/project-structure`,
      {
        reviewer: "author",
        rationale: "作者确认导入文档生成的项目结构草稿。",
        expected_version: selectedProposal.version
      }
    );
    await refreshWorkspace(projectId, result.scenes[0]?.id ?? sceneId);
    await refreshGraphPreview(projectId);
    await refreshProposals(projectId);
    setSelectedProposalId(result.proposal.id);
    if (result.scenes[0]?.id) {
      setSceneId(result.scenes[0].id);
      setWorkspaceTab("write");
    }
    setNotice(
      `已应用项目结构：创建 ${result.chapters.length} 个章节、${result.scenes.length} 个场景；canon 事实仍未改变。`
    );
  }, [
    apiBase,
    projectId,
    refreshGraphPreview,
    refreshProposals,
    refreshWorkspace,
    sceneId,
    selectedProposal
  ]);

  const promoteProposalToCandidates = useCallback(async () => {
    if (!selectedProposal || !projectId) throw new Error("请先选择协作草稿。");
    const sourceDraftId =
      proposalSourceDraftId.trim() || findProposalRef(selectedProposal, "draft") || draft?.id || "";
    if (!sourceDraftId) throw new Error("请提供真实来源草稿 ID。");
    const result = await apiPost<ProposalCandidatePromotionResult>(
      apiBase,
      `/projects/${projectId}/proposals/${selectedProposal.id}/promote/candidate-facts`,
      {
        source_draft_id: sourceDraftId,
        expected_version: selectedProposal.version
      }
    );
    await refreshProposals(projectId);
    await refreshFacts();
    setSelectedProposalId(result.proposal.id);
    setActiveTab("facts");
    setNotice(
      result.candidates.length
        ? `已提交 ${result.candidates.length} 条候选事实；canon 尚未改变。`
        : "来源草稿中没有可抽取的候选事实。"
    );
  }, [
    apiBase,
    draft,
    projectId,
    proposalSourceDraftId,
    refreshFacts,
    refreshProposals,
    selectedProposal
  ]);

  const reviewFact = useCallback(
    async (factId: string, action: "accept" | "reject" | "defer") => {
      await apiPost<CandidateFact>(
        apiBase,
        `/projects/${projectId}/facts/${factId}/${action}`,
        { reviewer: "author", note: `工作台执行：${reviewActionLabels[action]}` }
      );
      const remaining = await refreshFacts();
      if (run?.status === "awaiting_review" && remaining.length === 0) {
        const resumed = await apiPost<WorkflowRun>(apiBase, `/runs/${run.id}/resume-review`);
        setRun(resumed);
        const events = await apiGet<{ events: WorkflowStep[] }>(
          apiBase,
          `/runs/${resumed.id}/events`
        );
        setRunEvents(events.events);
        setNotice(`候选事实已${reviewActionLabels[action]}，工作流审阅暂停已恢复。`);
        return;
      }
      await refreshGraphPreview(projectId);
      setNotice(`候选事实已${reviewActionLabels[action]}。`);
    },
    [apiBase, projectId, refreshFacts, refreshGraphPreview, run]
  );

  useEffect(() => {
    if (!isDesktopRuntime()) return;
    refreshDesktopBackend("start").catch((exc) => {
      setDesktopBackendChecked(true);
      setError(toErrorMessage(exc));
    });
  }, [refreshDesktopBackend]);

  useEffect(() => {
    if (isDesktopRuntime() && !desktopBackendChecked) return;
    if (isDesktopRuntime() && !desktopBackend) {
      setWorkspaceLoaded(true);
      return;
    }
    if (isDesktopRuntime() && desktopBackend && !desktopBackend.workspaceCompatible) {
      setWorkspaceLoaded(true);
      setError(desktopBackend.error ?? "当前桌面后端工作区与设置不一致，请先处理后端连接。");
      return;
    }
    refreshWorkspace().catch((exc) => {
      setWorkspaceLoaded(true);
      setError(toErrorMessage(exc));
    });
  }, [
    apiBase,
    desktopBackend?.workspaceCompatible,
    desktopBackendChecked,
    refreshWorkspace
  ]);

  useEffect(() => {
    refreshFacts().catch(() => undefined);
  }, [refreshFacts]);

  useEffect(() => {
    if (!projectId) return;
    refreshGraphPreview(projectId).catch(() => undefined);
  }, [projectId, refreshGraphPreview]);

  useEffect(() => {
    refreshLatestDraft().catch(() => undefined);
  }, [refreshLatestDraft]);

  useEffect(() => {
    refreshProposals().catch(() => undefined);
  }, [refreshProposals]);

  useEffect(() => {
    if (!proposals.length) {
      setSelectedProposalId(null);
      return;
    }
    if (!selectedProposalId || !proposals.some((proposal) => proposal.id === selectedProposalId)) {
      setSelectedProposalId(proposals[0].id);
    }
  }, [proposals, selectedProposalId]);

  useEffect(() => {
    if (!selectedProposal) return;
    setProposalTitle(selectedProposal.title);
    setProposalText(selectedProposal.body);
    setProposalArtifactType(selectedProposal.artifact_type);
    setProposalSourceDraftId(findProposalRef(selectedProposal, "draft") ?? draft?.id ?? "");
  }, [draft, selectedProposal]);

  useEffect(() => {
    const firstChapterId = selectedProject?.chapters[0]?.id ?? "";
    if (!firstChapterId) return;
    setSceneForm((current) =>
      current.chapter_id ? current : { ...current, chapter_id: firstChapterId }
    );
  }, [selectedProject]);

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
  const writerNeedsKey =
    agentSettings?.scene_writer === "llm" &&
    (!agentSettings.api_key_configured || !agentSettings.llm_base_url || !agentSettings.llm_model);
  const llmConfigured = Boolean(
    agentSettings?.api_key_configured && agentSettings.llm_base_url && agentSettings.llm_model
  );
  const canRunScene = hasScene && canGenerate && !writerNeedsKey;
  const canExtractDocumentFacts = hasScene && canGenerate && llmConfigured;
  const runEditCommand = useCallback((command: "undo" | "redo") => {
    const active = document.activeElement;
    if (
      active instanceof HTMLInputElement ||
      active instanceof HTMLTextAreaElement
    ) {
      document.execCommand(command);
    }
  }, []);
  const currentChapterId = selectedProject?.chapters[0]?.id ?? "";
  const backendStatusLabel = desktopBackend ? formatDesktopBackendLabel(desktopBackend) : "FastAPI";
  const backendStatusTone = desktopBackend ? desktopBackendTone(desktopBackend) : "good";

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
        <div className="command-bar" aria-label="全局命令">
          <button
            type="button"
            onClick={() => runAction("save", saveDraft)}
            disabled={!canGenerate || !hasScene || busy !== null}
            title="保存当前场景草稿"
          >
            <Save size={15} /> 保存
          </button>
          <button type="button" onClick={() => runEditCommand("undo")} title="撤销当前输入框编辑">
            <Undo2 size={15} /> 撤销
          </button>
          <button type="button" onClick={() => runEditCommand("redo")} title="重做当前输入框编辑">
            <Redo2 size={15} /> 重做
          </button>
          <button
            type="button"
            onClick={() =>
              runAction("workspace", async () => {
                await refreshWorkspace(projectId, sceneId);
              })
            }
            disabled={busy !== null}
            title="刷新后端项目树"
          >
            <RefreshCw size={15} /> 刷新
          </button>
          <button type="button" onClick={() => setWorkspaceTab("sources")} title="打开本地资料与 LLM 抽设定">
            <Library size={15} /> 资料
          </button>
          <button type="button" onClick={() => setWorkspaceTab("proposals")} title="打开协作草稿箱">
            <SplitSquareVertical size={15} /> 草稿箱
          </button>
          <button
            type="button"
            onClick={() => runAction("run", runScene)}
            disabled={!canRunScene || busy !== null}
            title="根据当前 canon/context 运行场景写作工作流"
          >
            <Play size={15} /> 写作
          </button>
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
          <StatusDot label={backendStatusLabel} tone={backendStatusTone} />
          <StatusDot label={permissionLabels[agentSettings?.permission_level ?? "full"]} tone={permissionTone(agentSettings?.permission_level)} />
          <StatusDot label={`v${APP_VERSION}`} tone="neutral" />
          <button className="icon-button" title="设置" type="button" onClick={() => setActiveTab("settings")}>
            <Settings size={17} />
          </button>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <ProjectSidebar
            busy={busy}
            canReview={canReview}
            chapterForm={chapterForm}
            characterForm={characterForm}
            currentChapterId={currentChapterId}
            hasWorkspace={hasWorkspace}
            locationForm={locationForm}
            onChapterFormChange={setChapterForm}
            onCharacterFormChange={setCharacterForm}
            onCreateChapter={() => runAction("create-chapter", createChapter)}
            onCreateCharacter={() => runAction("create-character", createCharacter)}
            onCreateLocation={() => runAction("create-location", createLocation)}
            onCreateProject={() => runAction("create-project", createProject)}
            onCreateScene={() => runAction("create-scene", createScene)}
            onCreateWorldRule={() => runAction("create-world-rule", createWorldRule)}
            onArchiveDemo={() => runAction("archive-demo", archiveDemo)}
            onLocationFormChange={setLocationForm}
            onProjectFormChange={setProjectForm}
            onUpdateProject={() => runAction("update-project", updateProject)}
            onRefresh={() =>
              runAction("workspace", async () => {
                await refreshWorkspace(projectId, sceneId);
              })
            }
            onSceneFormChange={setSceneForm}
            onSelectProject={(nextProjectId) => {
              const nextProject = projects.find((project) => project.id === nextProjectId);
              const firstScene = nextProject ? flattenScenes(nextProject)[0] : null;
              setProjectId(nextProjectId);
              setSceneId(firstScene?.id ?? "");
              setContextPack(null);
              setRun(null);
              setRunEvents([]);
              setContinuityReport(null);
            }}
            onSelectScene={(nextSceneId) => {
              setSceneId(nextSceneId);
              setContextPack(null);
              setRun(null);
              setRunEvents([]);
              setContinuityReport(null);
            }}
            onWorldRuleFormChange={setWorldRuleForm}
            projectForm={projectForm}
            projectId={projectId}
            projects={projects}
            sceneForm={sceneForm}
            sceneId={sceneId}
            selectedProject={selectedProject}
            workspaceLoaded={workspaceLoaded}
            worldRuleForm={worldRuleForm}
          />
        </aside>

        <main className="editor">
          <section className="scene-toolbar">
            <div>
              <h1>
                {localizeText(selectedScene?.title) ||
                  (hasWorkspace ? "导入小说生成项目结构" : "空工作区")}
              </h1>
              <p>
                {hasScene
                  ? `${sceneId} / 视角 ${localizeText(contextPack?.pov_character_id || selectedScene?.pov_character_id) || "未设置"}`
                  : hasWorkspace
                    ? "先在“资料”中导入已有小说，由 Agent 生成章节/场景结构草稿；作者确认后再写入正式项目树。"
                    : "先创建项目，再导入已有小说生成章节/场景结构草稿。"}
              </p>
            </div>
            <div className="toolbar-actions">
              <button
                onClick={() => runAction("context", buildContext)}
                type="button"
                disabled={!hasScene}
              >
                <RefreshCw size={16} /> 上下文
              </button>
              <button
                onClick={() => runAction("save", saveDraft)}
                type="button"
                disabled={!canGenerate || !hasScene}
              >
                <Save size={16} /> 保存
              </button>
              <button
                onClick={() => runAction("draft", generateDraft)}
                type="button"
                disabled={missingCritical || !canRunScene}
                title="仅执行 build_context + write_draft，并保存到 Draft Store。"
              >
                <FileText size={16} /> 仅生成草稿
              </button>
              <button
                className="primary"
                onClick={() => runAction("run", runScene)}
                type="button"
                disabled={!canRunScene}
                title="根据当前场景 canon/context 写场景草稿，再做质检和候选事实抽取。不会读取本地资料区。"
              >
                <Play size={16} /> 运行场景写作工作流
              </button>
            </div>
          </section>

          <section className="state-strip" aria-label="当前工作流状态">
            <StatusDot
              label={`项目：${localizeText(selectedProject?.title) || "未创建"}`}
              tone={hasWorkspace ? "good" : "warning"}
            />
            <StatusDot
              label={`写作器：${formatWriter(agentSettings)}`}
              tone={writerNeedsKey ? "danger" : canGenerate ? "good" : "neutral"}
            />
            <StatusDot
              label={writerNeedsKey ? "LLM 设置未完整" : "Draft/Candidate/Canon 分离"}
              tone={writerNeedsKey ? "danger" : "neutral"}
            />
          </section>

          <section className="workspace-tabs" aria-label="主工作区">
            <TabButton active={workspaceTab === "write"} onClick={() => setWorkspaceTab("write")} icon={<FileText size={15} />} label="写作" />
            <TabButton active={workspaceTab === "sources"} onClick={() => setWorkspaceTab("sources")} icon={<Library size={15} />} label="资料" />
            <TabButton active={workspaceTab === "proposals"} onClick={() => setWorkspaceTab("proposals")} icon={<SplitSquareVertical size={15} />} label="协作草稿" />
            <TabButton active={workspaceTab === "workflow"} onClick={() => setWorkspaceTab("workflow")} icon={<Activity size={15} />} label="工作流" />
          </section>

          {(error || notice) && (
            <div className={`message ${error ? "error" : "notice"}`}>
              {error ? <AlertTriangle size={16} /> : <Check size={16} />}
              <span>{error ?? notice}</span>
            </div>
          )}

          {!hasWorkspace && (
            <section className="empty-workspace">
              <EmptyState
                icon={<Database />}
                title="当前后端没有真实项目"
                text="请先创建自己的小说项目；创建后可导入已有小说，让 Agent 生成章节和场景结构草稿。"
              />
            </section>
          )}

          {workspaceTab === "write" && (
            <section className="meta-grid" aria-label="场景元数据">
              <Meta label="目标" value={contextPack?.scene_goal || selectedScene?.goal || ""} />
              <Meta label="冲突" value={contextPack?.conflict || selectedScene?.conflict || ""} />
              <Meta
                label="时间线"
                value={contextPack?.timeline_position || selectedScene?.timeline_position || ""}
              />
              <Meta label="地点" value={contextPack?.location_id || selectedScene?.location_id || ""} />
            </section>
          )}

          {workspaceTab === "sources" && (
          <section className="library-panel" aria-label="本地资料库">
            <div className="library-header">
              <div>
                <span><Library size={15} /> 本地资料 / 导入</span>
                <small>{libraryDocuments.length} 个本地文档 / 默认只在浏览器内存 / 非 canon（正典）</small>
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
              <DocumentReader
                busy={busy}
                canAnalyzeProjectStructure={Boolean(projectId) && canGenerate}
                canExtractDocumentFacts={canExtractDocumentFacts}
                canGenerate={canGenerate}
                document={selectedLibraryDocument}
                hasProject={Boolean(projectId)}
                hasScene={hasScene}
                onAnalyzeStructure={(document) =>
                  runAction("document-structure", () => analyzeDocumentStructure(document))
                }
                onExtractDocumentFacts={(document) =>
                  runAction("document-facts", () => extractDocumentFacts(document))
                }
                onExtract={(document) =>
                  runAction("import-extract", () => saveDocumentAsDraftAndExtract(document))
                }
                onSaveDraft={(document) =>
                  runAction("import-draft", async () => {
                    await saveDocumentAsDraft(document);
                  })
                }
                onSaveProposal={(document) =>
                  runAction("import-proposal", () => saveDocumentAsProposal(document))
                }
                onSaveStyle={(document) =>
                  runAction("import-style", () => saveDocumentAsStyleSample(document))
                }
              />
            </div>
          </section>
          )}

          {workspaceTab === "proposals" && (
          <ProposalInbox
            busy={busy}
            canGenerate={canGenerate}
            canReview={canReview}
            currentDraftId={draft?.id ?? ""}
            filter={proposalStatusFilter}
            hasScene={hasScene}
            onAccept={() => runAction("proposal-accept", () => reviewProposal("accept"))}
            onApplyProjectStructure={() =>
              runAction("proposal-structure", applyProjectStructureProposal)
            }
            onCreateNew={startNewProposal}
            onExtractCandidates={() =>
              runAction("proposal-candidates", promoteProposalToCandidates)
            }
            onExtractFactDraft={() =>
              runAction("proposal-fact-draft", extractStateToProposal)
            }
            onFilterChange={setProposalStatusFilter}
            onOpenCanonReview={() => {
              setActiveTab("facts");
              setNotice("已打开候选事实审阅队列。");
            }}
            onPromoteDraft={() => runAction("proposal-draft", promoteProposalToDraft)}
            onReject={() => runAction("proposal-reject", () => reviewProposal("reject"))}
            onRequestAgent={() => runAction("proposal-agent", requestAgentProposal)}
            onSave={() => runAction("proposal-save", saveProposal)}
            onSelect={setSelectedProposalId}
            onSourceDraftChange={setProposalSourceDraftId}
            onSubmitReview={() => runAction("proposal-submit", submitProposalReview)}
            onTextChange={setProposalText}
            onTitleChange={setProposalTitle}
            onTypeChange={setProposalArtifactType}
            proposalSourceDraftId={proposalSourceDraftId}
            proposalText={proposalText}
            proposalTitle={proposalTitle}
            proposalType={proposalArtifactType}
            proposals={visibleProposals}
            selectedProposal={selectedProposal}
          />
          )}

          {workspaceTab === "write" && (
          <details className="draft-surface collapsible-panel" open>
            <summary className="draft-header">
              <span>场景草稿</span>
              <small>{draft ? `v${draft.version} / ${draft.id}` : "本地未保存草稿"}</small>
            </summary>
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
          </details>
          )}

          {workspaceTab === "workflow" && (
          <details className="run-panel collapsible-panel" open>
            <summary className="run-head">
              <div>
                <span>智能体运行</span>
                <small>{run?.id ?? "尚未运行"}</small>
              </div>
              <StatusDot label={formatStatus(run?.status ?? "idle")} tone={statusTone(run?.status)} />
            </summary>
            <div className="step-track">
              {(runEvents.length ? runEvents : fallbackSteps).map((step) => (
                <div key={step.name} className={`step ${step.status}`}>
                  <span>{stepLabels[step.name] ?? step.name}</span>
                  <small>{formatStatus(step.status)}</small>
                </div>
              ))}
            </div>
          </details>
          )}
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
              desktopBackend={desktopBackend}
              desktopSettings={desktopSettings}
              form={agentForm}
              onApiKeyChange={setApiKeyInput}
              onClearApiKeyChange={setClearApiKey}
              onFormChange={setAgentForm}
              onBackendRefresh={() => runAction("desktop-backend", () => refreshDesktopBackend("status").then(() => undefined))}
              onBackendStart={() => runAction("desktop-backend", () => refreshDesktopBackend("start").then(() => undefined))}
              onBackendStop={() => runAction("desktop-backend", stopDesktopBackend)}
              onRefresh={() => runAction("settings", refreshAgentSettings)}
              onSave={() => runAction("settings", saveAgentSettings)}
              onInstallUpdate={() => runAction("update-install", installAvailableUpdate)}
              onUpdateCheck={() => runAction("update-check", () => checkForUpdates(false))}
              settings={agentSettings}
              updateStatus={updateStatus}
            />
          )}
          <GraphPreview preview={graphPreview} selectedSceneId={sceneId} />
        </aside>
      </div>
    </div>
  );
}

function ProposalInbox({
  busy,
  canGenerate,
  canReview,
  currentDraftId,
  filter,
  hasScene,
  onAccept,
  onApplyProjectStructure,
  onCreateNew,
  onExtractCandidates,
  onExtractFactDraft,
  onFilterChange,
  onOpenCanonReview,
  onPromoteDraft,
  onReject,
  onRequestAgent,
  onSave,
  onSelect,
  onSourceDraftChange,
  onSubmitReview,
  onTextChange,
  onTitleChange,
  onTypeChange,
  proposalSourceDraftId,
  proposalText,
  proposalTitle,
  proposalType,
  proposals,
  selectedProposal
}: {
  busy: string | null;
  canGenerate: boolean;
  canReview: boolean;
  currentDraftId: string;
  filter: ProposalStatus | "all";
  hasScene: boolean;
  onAccept: () => void;
  onApplyProjectStructure: () => void;
  onCreateNew: () => void;
  onExtractCandidates: () => void;
  onExtractFactDraft: () => void;
  onFilterChange: (filter: ProposalStatus | "all") => void;
  onOpenCanonReview: () => void;
  onPromoteDraft: () => void;
  onReject: () => void;
  onRequestAgent: () => void;
  onSave: () => void;
  onSelect: (proposalId: string) => void;
  onSourceDraftChange: (draftId: string) => void;
  onSubmitReview: () => void;
  onTextChange: (text: string) => void;
  onTitleChange: (title: string) => void;
  onTypeChange: (artifactType: ProposalArtifactType) => void;
  proposalSourceDraftId: string;
  proposalText: string;
  proposalTitle: string;
  proposalType: ProposalArtifactType;
  proposals: ProposalArtifact[];
  selectedProposal: ProposalArtifact | null;
}) {
  const locked = selectedProposal?.status === "accepted" || selectedProposal?.status === "rejected";
  const canSave = canGenerate && busy === null && (!selectedProposal || !locked);
  const canSubmit = canGenerate && busy === null && Boolean(selectedProposal) && !locked;
  const canDecide = canReview && busy === null && Boolean(selectedProposal) && !locked;
  const canPromoteDraft =
    canReview &&
    busy === null &&
    hasScene &&
    selectedProposal?.status === "accepted" &&
    selectedProposal.artifact_type === "scene_draft";
  const effectiveSourceDraftId = proposalSourceDraftId || currentDraftId;
  const canPromoteCandidates =
    canReview &&
    busy === null &&
    selectedProposal?.status === "accepted" &&
    selectedProposal.artifact_type === "fact_draft" &&
    Boolean(effectiveSourceDraftId.trim());
  const canApplyProjectStructure =
    canReview &&
    busy === null &&
    selectedProposal?.status === "accepted" &&
    selectedProposal.artifact_type === "project_structure_draft";

  return (
    <section className="proposal-panel" aria-label="协作草稿箱">
      <div className="proposal-header">
        <div>
          <span><SplitSquareVertical size={15} /> 协作草稿箱</span>
          <small>{proposals.length} 条 / Proposal Store</small>
        </div>
        <div className="proposal-header-actions">
          <select
            value={filter}
            onChange={(event) => onFilterChange(event.target.value as ProposalStatus | "all")}
            aria-label="协作草稿状态筛选"
          >
            <option value="all">全部</option>
            {proposalStatuses.map((status) => (
              <option key={status} value={status}>{proposalStatusLabels[status]}</option>
            ))}
          </select>
          <button type="button" onClick={onCreateNew} disabled={busy !== null}>
            <FileText size={14} /> 新建
          </button>
        </div>
      </div>
      <div className="proposal-grid">
        <div className="proposal-list">
          {proposals.length ? (
            proposals.map((proposal) => (
              <button
                className={proposal.id === selectedProposal?.id ? "selected" : ""}
                key={proposal.id}
                onClick={() => onSelect(proposal.id)}
                title={proposal.id}
                type="button"
              >
                <strong>{proposal.title}</strong>
                <span>{proposalTypeLabels[proposal.artifact_type]} / {proposalStatusLabels[proposal.status]} / v{proposal.version}</span>
              </button>
            ))
          ) : (
            <EmptyState
              icon={<SplitSquareVertical />}
              title="暂无协作草稿"
              text="可从本地资料、Agent 工作流或手动编辑创建。"
            />
          )}
        </div>
        <div className="proposal-editor">
          <div className="proposal-fields">
            <select
              value={proposalType}
              disabled={Boolean(selectedProposal)}
              onChange={(event) => onTypeChange(event.target.value as ProposalArtifactType)}
              aria-label="协作草稿类型"
            >
              {proposalTypes.map((type) => (
                <option key={type} value={type}>{proposalTypeLabels[type]}</option>
              ))}
            </select>
            <input
              value={proposalTitle}
              onChange={(event) => onTitleChange(event.target.value)}
              placeholder="标题"
              aria-label="协作草稿标题"
              disabled={locked}
            />
          </div>
          <textarea
            className="proposal-textarea"
            value={proposalText}
            onChange={(event) => onTextChange(event.target.value)}
            spellCheck={false}
            aria-label="协作草稿正文"
            disabled={locked}
          />
          <div className="proposal-actions">
            <button type="button" onClick={onSave} disabled={!canSave}>
              <Save size={14} /> 保存草稿
            </button>
            <button type="button" onClick={onRequestAgent} disabled={!canGenerate || busy !== null || !hasScene}>
              <Wand2 size={14} /> 请求 Agent 修改
            </button>
            <button type="button" onClick={onExtractFactDraft} disabled={!canGenerate || busy !== null || !hasScene}>
              <ShieldCheck size={14} /> 生成事实草稿
            </button>
            <button type="button" onClick={onSubmitReview} disabled={!canSubmit}>
              <Clock3 size={14} /> 提交审阅
            </button>
            <button type="button" onClick={onAccept} disabled={!canDecide}>
              <Check size={14} /> 接受
            </button>
            <button type="button" onClick={onReject} disabled={!canDecide}>
              <X size={14} /> 拒绝
            </button>
            <button type="button" onClick={onPromoteDraft} disabled={!canPromoteDraft}>
              <FileText size={14} /> 转为当前场景草稿
            </button>
            <button type="button" onClick={onApplyProjectStructure} disabled={!canApplyProjectStructure}>
              <BookOpen size={14} /> 应用为章节/场景
            </button>
          </div>
        </div>
        <div className="proposal-meta">
          <MetricRow label="状态" value={selectedProposal ? proposalStatusLabels[selectedProposal.status] : "未选择"} />
          <MetricRow label="类型" value={proposalTypeLabels[proposalType]} />
          <MetricRow label="版本" value={selectedProposal ? `v${selectedProposal.version}` : "新建"} />
          <MetricRow label="创建方式" value={selectedProposal?.provenance.created_via ?? "manual"} />
          <label>
            <span>来源草稿</span>
            <input
              value={effectiveSourceDraftId}
              onChange={(event) => onSourceDraftChange(event.target.value)}
              placeholder="Draft ID"
            />
          </label>
          <div className="proposal-side-actions">
            <button type="button" onClick={onExtractCandidates} disabled={!canPromoteCandidates}>
              <ShieldCheck size={14} /> 抽取为 CandidateFact
            </button>
            <button type="button" onClick={onOpenCanonReview} disabled={busy !== null}>
              <ShieldCheck size={14} /> 提交 canon review
            </button>
          </div>
          <ListBlock
            title="来源"
            items={formatProposalRefs(selectedProposal?.source_refs ?? [])}
          />
          <ListBlock
            title="影响范围"
            items={formatProposalRefs(selectedProposal?.target_refs ?? [])}
          />
          <ListBlock
            title="派生"
            items={formatProposalRefs(selectedProposal?.derived_refs ?? [])}
          />
        </div>
      </div>
    </section>
  );
}

function ProjectSidebar({
  busy,
  canReview,
  chapterForm,
  characterForm,
  currentChapterId,
  hasWorkspace,
  locationForm,
  onChapterFormChange,
  onCharacterFormChange,
  onCreateChapter,
  onCreateCharacter,
  onCreateLocation,
  onCreateProject,
  onCreateScene,
  onCreateWorldRule,
  onArchiveDemo,
  onLocationFormChange,
  onProjectFormChange,
  onUpdateProject,
  onRefresh,
  onSceneFormChange,
  onSelectProject,
  onSelectScene,
  onWorldRuleFormChange,
  projectForm,
  projectId,
  projects,
  sceneForm,
  sceneId,
  selectedProject,
  workspaceLoaded,
  worldRuleForm
}: {
  busy: string | null;
  canReview: boolean;
  chapterForm: ChapterForm;
  characterForm: CharacterForm;
  currentChapterId: string;
  hasWorkspace: boolean;
  locationForm: LocationForm;
  onChapterFormChange: React.Dispatch<React.SetStateAction<ChapterForm>>;
  onCharacterFormChange: React.Dispatch<React.SetStateAction<CharacterForm>>;
  onCreateChapter: () => void;
  onCreateCharacter: () => void;
  onCreateLocation: () => void;
  onCreateProject: () => void;
  onCreateScene: () => void;
  onCreateWorldRule: () => void;
  onArchiveDemo: () => void;
  onLocationFormChange: React.Dispatch<React.SetStateAction<LocationForm>>;
  onProjectFormChange: React.Dispatch<React.SetStateAction<ProjectForm>>;
  onUpdateProject: () => void;
  onRefresh: () => void;
  onSceneFormChange: React.Dispatch<React.SetStateAction<SceneForm>>;
  onSelectProject: (projectId: string) => void;
  onSelectScene: (sceneId: string) => void;
  onWorldRuleFormChange: React.Dispatch<React.SetStateAction<WorldRuleForm>>;
  projectForm: ProjectForm;
  projectId: string;
  projects: ProjectOutline[];
  sceneForm: SceneForm;
  sceneId: string;
  selectedProject: ProjectOutline | null;
  workspaceLoaded: boolean;
  worldRuleForm: WorldRuleForm;
}) {
  const chapters = selectedProject?.chapters ?? [];
  const sceneChapterId = sceneForm.chapter_id || currentChapterId;
  const selectedBuiltinDemo = selectedProject?.id === "project_fantasy_demo";
  const [projectPanelMode, setProjectPanelMode] = useState<"view" | "create" | "edit">("view");
  const projectSceneCount = selectedProject ? flattenScenes(selectedProject).length : 0;

  useEffect(() => {
    if (workspaceLoaded && !hasWorkspace) {
      setProjectPanelMode("create");
    }
  }, [hasWorkspace, workspaceLoaded]);

  const startProjectCreate = () => {
    onProjectFormChange(defaultProjectForm);
    setProjectPanelMode("create");
  };

  const startProjectEdit = () => {
    if (selectedProject) {
      onProjectFormChange(projectToForm(selectedProject));
    }
    setProjectPanelMode("edit");
  };

  return (
    <>
      <div className="sidebar-scroll">
        <details className="sidebar-section workspace-section" open>
          <summary className="section-title">真实工作区</summary>
          {workspaceLoaded && hasWorkspace ? (
            <>
              <select
                className="sidebar-select"
                value={projectId}
                onChange={(event) => onSelectProject(event.target.value)}
              >
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {localizeText(project.title)}
                  </option>
                ))}
              </select>
              <div className="project-id">{projectId}</div>
              {selectedProject && (
                <div className="project-card">
                  <strong>{localizeText(selectedProject.title)}</strong>
                  <span>
                    {selectedProject.genre ?? "未分类"} / {selectedProject.language ?? "未设置语言"}
                  </span>
                  <span>
                    {chapters.length} 章 / {projectSceneCount} 场景
                  </span>
                  <span>{String(selectedProject.properties.narrative_pov ?? "未设置视角")}</span>
                </div>
              )}
            </>
          ) : (
            <div className="project-empty">
              {workspaceLoaded ? "后端还没有项目。" : "正在读取后端项目..."}
            </div>
          )}
          <div className="sidebar-button-row">
            <button
              disabled={busy !== null}
              onClick={onRefresh}
              title="从后端刷新项目树"
              type="button"
            >
              <RefreshCw size={15} /> 刷新
            </button>
            <button
              disabled={!canReview || busy !== null}
              onClick={startProjectCreate}
              title={canReview ? "创建新的小说项目" : "需要完全权限"}
              type="button"
            >
              <Database size={15} /> 新建项目
            </button>
            <button
              disabled={!canReview || !selectedProject || busy !== null}
              onClick={startProjectEdit}
              title={canReview ? "编辑当前项目信息" : "需要完全权限"}
              type="button"
            >
              <Settings size={15} /> 编辑项目
            </button>
            {selectedBuiltinDemo && (
              <button
                disabled={!canReview || busy !== null}
                onClick={onArchiveDemo}
                title={canReview ? "仅移除内置演示项目，真实项目不受影响" : "需要完全权限"}
                type="button"
              >
                <X size={15} /> 移除演示
              </button>
            )}
          </div>

        <nav className="scene-tree" aria-label="后端项目树">
          {selectedProject ? (
            selectedProject.chapters.map((chapter) => (
              <div key={chapter.id} className="chapter">
                <div className="chapter-row">
                  <BookOpen size={15} />
                  <span>{localizeText(chapter.title)}</span>
                  <small>{formatStatus(chapter.status ?? "planned")}</small>
                </div>
                {chapter.scenes.length ? (
                  chapter.scenes.map((scene) => (
                    <button
                      key={scene.id}
                      className={`scene-row ${scene.id === sceneId ? "selected" : ""}`}
                      onClick={() => onSelectScene(scene.id)}
                      type="button"
                    >
                      <ChevronRight size={14} />
                      <span>{localizeText(scene.title)}</span>
                      <small>{formatStatus(scene.status ?? "planned")}</small>
                    </button>
                  ))
                ) : (
                  <p className="tree-empty">本章节还没有场景。</p>
                )}
              </div>
            ))
          ) : (
            <EmptyState
              icon={<BookOpen />}
              title="没有后端项目树"
              text="创建项目后，章节和场景会从 Graph Store 读取。"
            />
          )}
        </nav>
        </details>

        {projectPanelMode !== "view" && (
          <details className="sidebar-section seed-panel" open>
            <summary className="section-title">
              {projectPanelMode === "edit" ? "编辑项目信息" : "创建新的小说项目"}
            </summary>
            <input
              placeholder="项目名称"
              value={projectForm.title}
              onChange={(event) =>
                onProjectFormChange((current) => ({ ...current, title: event.target.value }))
              }
            />
            <div className="compact-grid">
              <input
                placeholder="类型"
                value={projectForm.genre}
                onChange={(event) =>
                  onProjectFormChange((current) => ({ ...current, genre: event.target.value }))
                }
              />
              <input
                placeholder="语言"
                value={projectForm.language}
                onChange={(event) =>
                  onProjectFormChange((current) => ({ ...current, language: event.target.value }))
                }
              />
            </div>
            <input
              placeholder="目标篇幅"
              value={projectForm.target_length}
              onChange={(event) =>
                onProjectFormChange((current) => ({
                  ...current,
                  target_length: event.target.value
                }))
              }
            />
            <input
              placeholder="叙述视角"
              value={projectForm.narrative_pov}
              onChange={(event) =>
                onProjectFormChange((current) => ({
                  ...current,
                  narrative_pov: event.target.value
                }))
              }
            />
            <div className="compact-grid">
              <button
                className="sidebar-action"
                disabled={!canReview || busy !== null}
                onClick={() => {
                  const shouldClose = Boolean(projectForm.title.trim());
                  if (projectPanelMode === "edit") {
                    onUpdateProject();
                  } else {
                    onCreateProject();
                  }
                  if (shouldClose) {
                    setProjectPanelMode("view");
                  }
                }}
                type="button"
              >
                <Save size={15} /> {projectPanelMode === "edit" ? "保存信息" : "创建项目"}
              </button>
              {hasWorkspace && (
                <button
                  className="sidebar-action"
                  disabled={busy !== null}
                  onClick={() => setProjectPanelMode("view")}
                  type="button"
                >
                  <X size={15} /> 取消
                </button>
              )}
            </div>
          </details>
        )}

        <details className="sidebar-section seed-panel" open>
          <summary className="section-title">章节 / 场景</summary>
          <input
            placeholder="章节标题"
            value={chapterForm.title}
            onChange={(event) =>
              onChapterFormChange((current) => ({ ...current, title: event.target.value }))
            }
          />
          <div className="compact-grid">
            <input
              placeholder="章节序号"
              value={chapterForm.chapter_index}
              onChange={(event) =>
                onChapterFormChange((current) => ({
                  ...current,
                  chapter_index: event.target.value
                }))
              }
            />
            <button
              disabled={!canReview || !projectId || busy !== null}
              onClick={onCreateChapter}
              type="button"
            >
              <Save size={15} /> 添加章节
            </button>
          </div>
          <input
            placeholder="章节摘要"
            value={chapterForm.summary}
            onChange={(event) =>
              onChapterFormChange((current) => ({ ...current, summary: event.target.value }))
            }
          />
          <select
            value={sceneChapterId}
            onChange={(event) =>
              onSceneFormChange((current) => ({ ...current, chapter_id: event.target.value }))
            }
          >
            <option value="">选择章节</option>
            {chapters.map((chapter) => (
              <option key={chapter.id} value={chapter.id}>
                {localizeText(chapter.title)}
              </option>
            ))}
          </select>
          <input
            placeholder="场景标题"
            value={sceneForm.title}
            onChange={(event) =>
              onSceneFormChange((current) => ({ ...current, title: event.target.value }))
            }
          />
          <div className="compact-grid">
            <input
              placeholder="场景序号"
              value={sceneForm.scene_index}
              onChange={(event) =>
                onSceneFormChange((current) => ({
                  ...current,
                  scene_index: event.target.value
                }))
              }
            />
            <button
              disabled={!canReview || !projectId || !chapters.length || busy !== null}
              onClick={() => {
                if (!sceneForm.chapter_id && currentChapterId) {
                  onSceneFormChange((current) => ({
                    ...current,
                    chapter_id: currentChapterId
                  }));
                }
                onCreateScene();
              }}
              type="button"
            >
              <Save size={15} /> 添加场景
            </button>
          </div>
          <input
            placeholder="POV character_id"
            value={sceneForm.pov_character_id}
            onChange={(event) =>
              onSceneFormChange((current) => ({
                ...current,
                pov_character_id: event.target.value
              }))
            }
          />
          <input
            placeholder="location_id"
            value={sceneForm.location_id}
            onChange={(event) =>
              onSceneFormChange((current) => ({
                ...current,
                location_id: event.target.value
              }))
            }
          />
          <input
            placeholder="时间线"
            value={sceneForm.timeline_position}
            onChange={(event) =>
              onSceneFormChange((current) => ({
                ...current,
                timeline_position: event.target.value
              }))
            }
          />
          <input
            placeholder="场景目标"
            value={sceneForm.goal}
            onChange={(event) =>
              onSceneFormChange((current) => ({ ...current, goal: event.target.value }))
            }
          />
          <input
            placeholder="场景冲突"
            value={sceneForm.conflict}
            onChange={(event) =>
              onSceneFormChange((current) => ({ ...current, conflict: event.target.value }))
            }
          />
          <textarea
            className="mini-textarea"
            placeholder="必须包含：每行一条"
            value={sceneForm.must_include}
            onChange={(event) =>
              onSceneFormChange((current) => ({
                ...current,
                must_include: event.target.value
              }))
            }
          />
          <textarea
            className="mini-textarea"
            placeholder="禁止违反：每行一条"
            value={sceneForm.must_not_violate}
            onChange={(event) =>
              onSceneFormChange((current) => ({
                ...current,
                must_not_violate: event.target.value
              }))
            }
          />
        </details>

        <details className="sidebar-section seed-panel">
          <summary className="section-title">人物 / 地点 / 规则</summary>
          <input
            placeholder="人物名称"
            value={characterForm.name}
            onChange={(event) =>
              onCharacterFormChange((current) => ({ ...current, name: event.target.value }))
            }
          />
          <div className="compact-grid">
            <input
              placeholder="人物作用"
              value={characterForm.role}
              onChange={(event) =>
                onCharacterFormChange((current) => ({ ...current, role: event.target.value }))
              }
            />
            <button
              disabled={!canReview || !projectId || busy !== null}
              onClick={onCreateCharacter}
              type="button"
            >
              <Save size={15} /> 人物
            </button>
          </div>
          <input
            placeholder="地点名称"
            value={locationForm.name}
            onChange={(event) =>
              onLocationFormChange((current) => ({ ...current, name: event.target.value }))
            }
          />
          <div className="compact-grid">
            <input
              placeholder="地点类型"
              value={locationForm.type}
              onChange={(event) =>
                onLocationFormChange((current) => ({ ...current, type: event.target.value }))
              }
            />
            <button
              disabled={!canReview || !projectId || busy !== null}
              onClick={onCreateLocation}
              type="button"
            >
              <Save size={15} /> 地点
            </button>
          </div>
          <input
            placeholder="规则领域"
            value={worldRuleForm.domain}
            onChange={(event) =>
              onWorldRuleFormChange((current) => ({ ...current, domain: event.target.value }))
            }
          />
          <input
            placeholder="世界规则"
            value={worldRuleForm.rule}
            onChange={(event) =>
              onWorldRuleFormChange((current) => ({ ...current, rule: event.target.value }))
            }
          />
          <div className="compact-grid">
            <select
              value={worldRuleForm.severity}
              onChange={(event) =>
                onWorldRuleFormChange((current) => ({
                  ...current,
                  severity: event.target.value
                }))
              }
            >
              <option value="low">低</option>
              <option value="medium">中</option>
              <option value="high">高</option>
              <option value="critical">严重</option>
            </select>
            <button
              disabled={!canReview || !projectId || busy !== null}
              onClick={onCreateWorldRule}
              type="button"
            >
              <Save size={15} /> 规则
            </button>
          </div>
        </details>
      </div>
      <div className="sidebar-footer">
        <ShieldCheck size={16} />
        导入、草稿、候选事实都不会直接改写 canon（正典）。
      </div>
    </>
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

function DocumentReader({
  busy,
  canAnalyzeProjectStructure,
  canExtractDocumentFacts,
  canGenerate,
  document: doc,
  hasProject,
  hasScene,
  onAnalyzeStructure,
  onExtract,
  onExtractDocumentFacts,
  onSaveDraft,
  onSaveProposal,
  onSaveStyle
}: {
  busy: string | null;
  canAnalyzeProjectStructure: boolean;
  canExtractDocumentFacts: boolean;
  canGenerate: boolean;
  document: LibraryDocument | null;
  hasProject: boolean;
  hasScene: boolean;
  onAnalyzeStructure: (document: LibraryDocument) => void;
  onExtract: (document: LibraryDocument) => void;
  onExtractDocumentFacts: (document: LibraryDocument) => void;
  onSaveDraft: (document: LibraryDocument) => void;
  onSaveProposal: (document: LibraryDocument) => void;
  onSaveStyle: (document: LibraryDocument) => void;
}) {
  if (!doc) {
    return (
      <div className="document-reader empty">
        <EmptyState
          icon={<Library />}
          title="选择一个文档"
          text="导入内容默认只保存在浏览器内存中，不会自动进入草稿、候选事实或 canon。"
        />
      </div>
    );
  }

  const canBridge = doc.status === "ready" && canGenerate && hasScene && busy === null;
  const canBuildStructure = doc.status === "ready" && canAnalyzeProjectStructure && busy === null;
  const canUseLlmExtraction = doc.status === "ready" && canExtractDocumentFacts && busy === null;
  const noProjectTitle = hasProject ? undefined : "请先创建或选择项目。";

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
      <div className="reader-bridge">
        <span>当前是本地阅读器资料；只有点击下面按钮才会写入后端 Proposal/Draft/StyleSample/CandidateFact。</span>
        <div>
          <button
            className="primary"
            disabled={!canBuildStructure}
            onClick={() => onAnalyzeStructure(doc)}
            title={noProjectTitle ?? "从导入小说生成可编辑的项目结构草稿；作者确认后才会创建章节/场景。"}
            type="button"
          >
            <BookOpen size={14} /> 生成项目结构草稿
          </button>
          <button
            disabled={!canBridge}
            onClick={() => onSaveDraft(doc)}
            title="保存为当前场景 Draft Store 草稿，不写 canon。"
            type="button"
          >
            <FileText size={14} /> 设为当前草稿
          </button>
          <button
            disabled={!canBridge}
            onClick={() => onSaveProposal(doc)}
            title="保存为 Proposal Store 协作草稿，不写当前场景草稿。"
            type="button"
          >
            <SplitSquareVertical size={14} /> 存入草稿箱
          </button>
          <button
            disabled={doc.status !== "ready" || !canGenerate || busy !== null}
            onClick={() => onSaveStyle(doc)}
            title="保存为 StyleSample Store 风格样本，只作为 P6 软参考。"
            type="button"
          >
            <Wand2 size={14} /> 存为风格样本
          </button>
          <button
            disabled={!canUseLlmExtraction}
            onClick={() => onExtractDocumentFacts(doc)}
            title="把导入资料发送给已配置的 LLM，生成可编辑 fact_draft；不会自动进入 canon。"
            type="button"
          >
            <ShieldCheck size={14} /> LLM 抽设定草稿
          </button>
          <button
            disabled={!canBridge}
            onClick={() => onExtract(doc)}
            title="保存为草稿后，仅解析文中已有的 [[fact:...]] 显式标记。"
            type="button"
          >
            <ShieldCheck size={14} /> 解析显式标记
          </button>
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
  desktopBackend,
  desktopSettings,
  form,
  onApiKeyChange,
  onBackendRefresh,
  onBackendStart,
  onBackendStop,
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
  desktopBackend: DesktopBackendStatus | null;
  desktopSettings: DesktopSettings | null;
  form: AgentSettingsUpdate;
  onApiKeyChange: (value: string) => void;
  onBackendRefresh: () => void;
  onBackendStart: () => void;
  onBackendStop: () => void;
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
      {isDesktopRuntime() && (
        <section className="settings-block">
          <div className="settings-title"><Database size={15} /> 桌面后端</div>
          <MetricRow label="API 地址" value={desktopSettings?.backendUrl ?? "读取中"} />
          <MetricRow label="配置工作区" value={desktopSettings?.workspacePath ?? "读取中"} />
          <MetricRow label="运行状态" value={formatDesktopBackendDetail(desktopBackend)} />
          <MetricRow
            label="健康检查工作区"
            value={desktopBackend?.healthWorkspacePath ?? (desktopBackend?.reachable ? "未返回" : "未连接")}
          />
          <MetricRow
            label="进程"
            value={
              desktopBackend?.pid
                ? `${desktopBackend.managed ? "受管" : "外部"} PID ${desktopBackend.pid}`
                : desktopBackend?.reachable
                  ? "外部或未知进程"
                  : "未运行"
            }
          />
          {desktopBackend?.error && (
            <div className={`desktop-backend-card ${desktopBackend.workspaceCompatible ? "warning" : "danger"}`}>
              <AlertTriangle size={15} />
              <span>{desktopBackend.error}</span>
            </div>
          )}
          {desktopBackend?.reachable && !desktopBackend.managed && desktopBackend.workspaceCompatible && (
            <div className="desktop-backend-card warning">
              <AlertTriangle size={15} />
              <span>当前连接的是外部后端；退出桌面壳不会停止这个进程。</span>
            </div>
          )}
          <div className="settings-actions compact">
            <button onClick={onBackendRefresh} type="button" disabled={busy === "desktop-backend"}>
              <RefreshCw size={15} /> 刷新后端
            </button>
            <button onClick={onBackendStart} type="button" disabled={busy === "desktop-backend"}>
              <Play size={15} /> 启动/连接
            </button>
            <button onClick={onBackendStop} type="button" disabled={busy === "desktop-backend" || !desktopBackend?.managed}>
              <X size={15} /> 停止受管后端
            </button>
          </div>
        </section>
      )}

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
        <div className="reader-warning">
          <ShieldCheck size={15} />
          <span>保存后权限立即生效；具体 canon 写入仍需要后端 full 权限和人工 provenance。</span>
        </div>
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
      <ListBlock title="必须包含" items={pack.must_include.map(localizeText)} />
      <ListBlock title="禁止违反" items={pack.must_not_violate.map(localizeText)} tone="danger" />
      <ListBlock title="关系" items={pack.active_relationships.map(localizeText)} />
      <ListBlock title="伏笔" items={pack.unresolved_foreshadowing.map(localizeText)} />
      <ListBlock title="缺失上下文" items={pack.missing_context.map((gap) => `${formatSeverity(gap.severity)}: ${localizeText(gap.ref)} - ${formatKnownMessage(gap.message)}`)} tone="warning" />
      <ListBlock title="已丢弃项目" items={pack.budget.dropped_items.map(localizeText)} />
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
            <strong>{localizeText(fact.fact_type)}</strong>
            <span>{localizeText(fact.subject_id)} {localizeText(fact.relation)} {localizeText(fact.object_id)}</span>
          </div>
          <p>{localizeText(fact.rationale)}</p>
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

function GraphPreview({
  preview,
  selectedSceneId
}: {
  preview: ProjectGraphPreview | null;
  selectedSceneId: string;
}) {
  if (!preview) {
    return (
      <div className="graph-preview">
        <div className="preview-title"><Network size={15} /> 图谱 / 时间线</div>
        <EmptyState
          icon={<Network />}
          title="暂无后端图谱预览"
          text="选择真实项目后，这里会显示 Graph Store 中的 CANON 节点关系和场景时间线。"
        />
      </div>
    );
  }

  return (
    <div className="graph-preview">
      <div className="preview-title"><Network size={15} /> 图谱 / 时间线</div>
      <div className="graph-lines">
        {preview.relationships.length ? (
          preview.relationships.map((edge) => (
            <div key={edge.id}>
              <span title={edge.source_id}>{localizeText(edge.source_label)}</span>
              <b>{localizeText(edge.type)}</b>
              <span title={edge.target_id}>{localizeText(edge.target_label)}</span>
            </div>
          ))
        ) : (
          <p className="muted">暂无可预览关系。</p>
        )}
      </div>
      {preview.truncated && <p className="muted">预览已截断，只显示前几条关系。</p>}
      <div className="timeline">
        {preview.timeline.length ? (
          preview.timeline.map((item) => (
            <div
              key={item.id}
              className={item.id === selectedSceneId ? "current" : item.state}
            >
              {localizeText(item.label)}
            </div>
          ))
        ) : (
          <div>暂无场景</div>
        )}
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return <div className="meta"><span>{label}</span><strong>{localizeText(value) || "缺失"}</strong></div>;
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

function findProposalRef(proposal: ProposalArtifact, kind: string): string | null {
  return (
    proposal.derived_refs.find((ref) => ref.kind === kind)?.ref ??
    proposal.target_refs.find((ref) => ref.kind === kind)?.ref ??
    proposal.source_refs.find((ref) => ref.kind === kind)?.ref ??
    null
  );
}

function formatProposalRefs(refs: ProposalArtifact["source_refs"]): string[] {
  return refs.map((ref) => `${ref.kind}: ${ref.ref}${ref.note ? ` / ${ref.note}` : ""}`);
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

const permissionLevels: AgentPermissionLevel[] = ["read_only", "read_generate", "full"];

const permissionLabels: Record<AgentPermissionLevel, string> = {
  read_only: "仅读取",
  read_generate: "可读取生成",
  full: "完全权限"
};

const proposalTypes: ProposalArtifactType[] = [
  "scene_draft",
  "fact_draft",
  "scene_rebuild",
  "canon_patch",
  "outline_draft",
  "project_structure_draft"
];

const proposalStatuses: ProposalStatus[] = [
  "drafting",
  "agent_revised",
  "author_revised",
  "ready_for_review",
  "accepted",
  "rejected"
];

const proposalTypeLabels: Record<ProposalArtifactType, string> = {
  scene_draft: "场景草稿",
  fact_draft: "事实草稿",
  scene_rebuild: "场景重建",
  canon_patch: "Canon 补丁",
  outline_draft: "大纲草稿",
  project_structure_draft: "项目结构草稿"
};

const proposalStatusLabels: Record<ProposalStatus, string> = {
  drafting: "起草中",
  agent_revised: "Agent 已修订",
  author_revised: "作者已修订",
  ready_for_review: "待审",
  accepted: "已接受",
  rejected: "已拒绝"
};

const defaultPermissionDescriptions: Record<AgentPermissionLevel, string> = {
  read_only: "只能读取 canon（正典）、草稿、协作草稿、上下文包、运行记录和待审事实。",
  read_generate: "可读取并生成草稿、协作草稿、检查结果、候选事实和风格样本。",
  full: "允许完整本地作者操作，包括人工初始化（seed）、协作草稿决策和 CandidateFact（候选事实）审阅决策。"
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
  planned: "已规划",
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

function flattenScenes(project: ProjectOutline): SceneOutline[] {
  return project.chapters.flatMap((chapter) => chapter.scenes);
}

function projectToForm(project: ProjectOutline): ProjectForm {
  return {
    title: project.title ?? "",
    genre: project.genre ?? String(project.properties.genre ?? "fiction"),
    language: project.language ?? String(project.properties.language ?? "zh-CN"),
    target_length: String(project.properties.target_length ?? ""),
    narrative_pov: String(project.properties.narrative_pov ?? "")
  };
}

function findScene(
  projects: ProjectOutline[],
  projectId: string,
  sceneId: string
): SceneOutline | null {
  const project = projects.find((item) => item.id === projectId);
  if (!project) return null;
  return flattenScenes(project).find((scene) => scene.id === sceneId) ?? null;
}

function splitLines(value: string): string[] {
  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function toPositiveInteger(value: string, fallback: number): number {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function formatWriter(settings: AgentSettings | null): string {
  if (!settings) return "读取中";
  if (settings.scene_writer === "llm") {
    return settings.api_key_configured ? `LLM ${settings.llm_model}` : "LLM 未配置密钥";
  }
  return "本地规则";
}

function formatDesktopBackendLabel(status: DesktopBackendStatus): string {
  if (!status.reachable) return "后端未连接";
  if (!status.workspaceCompatible) return "后端工作区冲突";
  return status.managed ? "受管 FastAPI" : "外部 FastAPI";
}

function formatDesktopBackendDetail(status: DesktopBackendStatus | null): string {
  if (!status) return "读取中";
  if (!status.reachable) return "未连接";
  if (!status.workspaceCompatible) return "工作区冲突";
  return status.managed ? "已连接，桌面受管" : "已连接，外部进程";
}

function desktopBackendTone(status: DesktopBackendStatus): "good" | "warning" | "danger" | "neutral" {
  if (!status.reachable || !status.workspaceCompatible) return "danger";
  if (!status.managed) return "warning";
  return "good";
}

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
  const message = exc instanceof Error ? exc.message : String(exc);
  if (/Failed to fetch|NetworkError|Load failed/i.test(message)) {
    return "无法连接本机 FastAPI 后端。请在“设置 > 桌面后端”检查 8000 端口是否被旧后端占用，或先启动/连接受管后端。";
  }
  return message;
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
  return statusLabels[status] ?? localizeStatus(status) ?? status;
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
