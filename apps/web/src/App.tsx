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
  MapPin,
  MessageSquare,
  Network,
  Play,
  Redo2,
  RefreshCw,
  Save,
  Search,
  Settings,
  ShieldCheck,
  SplitSquareVertical,
  Undo2,
  UserRound,
  Wand2,
  X
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AgentDiscussionMode,
  AgentDiscussionRequest,
  AgentDiscussionResult,
  AgentPermissionLevel,
  AgentSettings,
  AgentSettingsUpdate,
  ApiRequestError,
  CandidateFact,
  ChapterOutline,
  ContextPack,
  ContinuityReport,
  CrossLanguagePolicy,
  DemoArchiveResult,
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
  SourceDocument,
  SourceDocumentImportRequest,
  SourceDocumentImportResult,
  SourceDocumentSummary,
  SourceDocumentUpdateRequest,
  SourceLanguage,
  SourceMediaType,
  WorkflowRun,
  WorkflowStep,
  apiGet,
  apiPatch,
  apiPost,
  apiPut
} from "./api";
import {
  APP_LOCALE,
  UI_LOCALE_STORAGE_KEY,
  activateLocale,
  appText,
  defaultPermissionDescriptions,
  formatDimension,
  formatIssueType,
  formatKnownMessage,
  formatProvenanceMethod,
  formatRefKind,
  formatSeverity,
  formatStatus,
  getLocaleCatalog,
  localizedTerms,
  localizeSystemValue,
  permissionLabels,
  proposalStatusLabels,
  proposalTypeLabels,
  reviewActionLabels,
  stepLabels,
  uiText,
  type AppLocale,
  normalizeAppLocale
} from "./localization";
import { APP_VERSION, GITHUB_LATEST_RELEASE_API } from "./version";
import "./styles.css";

type InspectorTab = "context" | "continuity" | "facts" | "settings";
type WorkspaceTab = "write" | "sources" | "agent" | "proposals" | "workflow";

type LibraryTreeNode = {
  id: string;
  name: string;
  path: string;
  type: "folder" | "document";
  children: LibraryTreeNode[];
  document?: SourceDocumentSummary;
};

type SourceImportProgress = {
  active: boolean;
  current: number;
  total: number;
  currentName: string;
  created: number;
  updated: number;
  unchanged: number;
  skipped: number;
  failed: number;
  issues: Array<{ name: string; message: string; technicalDetails?: string }>;
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
  volume_index: string;
  chapter_index: string;
  summary: string;
  purpose: string;
  status: string;
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
  outcome: string;
  emotional_turn: string;
  previous_scene_id: string;
  status: string;
  style_pov: string;
  style_tense: string;
  style_tone: string;
  style_sentence_rhythm: string;
  style_diction: string;
  style_dialogue_style: string;
  style_banned_patterns: string;
  required_characters: string;
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

type AgentDiscussionForm = {
  mode: AgentDiscussionMode;
  instruction: string;
  selectedText: string;
  includeContextPack: boolean;
  includeLatestDraft: boolean;
  allowWebSearch: boolean;
  webSearchQuery: string;
};

type UpdateStatus = {
  state: "idle" | "checking" | "current" | "available" | "installing" | "error";
  message: () => string;
  technicalDetails?: string;
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
  provider_label: "OpenAI-compatible",
  llm_base_url: "",
  llm_model: "deepseek-chat",
  llm_json_mode: true,
  permission_level: "full"
};

const defaultProjectForm: ProjectForm = {
  title: "",
  genre: "",
  language: "zh-CN",
  target_length: "",
  narrative_pov: ""
};

const defaultChapterForm: ChapterForm = {
  title: "",
  volume_index: "1",
  chapter_index: "1",
  summary: "",
  purpose: "",
  status: "planned"
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
  outcome: "",
  emotional_turn: "",
  previous_scene_id: "",
  status: "planned",
  style_pov: "",
  style_tense: "",
  style_tone: "",
  style_sentence_rhythm: "",
  style_diction: "",
  style_dialogue_style: "",
  style_banned_patterns: "",
  required_characters: "",
  must_include: "",
  must_not_violate: ""
};

const sceneStyleFieldMap: Array<[keyof SceneForm, string]> = [
  ["style_pov", "pov"],
  ["style_tense", "tense"],
  ["style_tone", "tone"],
  ["style_sentence_rhythm", "sentence_rhythm"],
  ["style_diction", "diction"],
  ["style_dialogue_style", "dialogue_style"]
];

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

const auditText = {
  updateProject: "workbench.project.update",
  updateChapter: "workbench.chapter.update",
  createChapter: "workbench.chapter.create",
  createScene: "workbench.scene.create",
  updateScene: "workbench.scene.update",
  createCharacter: "workbench.character.create",
  createLocation: "workbench.location.create",
  createWorldRule: "workbench.world_rule.create",
  createProposal: "workbench.proposal.create",
  reviseProposal: "agent.context_pack.proposal_revision",
  applyStructure: "workbench.project_structure.apply",
  reviewPrefix: "workbench.review"
} as const;

const defaultAgentDiscussionForm: AgentDiscussionForm = {
  mode: "discuss",
  instruction: "",
  selectedText: "",
  includeContextPack: true,
  includeLatestDraft: true,
  allowWebSearch: false,
  webSearchQuery: ""
};

export default function App() {
  const [uiLocale, setUiLocale] = useState<AppLocale>(() => loadUiLocale());
  activateLocale(uiLocale);
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
  const [storyCharacters, setStoryCharacters] = useState<GraphNodePayload[]>([]);
  const [storyLocations, setStoryLocations] = useState<GraphNodePayload[]>([]);
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
  const [agentDiscussionForm, setAgentDiscussionForm] =
    useState<AgentDiscussionForm>(defaultAgentDiscussionForm);
  const [agentDiscussionResult, setAgentDiscussionResult] =
    useState<AgentDiscussionResult | null>(null);
  const [draftSelection, setDraftSelection] = useState("");
  const draftTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [desktopUpdate, setDesktopUpdate] = useState<TauriUpdate | null>(null);
  const [updateStatus, setUpdateStatus] = useState<UpdateStatus>({
    state: "idle",
    message: () => uiText.runtime.updateIdle
  });
  const [desktopSettings, setDesktopSettings] = useState<DesktopSettings | null>(null);
  const [desktopBackend, setDesktopBackend] = useState<DesktopBackendStatus | null>(null);
  const [desktopBackendChecked, setDesktopBackendChecked] = useState(() => !isDesktopRuntime());
  const [sourceDocuments, setSourceDocuments] = useState<SourceDocumentSummary[]>([]);
  const [selectedSourceDocumentId, setSelectedSourceDocumentId] = useState<string | null>(null);
  const [selectedSourceDocument, setSelectedSourceDocument] = useState<SourceDocument | null>(null);
  const [sourceDetailLoading, setSourceDetailLoading] = useState(false);
  const [sourceDetailRevision, setSourceDetailRevision] = useState(0);
  const [selectedAgentSourceIds, setSelectedAgentSourceIds] = useState<Set<string>>(
    () => new Set()
  );
  const [crossLanguagePolicy, setCrossLanguagePolicy] =
    useState<CrossLanguagePolicy>("project_only");
  const [sourceImportProgress, setSourceImportProgress] = useState<SourceImportProgress | null>(null);
  const [expandedLibraryPaths, setExpandedLibraryPaths] = useState<Set<string>>(
    () => new Set(["library"])
  );
  const sourceListRequestSequenceRef = useRef(0);
  const draftRequestSequenceRef = useRef(0);
  const activeApiBaseRef = useRef(apiBase);
  const activeProjectIdRef = useRef(projectId);
  const activeSceneIdRef = useRef(sceneId);
  activeApiBaseRef.current = apiBase;
  activeProjectIdRef.current = projectId;
  activeSceneIdRef.current = sceneId;
  const [busy, setBusy] = useState<string | null>(null);
  const actionInFlightRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [technicalError, setTechnicalError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    // Ephemeral messages contain the catalog value that was active when the
    // operation completed. Drop them on an intentional locale switch so a
    // message from the previous UI language cannot leak into the new one.
    setError(null);
    setTechnicalError(null);
    setNotice(null);
    setSourceImportProgress((current) => current?.active ? current : null);
    try {
      window.localStorage.setItem(UI_LOCALE_STORAGE_KEY, uiLocale);
    } catch {
      // The active locale still works for this session when storage is unavailable.
    }
    document.documentElement.lang = uiLocale;
    document.title = appText.documentTitle;
    if (isDesktopRuntime()) {
      invoke("set_native_locale", { locale: uiLocale }).catch((exc) => {
        setError(uiText.errors.requestFailed);
        setTechnicalError(technicalErrorMessage(exc));
      });
    }
  }, [uiLocale]);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === projectId) ?? null,
    [projectId, projects]
  );
  const selectedScene = useMemo(
    () => findScene(projects, projectId, sceneId),
    [projectId, projects, sceneId]
  );
  const currentChapterId = useMemo(
    () =>
      findSceneChapterId(projects, projectId, sceneId) ??
      selectedProject?.chapters[0]?.id ??
      "",
    [projectId, projects, sceneId, selectedProject]
  );
  const selectedChapter = useMemo(
    () => selectedProject?.chapters.find((chapter) => chapter.id === currentChapterId) ?? null,
    [currentChapterId, selectedProject]
  );
  const hasWorkspace = projects.length > 0;
  const hasScene = Boolean(projectId && sceneId);
  const endpoint = useMemo(
    () => (projectId && sceneId ? `/projects/${projectId}/scenes/${sceneId}` : ""),
    [projectId, sceneId]
  );
  const libraryTree = useMemo(
    () => buildLibraryTree(sourceDocuments),
    [sourceDocuments]
  );
  const selectedSourceSummary = useMemo(
    () => sourceDocuments.find((document) => document.id === selectedSourceDocumentId) ?? null,
    [selectedSourceDocumentId, sourceDocuments]
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
    if (actionInFlightRef.current) return;
    actionInFlightRef.current = true;
    setBusy(label);
    setError(null);
    setTechnicalError(null);
    setNotice(null);
    try {
      await action();
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : String(exc);
      if (isLocalizedUserError(message)) {
        setError(message);
      } else {
        setError(uiText.errors.requestFailed);
        setTechnicalError(
          exc instanceof ApiRequestError ? exc.technicalDetails : toErrorMessage(exc)
        );
      }
    } finally {
      actionInFlightRef.current = false;
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
      setError(uiText.errors.requestFailed);
      setTechnicalError(status.error);
    }
    return status;
  }, []);

  const stopDesktopBackend = useCallback(async () => {
    if (!isDesktopRuntime()) return;
    const status = await invoke<DesktopBackendStatus>("stop_backend");
    setDesktopBackend(status);
    setDesktopBackendChecked(true);
    setNotice(status.reachable ? uiText.runtime.backendStopExternal : uiText.runtime.backendStopped);
  }, []);

  const refreshSources = useCallback(
    async (targetProjectId = projectId) => {
      const requestSequence = ++sourceListRequestSequenceRef.current;
      const requestApiBase = apiBase;
      const requestIsCurrent = () =>
        requestSequence === sourceListRequestSequenceRef.current &&
        activeApiBaseRef.current === requestApiBase &&
        activeProjectIdRef.current === targetProjectId;
      if (!targetProjectId) {
        if (requestIsCurrent()) {
          setSourceDocuments([]);
          setSelectedSourceDocumentId(null);
          setSelectedSourceDocument(null);
        }
        return [];
      }
      let payload: { sources: SourceDocumentSummary[] };
      try {
        payload = await apiGet<{ sources: SourceDocumentSummary[] }>(
          requestApiBase,
          `/projects/${targetProjectId}/sources`
        );
      } catch (exc) {
        if (!requestIsCurrent()) return [];
        throw exc;
      }
      if (!requestIsCurrent()) return [];
      setSourceDocuments(payload.sources);
      setSourceDetailRevision((current) => current + 1);
      const readyIds = new Set(
        payload.sources
          .filter((document) => document.extraction_status === "ready")
          .map((document) => document.id)
      );
      setSelectedAgentSourceIds((current) =>
        new Set(Array.from(current).filter((sourceId) => readyIds.has(sourceId)))
      );
      setSelectedSourceDocumentId((current) =>
        current && payload.sources.some((document) => document.id === current) ? current : null
      );
      return payload.sources;
    },
    [apiBase, projectId]
  );

  const importSourceFiles = useCallback(
    async (files: File[], retryTarget?: SourceDocumentSummary) => {
      if (!projectId) throw new Error(uiText.errors.selectProjectOrCreate);
      if (!files.length) {
        setNotice(uiText.notices.sourceImportNoSelection);
        return;
      }
      const progress: SourceImportProgress = {
        active: true,
        current: 0,
        total: files.length,
        currentName: "",
        created: 0,
        updated: 0,
        unchanged: 0,
        failed: 0,
        skipped: 0,
        issues: []
      };
      setSourceImportProgress({ ...progress });
      let firstPersistedId: string | null = null;
      for (const [index, file] of files.entries()) {
        progress.current = index + 1;
        progress.currentName = file.name;
        setSourceImportProgress({ ...progress });
        const mediaType = getSourceMediaType(file.name);
        if (!mediaType) {
          if (retryTarget) {
            progress.failed += 1;
          } else {
            progress.skipped += 1;
          }
          progress.issues.push({
            name: file.name,
            message: uiText.errors.sourceUnsupportedFormat
          });
          setSourceImportProgress({ ...progress });
          continue;
        }
        try {
          if (retryTarget && mediaType !== retryTarget.media_type) {
            throw new Error(uiText.errors.sourceRetryFormatMismatch);
          }
          const request = await prepareSourceDocumentImport(
            file,
            mediaType,
            retryTarget?.language
          );
          if (retryTarget) {
            request.title = retryTarget.title;
            request.relative_path = retryTarget.relative_path;
          }
          const result = await apiPost<SourceDocumentImportResult>(
            apiBase,
            `/projects/${projectId}/sources`,
            request
          );
          firstPersistedId ??= result.document.id;
          if (result.created) progress.created += 1;
          else if (result.updated) progress.updated += 1;
          else progress.unchanged += 1;
          if (result.document.extraction_status === "failed") {
            progress.failed += 1;
            progress.issues.push({
              name: result.document.title,
              message: uiText.library.unknownReadError,
              technicalDetails: result.document.error ?? undefined
            });
          }
          for (const path of getAncestorFolderPaths(result.document.relative_path)) {
            setExpandedLibraryPaths((current) => new Set(current).add(path));
          }
        } catch (exc) {
          progress.failed += 1;
          const detail = exc instanceof ApiRequestError ? exc.technicalDetails : toErrorMessage(exc);
          progress.issues.push({
            name: file.name,
            message: isLocalizedUserError(detail) ? detail : uiText.errors.requestFailed,
            technicalDetails: isLocalizedUserError(detail) ? undefined : detail
          });
        }
        setSourceImportProgress({ ...progress });
      }
      progress.active = false;
      progress.currentName = "";
      setSourceImportProgress({ ...progress });
      await refreshSources(projectId);
      if (firstPersistedId) setSelectedSourceDocumentId(firstPersistedId);
      setNotice(retryTarget ? uiText.notices.sourceRetryFinished : uiText.notices.sourceImportFinished);
    },
    [apiBase, projectId, refreshSources]
  );

  const handleLibraryInputChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(event.currentTarget.files ?? []);
      event.currentTarget.value = "";
      if (!files.length) return;
      void runAction("source-import", () => importSourceFiles(files));
    },
    [importSourceFiles, runAction]
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

  const refreshStoryBibleRefs = useCallback(
    async (targetProjectId = projectId) => {
      if (!targetProjectId) {
        setStoryCharacters([]);
        setStoryLocations([]);
        return;
      }
      const [characters, locations] = await Promise.all([
        apiGet<{ characters: GraphNodePayload[] }>(
          apiBase,
          `/projects/${targetProjectId}/characters`
        ),
        apiGet<{ locations: GraphNodePayload[] }>(
          apiBase,
          `/projects/${targetProjectId}/locations`
        )
      ]);
      setStoryCharacters(characters.characters);
      setStoryLocations(locations.locations);
    },
    [apiBase, projectId]
  );

  const refreshLatestDraft = useCallback(
    async (targetProjectId = projectId, targetSceneId = sceneId) => {
      const requestSequence = ++draftRequestSequenceRef.current;
      const requestApiBase = apiBase;
      const requestIsCurrent = () =>
        requestSequence === draftRequestSequenceRef.current &&
        activeApiBaseRef.current === requestApiBase &&
        activeProjectIdRef.current === targetProjectId &&
        activeSceneIdRef.current === targetSceneId;
      if (!targetProjectId || !targetSceneId) {
        if (requestIsCurrent()) {
          setDraft(null);
          setDraftText("");
          setDraftSummary("");
        }
        return;
      }
      let payload: { draft: Draft | null };
      try {
        payload = await apiGet<{ draft: Draft | null }>(
          requestApiBase,
          `/projects/${targetProjectId}/scenes/${targetSceneId}/draft`
        );
      } catch (exc) {
        if (!requestIsCurrent()) return;
        throw exc;
      }
      if (!requestIsCurrent()) return;
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
    setNotice(uiText.notices.settingsSaved);
  }, [agentForm, apiBase, apiKeyInput, clearApiKey]);

  const checkForUpdates = useCallback(async (silent = false) => {
    setDesktopUpdate(null);
    if (!silent) {
      setUpdateStatus({ state: "checking", message: () => uiText.runtime.updateChecking });
    }
    if (isDesktopRuntime()) {
      try {
        const update = await checkTauriUpdate();
        if (update) {
          setDesktopUpdate(update);
          setUpdateStatus({
            state: "available",
            channel: "desktop",
            message: () => uiText.runtime.desktopUpdateAvailable(update.version),
            latestVersion: update.version,
            publishedAt: update.date,
            canInstall: true
          });
          return;
        }
        setUpdateStatus({
          state: "current",
          channel: "desktop",
          message: () => uiText.runtime.updateCurrent(APP_VERSION)
        });
      } catch (exc) {
        setUpdateStatus({
          state: "error",
          channel: "desktop",
          message: () => uiText.runtime.updateChannelUnavailable,
          technicalDetails: toErrorMessage(exc)
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
          message: () => uiText.runtime.noGithubRelease
        });
        return;
      }
      if (!response.ok) {
        throw new Error(`GitHub returned HTTP ${response.status}`);
      }
      const release = (await response.json()) as GitHubRelease;
      const latestVersion = normalizeVersion(release.tag_name ?? "");
      if (!latestVersion) {
        throw new Error("Latest GitHub Release has no valid version number.");
      }
      const installer = release.assets?.find((asset) =>
        /StoryGraph[ .]Agent_.*_x64-setup\.exe$/i.test(asset.name)
      );
      const comparison = compareVersions(latestVersion, APP_VERSION);
      if (comparison > 0) {
        setUpdateStatus({
          state: "available",
          channel: "github",
          message: () => uiText.runtime.installerUpdateAvailable(latestVersion),
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
        message: () => uiText.runtime.updateCurrent(APP_VERSION),
        latestVersion,
        releaseUrl: release.html_url,
        publishedAt: release.published_at
      });
    } catch (exc) {
      setUpdateStatus({
        state: "error",
        channel: "github",
        message: () => uiText.runtime.updateCheckFailed,
        technicalDetails: toErrorMessage(exc)
      });
    }
  }, []);

  const installAvailableUpdate = useCallback(async () => {
    if (!desktopUpdate) {
      setUpdateStatus({
        state: "error",
        channel: "desktop",
        message: () => uiText.runtime.noInstallableUpdate
      });
      return;
    }

    setUpdateStatus({
      state: "installing",
      channel: "desktop",
      message: () => uiText.runtime.installingUpdate(desktopUpdate.version),
      latestVersion: desktopUpdate.version,
      publishedAt: desktopUpdate.date,
      canInstall: false
    });

    let updateInstalled = false;
    try {
      await invoke("stop_backend").catch(() => undefined);
      await desktopUpdate.downloadAndInstall();
      updateInstalled = true;
      setUpdateStatus({
        state: "installing",
        channel: "desktop",
        message: () => uiText.runtime.installedRestarting,
        latestVersion: desktopUpdate.version,
        publishedAt: desktopUpdate.date
      });
      const { relaunch } = await import("@tauri-apps/plugin-process");
      await relaunch();
    } catch (exc) {
      const failureMessage = technicalErrorMessage(exc);
      if (updateInstalled) {
        setUpdateStatus({
          state: "error",
          channel: "desktop",
          message: () => uiText.runtime.installedManualRestart,
          technicalDetails: failureMessage,
          latestVersion: desktopUpdate.version,
          publishedAt: desktopUpdate.date,
          canInstall: false
        });
        return;
      }

      let backendRecoveryMessage: string;
      let backendRecoveryDetails: string | null = null;
      try {
        const status = await invoke<DesktopBackendStatus>("start_backend");
        setDesktopBackend(status);
        setDesktopBackendChecked(true);
        backendRecoveryDetails = status.error ?? null;
        if (status.reachable && status.workspaceCompatible) {
          backendRecoveryMessage = uiText.runtime.backendRecovered;
        } else if (status.reachable) {
          backendRecoveryMessage = uiText.runtime.backendRecoveredIncompatible;
        } else {
          backendRecoveryMessage = uiText.runtime.backendRecoveryFailed;
        }
      } catch (recoveryExc) {
        setDesktopBackend(null);
        setDesktopBackendChecked(true);
        backendRecoveryMessage = uiText.runtime.backendRecoveryFailed;
        backendRecoveryDetails = technicalErrorMessage(recoveryExc);
      }
      setUpdateStatus({
        state: "error",
        channel: "desktop",
        message: () => `${uiText.runtime.updateInstallFailed} ${backendRecoveryMessage}`,
        technicalDetails: [failureMessage, backendRecoveryDetails].filter(Boolean).join("\n"),
        latestVersion: desktopUpdate.version,
        publishedAt: desktopUpdate.date,
        canInstall: true
      });
    }
  }, [desktopUpdate]);

  const createProject = useCallback(async () => {
    if (!projectForm.title.trim()) {
      throw new Error(uiText.errors.projectNameRequired);
    }
    const result = await apiPost<{ project_id: string }>(apiBase, "/projects", {
      title: projectForm.title.trim(),
      genre: projectForm.genre.trim() || getLocaleCatalog(projectForm.language).contentDefaults.genre,
      language: normalizeAppLocale(projectForm.language),
      target_length: projectForm.target_length.trim() || null,
      narrative_pov:
        projectForm.narrative_pov.trim() ||
        getLocaleCatalog(projectForm.language).contentDefaults.narrativePov
    });
    setProjectForm(defaultProjectForm);
    await refreshWorkspace(result.project_id);
    await refreshGraphPreview(result.project_id);
    setWorkspaceTab("sources");
    setNotice(uiText.notices.projectCreated);
  }, [apiBase, projectForm, refreshGraphPreview, refreshWorkspace]);

  const updateProject = useCallback(async () => {
    if (!projectId) throw new Error(uiText.errors.selectProject);
    if (!selectedProject) throw new Error(uiText.errors.selectProject);
    if (!projectForm.title.trim()) {
      throw new Error(uiText.errors.projectNameNotEmpty);
    }
    if (projectForm.language !== "zh-CN" && projectForm.language !== "en-US") {
      throw new Error(uiText.errors.projectLanguageRequired);
    }
    if (
      projectForm.language !== selectedProject?.language &&
      !window.confirm(uiText.language.projectLanguageChangeConfirm)
    ) {
      return;
    }
    await apiPatch<GraphNodePayload>(apiBase, `/projects/${projectId}`, {
      title: projectForm.title.trim(),
      genre: projectForm.genre.trim() || null,
      language: projectForm.language,
      expected_language: selectedProject.language,
      language_change_policy: "future_outputs_only",
      target_length: projectForm.target_length.trim() || null,
      narrative_pov: projectForm.narrative_pov.trim() || null,
      reviewer: "author",
      rationale: auditText.updateProject,
      source_ref: "author_seed:workbench_project"
    });
    await refreshWorkspace(projectId, sceneId);
    await refreshGraphPreview(projectId);
    setCrossLanguagePolicy("project_only");
    setSelectedAgentSourceIds(new Set());
    setNotice(uiText.notices.projectUpdated);
  }, [apiBase, projectForm, projectId, refreshGraphPreview, refreshWorkspace, sceneId, selectedProject]);

  const updateChapter = useCallback(async () => {
    if (!projectId) throw new Error(uiText.errors.selectProject);
    const targetChapterId = currentChapterId;
    if (!targetChapterId) throw new Error(uiText.errors.chooseChapterForEdit);
    if (!chapterForm.title.trim()) throw new Error(uiText.errors.chapterTitleRequired);
    await apiPatch<GraphNodePayload>(apiBase, `/projects/${projectId}/chapters/${targetChapterId}`, {
      title: chapterForm.title.trim(),
      volume_index: toPositiveInteger(chapterForm.volume_index, 1),
      chapter_index: toPositiveInteger(chapterForm.chapter_index, 1),
      summary: chapterForm.summary.trim() || null,
      purpose: chapterForm.purpose.trim() || null,
      status: chapterForm.status.trim() || "planned",
      reviewer: "author",
      rationale: auditText.updateChapter,
      source_ref: "author_seed:workbench_chapter_metadata"
    });
    await refreshWorkspace(projectId, sceneId);
    await refreshGraphPreview(projectId);
    setNotice(uiText.notices.chapterUpdated);
  }, [
    apiBase,
    chapterForm,
    currentChapterId,
    projectId,
    refreshGraphPreview,
    refreshWorkspace,
    sceneId
  ]);

  const createChapter = useCallback(async () => {
    if (!projectId) throw new Error(uiText.errors.selectProjectOrCreate);
    if (!chapterForm.title.trim()) throw new Error(uiText.errors.chapterTitleRequired);
    await apiPost<GraphNodePayload>(apiBase, `/projects/${projectId}/chapters`, {
      title: chapterForm.title.trim(),
      volume_index: toPositiveInteger(chapterForm.volume_index, 1),
      chapter_index: toPositiveInteger(chapterForm.chapter_index, 1),
      summary: chapterForm.summary.trim() || null,
      purpose: chapterForm.purpose.trim() || null,
      status: chapterForm.status.trim() || "planned",
      reviewer: "author",
      rationale: auditText.createChapter,
      source_ref: "author_seed:workbench_outline"
    });
    setChapterForm((current) => ({
      ...defaultChapterForm,
      volume_index: current.volume_index,
      chapter_index: String(toPositiveInteger(current.chapter_index, 1) + 1)
    }));
    await refreshWorkspace(projectId, sceneId);
    await refreshGraphPreview(projectId);
    setNotice(uiText.notices.chapterCreated);
  }, [apiBase, chapterForm, projectId, refreshGraphPreview, refreshWorkspace, sceneId]);

  const createScene = useCallback(async () => {
    if (!projectId) throw new Error(uiText.errors.selectProjectOrCreate);
    const targetChapterId = sceneForm.chapter_id || selectedProject?.chapters[0]?.id || "";
    if (!targetChapterId) throw new Error(uiText.errors.chooseChapter);
    if (!sceneForm.title.trim()) throw new Error(uiText.errors.sceneTitleRequired);
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
        outcome: sceneForm.outcome.trim() || null,
        emotional_turn: sceneForm.emotional_turn.trim() || null,
        previous_scene_id: sceneForm.previous_scene_id.trim() || null,
        style_constraints: sceneStyleConstraints(sceneForm),
        required_characters: splitLines(sceneForm.required_characters),
        must_include: splitLines(sceneForm.must_include),
        must_not_violate: splitLines(sceneForm.must_not_violate),
        status: sceneForm.status.trim() || "planned",
        reviewer: "author",
        rationale: auditText.createScene,
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
    setNotice(uiText.notices.sceneCreated);
  }, [apiBase, projectId, refreshGraphPreview, refreshWorkspace, sceneForm, selectedProject]);

  const updateScene = useCallback(async () => {
    if (!projectId || !sceneId) throw new Error(uiText.errors.chooseSceneForEdit);
    if (!sceneForm.title.trim()) throw new Error(uiText.errors.sceneTitleRequired);
    await apiPatch<GraphNodePayload>(apiBase, `/projects/${projectId}/scenes/${sceneId}`, {
      title: sceneForm.title.trim(),
      scene_index: toPositiveInteger(sceneForm.scene_index, selectedScene?.scene_index ?? 1),
      pov_character_id: sceneForm.pov_character_id.trim() || null,
      location_id: sceneForm.location_id.trim() || null,
      timeline_position: sceneForm.timeline_position.trim() || null,
      goal: sceneForm.goal.trim() || null,
      conflict: sceneForm.conflict.trim() || null,
      outcome: sceneForm.outcome.trim() || null,
      emotional_turn: sceneForm.emotional_turn.trim() || null,
      previous_scene_id: sceneForm.previous_scene_id.trim() || null,
      style_constraints: sceneStyleConstraints(sceneForm),
      required_characters: splitLines(sceneForm.required_characters),
      must_include: splitLines(sceneForm.must_include),
      must_not_violate: splitLines(sceneForm.must_not_violate),
      status: sceneForm.status.trim() || "planned",
      reviewer: "author",
      rationale: auditText.updateScene,
      source_ref: "author_seed:workbench_scene_metadata"
    });
    await refreshWorkspace(projectId, sceneId);
    await refreshGraphPreview(projectId);
    setContextPack(null);
    setNotice(uiText.notices.sceneUpdated);
  }, [
    apiBase,
    projectId,
    refreshGraphPreview,
    refreshWorkspace,
    sceneForm,
    sceneId,
    selectedScene
  ]);

  const createCharacter = useCallback(async () => {
    if (!projectId) throw new Error(uiText.errors.selectProjectOrCreate);
    if (!characterForm.name.trim()) throw new Error(uiText.errors.characterNameRequired);
    const shouldFillCurrentScene = !sceneForm.pov_character_id.trim();
    const node = await apiPost<GraphNodePayload>(apiBase, `/projects/${projectId}/characters`, {
      name: characterForm.name.trim(),
      properties: { role: characterForm.role.trim() || undefined },
      reviewer: "author",
      rationale: auditText.createCharacter,
      source_ref: "author_seed:workbench_story_bible"
    });
    setCharacterForm(defaultCharacterForm);
    setSceneForm((current) =>
      current.pov_character_id
        ? current
        : {
            ...current,
            pov_character_id: node.id,
            required_characters: appendLineIfMissing(current.required_characters, node.id)
          }
    );
    await refreshStoryBibleRefs(projectId);
    await refreshGraphPreview(projectId);
    setNotice(uiText.runtime.characterCreated(node.id, shouldFillCurrentScene));
  }, [apiBase, characterForm, projectId, refreshGraphPreview, refreshStoryBibleRefs, sceneForm]);

  const createLocation = useCallback(async () => {
    if (!projectId) throw new Error(uiText.errors.selectProjectOrCreate);
    if (!locationForm.name.trim()) throw new Error(uiText.errors.locationNameRequired);
    const shouldFillCurrentScene = !sceneForm.location_id.trim();
    const node = await apiPost<GraphNodePayload>(apiBase, `/projects/${projectId}/locations`, {
      name: locationForm.name.trim(),
      properties: { type: locationForm.type.trim() || undefined },
      reviewer: "author",
      rationale: auditText.createLocation,
      source_ref: "author_seed:workbench_story_bible"
    });
    setLocationForm(defaultLocationForm);
    setSceneForm((current) =>
      current.location_id ? current : { ...current, location_id: node.id }
    );
    await refreshStoryBibleRefs(projectId);
    await refreshGraphPreview(projectId);
    setNotice(uiText.runtime.locationCreated(node.id, shouldFillCurrentScene));
  }, [apiBase, locationForm, projectId, refreshGraphPreview, refreshStoryBibleRefs, sceneForm]);

  const createWorldRule = useCallback(async () => {
    if (!projectId) throw new Error(uiText.errors.selectProjectOrCreate);
    if (!worldRuleForm.domain.trim() || !worldRuleForm.rule.trim()) {
      throw new Error(uiText.errors.worldRuleRequired);
    }
    await apiPost<GraphNodePayload>(apiBase, `/projects/${projectId}/world-rules`, {
      domain: worldRuleForm.domain.trim(),
      rule: worldRuleForm.rule.trim(),
      severity: worldRuleForm.severity,
      reviewer: "author",
      rationale: auditText.createWorldRule,
      source_ref: "author_seed:workbench_story_bible"
    });
    setWorldRuleForm(defaultWorldRuleForm);
    await refreshGraphPreview(projectId);
    setNotice(uiText.notices.worldRuleCreated);
  }, [apiBase, projectId, refreshGraphPreview, worldRuleForm]);

  const saveDocumentAsDraft = useCallback(
    async (document: SourceDocument) => {
      if (!endpoint) throw new Error(uiText.errors.selectSceneForDraft);
      requireProjectContentLanguage(document, selectedProject?.language);
      const sourceText = requireReadySourceText(document);
      const saved = await apiPost<Draft>(apiBase, `${endpoint}/draft`, {
        text: sourceText,
        summary: `${getLocaleCatalog(selectedProject?.language).ui.library.importedDraftSummaryPrefix}${document.title}`
      });
      setDraft(saved);
      setDraftText(saved.text);
      setDraftSummary(saved.summary ?? "");
      setWorkspaceTab("write");
      setNotice(uiText.notices.sourceSavedAsDraft(document.title, saved.version));
      return saved;
    },
    [apiBase, endpoint, selectedProject]
  );

  const saveDocumentAsStyleSample = useCallback(
    async (document: SourceDocument) => {
      if (!projectId) throw new Error(uiText.errors.selectProjectForStyle);
      requireProjectContentLanguage(document, selectedProject?.language);
      const sourceText = requireReadySourceText(document);
      await apiPost(apiBase, `/projects/${projectId}/style-samples`, {
        text: sourceText,
        source_ref: `source_document:${document.id}`,
        pov: contextPack?.style_constraints.pov ?? null,
        tone: contextPack?.style_constraints.tone ?? null,
        dialogue_style: contextPack?.style_constraints.dialogue_style ?? null,
        tags: ["source_document"],
        summary: `${getLocaleCatalog(selectedProject?.language).ui.library.importedStyleSummaryPrefix}${document.title}`
      });
      setNotice(uiText.notices.sourceSavedAsStyle(document.title));
    },
    [apiBase, contextPack, projectId, selectedProject]
  );

  const analyzeDocumentStructure = useCallback(
    async (document: SourceDocumentSummary) => {
      if (!projectId) throw new Error(uiText.errors.selectProject);
      if (document.extraction_status !== "ready") {
        throw new Error(uiText.errors.sourceNotReadyStructure);
      }
      if (document.language === "und") {
        throw new Error(uiText.errors.sourceLanguageRequired);
      }
      const projectLanguage = outputLanguageOrNull(selectedProject?.language);
      if (!projectLanguage) throw new Error(uiText.errors.projectLanguageRequired);
      if (
        document.language !== projectLanguage &&
        crossLanguagePolicy === "project_only"
      ) {
        throw new Error(uiText.errors.mixedLanguageStructure);
      }
      const result = await apiPost<ProjectStructureDraftResult>(
        apiBase,
        `/projects/${projectId}/sources/${document.id}/structure-draft`,
        {
          max_chapters: 24,
          max_scenes_per_chapter: 12,
          cross_language_policy: crossLanguagePolicy
        }
      );
      await refreshProposals(projectId);
      setSelectedProposalId(result.proposal.id);
      setWorkspaceTab("proposals");
      const sceneCount = result.outline.chapters.reduce(
        (total, chapter) => total + chapter.scenes.length,
        0
      );
      setNotice(uiText.notices.sourceStructureCreated(
        result.outline.chapters.length,
        sceneCount,
        result.truncated
      ));
    },
    [apiBase, crossLanguagePolicy, projectId, refreshProposals, selectedProject]
  );

  const saveDocumentAsProposal = useCallback(
    async (document: SourceDocument) => {
      if (!projectId || !sceneId) throw new Error(uiText.errors.selectSceneForDraft);
      requireProjectContentLanguage(document, selectedProject?.language);
      const sourceText = requireReadySourceText(document);
      const proposal = await apiPost<ProposalArtifact>(
        apiBase,
        `/projects/${projectId}/proposals`,
        {
          artifact_type: "scene_draft",
          title: `${getLocaleCatalog(selectedProject?.language).ui.library.importedProposalTitlePrefix}${document.title}`,
          body: sourceText,
          target_refs: [{ kind: "scene", ref: sceneId }],
          source_refs: [{ kind: "source_document", ref: document.id, note: document.title }],
          created_by: "author",
          created_via: "import",
          provenance_note: `${getLocaleCatalog(selectedProject?.language).ui.library.importedProposalNotePrefix}${document.title}`
        }
      );
      await refreshProposals(projectId);
      setSelectedProposalId(proposal.id);
      setWorkspaceTab("proposals");
      setNotice(uiText.notices.sourceSavedAsProposal(document.title));
    },
    [apiBase, projectId, refreshProposals, sceneId, selectedProject]
  );

  const archiveSourceDocument = useCallback(
    async (document: SourceDocumentSummary) => {
      if (!projectId) throw new Error(uiText.errors.selectProject);
      await apiPost<SourceDocumentSummary>(
        apiBase,
        `/projects/${projectId}/sources/${document.id}/archive`
      );
      setSelectedAgentSourceIds((current) => {
        const next = new Set(current);
        next.delete(document.id);
        return next;
      });
      if (selectedSourceDocumentId === document.id) {
        setSelectedSourceDocumentId(null);
        setSelectedSourceDocument(null);
      }
      await refreshSources(projectId);
      setNotice(uiText.notices.sourceArchived(document.title));
    },
    [apiBase, projectId, refreshSources, selectedSourceDocumentId]
  );

  const updateSourceDocumentLanguage = useCallback(
    async (document: SourceDocumentSummary, language: "zh-CN" | "en-US") => {
      if (!projectId) throw new Error(uiText.errors.selectProject);
      const request: SourceDocumentUpdateRequest = {
        language,
        expected_updated_at: document.updated_at
      };
      const updated = await apiPatch<SourceDocument>(
        apiBase,
        `/projects/${projectId}/sources/${document.id}`,
        request
      );
      setSelectedSourceDocument(updated);
      if (
        crossLanguagePolicy === "project_only" &&
        updated.language !== outputLanguageOrNull(selectedProject?.language)
      ) {
        setSelectedAgentSourceIds((current) => {
          const next = new Set(current);
          next.delete(updated.id);
          return next;
        });
      }
      await refreshSources(projectId);
      setSelectedSourceDocumentId(updated.id);
    },
    [apiBase, crossLanguagePolicy, projectId, refreshSources, selectedProject]
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
    setNotice(uiText.runtime.archiveDemo(result.nodes_archived, result.relationships_archived));
  }, [apiBase, refreshFacts, refreshWorkspace]);

  const buildContext = useCallback(async () => {
    if (!endpoint) throw new Error(uiText.errors.selectScene);
    const pack = await apiPost<ContextPack>(apiBase, `${endpoint}/context-pack`);
    setContextPack(pack);
    setWorkspaceTab("write");
    setActiveTab("context");
    setNotice(uiText.notices.contextRefreshed);
  }, [apiBase, endpoint]);

  const saveDraft = useCallback(async () => {
    if (!endpoint) throw new Error(uiText.errors.selectScene);
    const saved = await apiPost<Draft>(apiBase, `${endpoint}/draft`, {
      text: draftText,
      summary: draftSummary
    });
    setDraft(saved);
    setNotice(uiText.runtime.draftSaved(saved.version));
    setWorkspaceTab("write");
  }, [apiBase, draftSummary, draftText, endpoint]);

  const readDraftSelection = useCallback((target: HTMLTextAreaElement | null) => {
    if (!target) {
      return "";
    }
    const selection = target.value.slice(target.selectionStart, target.selectionEnd).trim();
    return selection;
  }, []);

  const captureDraftSelection = useCallback((event: React.SyntheticEvent<HTMLTextAreaElement>) => {
    setDraftSelection(readDraftSelection(event.currentTarget));
  }, [readDraftSelection]);

  const refreshDraftSelection = useCallback(() => {
    const selection = readDraftSelection(draftTextareaRef.current);
    setDraftSelection(selection);
    return selection;
  }, [readDraftSelection]);

  const handleDraftTextChange = useCallback((event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setDraftText(event.target.value);
    setDraftSelection(readDraftSelection(event.target));
  }, [readDraftSelection]);

  const handleDraftSummaryChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    setDraftSummary(event.target.value);
  }, []);

  const useDraftSelectionForAgent = useCallback(() => {
    const selection = draftSelection || refreshDraftSelection();
    if (!selection) {
      setNotice(uiText.notices.draftSelectionRequired);
      return;
    }
    setAgentDiscussionForm((current) => ({
      ...current,
      mode: "revise_selection",
      selectedText: selection,
      includeLatestDraft: true
    }));
    setWorkspaceTab("agent");
  }, [draftSelection, refreshDraftSelection]);

  const requestAgentDiscussion = useCallback(async () => {
    if (!endpoint || !projectId) throw new Error(uiText.errors.selectScene);
    const instruction = agentDiscussionForm.instruction.trim();
    if (!instruction) throw new Error(uiText.errors.agentInstructionRequired);
    const selectedText = agentDiscussionForm.selectedText.trim();
    if (agentDiscussionForm.mode === "revise_selection" && !selectedText) {
      throw new Error(uiText.errors.agentSelectionRequired);
    }
    if (
      agentDiscussionForm.mode !== "discuss" &&
      (!agentDiscussionForm.includeLatestDraft || !draft || draftText !== draft.text)
    ) {
      throw new Error(uiText.errors.agentRevisionRequiresSavedDraft);
    }
    const payload: AgentDiscussionRequest = {
      mode: agentDiscussionForm.mode,
      instruction,
      selected_text: agentDiscussionForm.includeLatestDraft ? selectedText || null : null,
      base_text: null,
      include_context_pack: agentDiscussionForm.includeContextPack,
      include_latest_draft: agentDiscussionForm.includeLatestDraft,
      local_sources: [],
      source_document_ids: Array.from(selectedAgentSourceIds),
      allow_web_search: agentDiscussionForm.allowWebSearch,
      web_search_query: agentDiscussionForm.webSearchQuery.trim() || null,
      cross_language_policy: crossLanguagePolicy
    };
    const result = await apiPost<AgentDiscussionResult>(
      apiBase,
      `${endpoint}/agent-discussion`,
      payload
    );
    setAgentDiscussionResult(result);
    const refreshed = await refreshProposals(projectId);
    const created = refreshed.find((proposal) => proposal.id === result.proposal.id);
    setSelectedProposalId(created?.id ?? result.proposal.id);
    setProposalTitle(result.proposal.title);
    setProposalText(result.proposal.body);
    setProposalArtifactType(result.proposal.artifact_type);
    setWorkspaceTab("agent");
    setNotice(
      result.replacement_applied
        ? uiText.notices.agentSceneDraftCreated
        : uiText.notices.agentDiscussionCreated
    );
  }, [
    agentDiscussionForm,
    apiBase,
    draft,
    draftText,
    endpoint,
    projectId,
    refreshProposals,
    selectedAgentSourceIds,
    crossLanguagePolicy
  ]);

  const generateDraft = useCallback(async () => {
    if (!endpoint) throw new Error(uiText.errors.selectScene);
    const saved = await apiPost<Draft>(apiBase, `${endpoint}/draft`);
    const pack = await apiPost<ContextPack>(apiBase, `${endpoint}/context-pack`);
    setContextPack(pack);
    setDraft(saved);
    setDraftText(saved.text);
    setDraftSummary(saved.summary ?? "");
    setNotice(uiText.runtime.draftGenerated(saved.version));
    setWorkspaceTab("write");
  }, [apiBase, endpoint]);

  const runScene = useCallback(async () => {
    if (!endpoint) throw new Error(uiText.errors.selectScene);
    const result = await apiPost<SceneRunResult>(
      apiBase,
      `${endpoint}/runs/scene-generation`
    );
    if (!result.draft || !result.continuity_report) {
      throw new Error(uiText.errors.workflowMissingDraft);
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
    setNotice(uiText.runtime.workflowStatus(formatStatus(result.workflow_run.status)));
  }, [apiBase, endpoint, refreshFacts]);

  const startNewProposal = useCallback(() => {
    const contentLanguage = outputLanguageOrNull(selectedProject?.language);
    setSelectedProposalId(null);
    setProposalArtifactType("scene_draft");
    setProposalTitle(
      selectedScene && contentLanguage
        ? `${selectedScene.title} ${getLocaleCatalog(contentLanguage).contentDefaults.proposalSuffix}`
        : ""
    );
    setProposalText("");
    setProposalSourceDraftId(draft?.id ?? "");
  }, [draft, selectedProject, selectedScene]);

  const saveProposal = useCallback(async () => {
    if (!projectId) throw new Error(uiText.errors.selectProjectOrCreate);
    const contentLanguage = outputLanguageOrNull(selectedProject?.language);
    if (!contentLanguage) throw new Error(uiText.errors.projectLanguageRequired);
    const title =
      proposalTitle.trim() ||
      getLocaleCatalog(contentLanguage).contentDefaults.untitledProposal;
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
      setNotice(uiText.runtime.proposalSaved(saved.version));
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
        provenance_note: auditText.createProposal
      }
    );
    await refreshProposals(projectId);
    setSelectedProposalId(saved.id);
    setNotice(uiText.runtime.proposalCreated(saved.version));
  }, [
    apiBase,
    projectId,
    proposalArtifactType,
    proposalSourceDraftId,
    proposalText,
    proposalTitle,
    refreshProposals,
    sceneId,
    selectedProject,
    selectedProposal
  ]);

  const requestAgentProposal = useCallback(async () => {
    if (!endpoint) throw new Error(uiText.errors.selectScene);
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
          note: auditText.reviseProposal
        }
      );
      await refreshProposals(projectId);
      setSelectedProposalId(revised.id);
      setWorkspaceTab("proposals");
      setNotice(uiText.runtime.proposalRevised(revised.version));
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
    setNotice(uiText.notices.agentSceneDraftCreated);
  }, [apiBase, endpoint, projectId, refreshProposals, selectedProposal]);

  const extractStateToProposal = useCallback(async () => {
    if (!endpoint) throw new Error(uiText.errors.selectScene);
    const result = await apiPost<{
      proposal: ProposalArtifact;
      candidate_previews: CandidateFact[];
      candidates: CandidateFact[];
    }>(apiBase, `${endpoint}/extract-state`, { output_target: "proposal_workspace" });
    await refreshProposals(projectId);
    setSelectedProposalId(result.proposal.id);
    setWorkspaceTab("proposals");
    setNotice(uiText.runtime.factDraftCreated(result.candidate_previews.length));
  }, [apiBase, endpoint, projectId, refreshProposals]);

  const submitProposalReview = useCallback(async () => {
    if (!selectedProposal || !projectId) throw new Error(uiText.errors.selectProposal);
    const saved = await apiPost<ProposalArtifact>(
      apiBase,
      `/projects/${projectId}/proposals/${selectedProposal.id}/submit-review`,
      { expected_version: selectedProposal.version }
    );
    await refreshProposals(projectId);
    setSelectedProposalId(saved.id);
    setNotice(uiText.runtime.proposalSubmitted(saved.id));
  }, [apiBase, projectId, refreshProposals, selectedProposal]);

  const reviewProposal = useCallback(
    async (decision: "accept" | "reject") => {
      if (!selectedProposal || !projectId) throw new Error(uiText.errors.selectProposal);
      const saved = await apiPost<ProposalArtifact>(
        apiBase,
        `/projects/${projectId}/proposals/${selectedProposal.id}/${decision}`,
        { reviewer: "author", expected_version: selectedProposal.version }
      );
      await refreshProposals(projectId);
      setSelectedProposalId(saved.id);
      setNotice(uiText.runtime.proposalDecided(decision === "accept"));
    },
    [apiBase, projectId, refreshProposals, selectedProposal]
  );

  const promoteProposalToDraft = useCallback(async () => {
    if (!selectedProposal || !projectId || !sceneId) throw new Error(uiText.errors.selectSceneAndProposal);
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
    setNotice(uiText.runtime.proposalPromoted(result.draft.version));
  }, [apiBase, projectId, refreshProposals, sceneId, selectedProposal]);

  const applyProjectStructureProposal = useCallback(async () => {
    if (!selectedProposal || !projectId) throw new Error(uiText.errors.selectProjectStructureProposal);
    const result = await apiPost<ProjectStructureApplyResult>(
      apiBase,
      `/projects/${projectId}/proposals/${selectedProposal.id}/apply/project-structure`,
      {
        reviewer: "author",
        rationale: auditText.applyStructure,
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
      uiText.runtime.structureApplied(
        result.chapters.length,
        result.scenes.length,
        result.already_applied
      )
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
    if (!selectedProposal || !projectId) throw new Error(uiText.errors.selectProposal);
    const sourceDraftId =
      proposalSourceDraftId.trim() || findProposalRef(selectedProposal, "draft") || draft?.id || "";
    if (!sourceDraftId) throw new Error(uiText.errors.sourceDraftRequired);
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
    setNotice(uiText.runtime.candidatesSubmitted(result.candidates.length));
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
        { reviewer: "author", note: `${auditText.reviewPrefix}.${action}` }
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
        setNotice(uiText.runtime.factReviewed(reviewActionLabels[action], true));
        return;
      }
      await refreshGraphPreview(projectId);
      setNotice(uiText.runtime.factReviewed(reviewActionLabels[action], false));
    },
    [apiBase, projectId, refreshFacts, refreshGraphPreview, run]
  );

  useEffect(() => {
    if (!isDesktopRuntime()) return;
    refreshDesktopBackend("start").catch((exc) => {
      setDesktopBackendChecked(true);
      setError(uiText.errors.requestFailed);
      setTechnicalError(technicalErrorMessage(exc));
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
      setError(uiText.runtime.backendWorkspaceConflict);
      setTechnicalError(desktopBackend.error ?? null);
      return;
    }
    refreshWorkspace().catch((exc) => {
      setWorkspaceLoaded(true);
      setError(uiText.errors.requestFailed);
      setTechnicalError(technicalErrorMessage(exc));
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
    refreshStoryBibleRefs(projectId).catch(() => undefined);
  }, [projectId, refreshStoryBibleRefs]);

  useEffect(() => {
    refreshLatestDraft().catch(() => undefined);
  }, [refreshLatestDraft]);

  useEffect(() => {
    refreshProposals().catch(() => undefined);
  }, [refreshProposals]);

  useEffect(() => {
    setSourceDocuments([]);
    setSelectedSourceDocumentId(null);
    setSelectedSourceDocument(null);
    setSelectedAgentSourceIds(new Set());
    setCrossLanguagePolicy("project_only");
    setSourceImportProgress(null);
    setExpandedLibraryPaths(new Set(["library"]));
    setAgentDiscussionResult(null);
    if (!projectId) return;
    refreshSources(projectId).catch((exc) => {
      setError(uiText.errors.requestFailed);
      setTechnicalError(technicalErrorMessage(exc));
    });
  }, [projectId, refreshSources]);

  useEffect(() => {
    setAgentDiscussionResult(null);
    setSelectedAgentSourceIds(new Set());
    setCrossLanguagePolicy("project_only");
    setDraftSelection("");
    setDraft(null);
    setDraftText("");
    setDraftSummary("");
    setAgentDiscussionForm((current) => ({ ...current, selectedText: "" }));
  }, [projectId, sceneId]);

  useEffect(() => {
    if (!projectId || !selectedSourceDocumentId) {
      setSelectedSourceDocument(null);
      setSourceDetailLoading(false);
      return;
    }
    let cancelled = false;
    setSelectedSourceDocument(null);
    setSourceDetailLoading(true);
    apiGet<SourceDocument>(
      apiBase,
      `/projects/${projectId}/sources/${selectedSourceDocumentId}`
    )
      .then((document) => {
        if (!cancelled) setSelectedSourceDocument(document);
      })
      .catch((exc) => {
        if (!cancelled) {
          setError(uiText.errors.requestFailed);
          setTechnicalError(technicalErrorMessage(exc));
        }
      })
      .finally(() => {
        if (!cancelled) setSourceDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiBase, projectId, selectedSourceDocumentId, sourceDetailRevision]);

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
  const projectLanguageReady = outputLanguageOrNull(selectedProject?.language) !== null;
  const canRunScene = hasScene && canGenerate && !writerNeedsKey && projectLanguageReady;
  const canDiscussWithAgent = hasScene && canGenerate && llmConfigured && projectLanguageReady;
  const toggleAgentSource = useCallback((sourceId: string) => {
    const source = sourceDocuments.find((item) => item.id === sourceId);
    if (!source || source.language === "und") {
      setNotice(uiText.language.sourceUnknownDisabled);
      return;
    }
    if (
      source.language !== outputLanguageOrNull(selectedProject?.language) &&
      crossLanguagePolicy !== "explicit_reference"
    ) {
      setNotice(uiText.language.sourceMismatchDisabled);
      return;
    }
    setSelectedAgentSourceIds((current) => {
      const next = new Set(current);
      if (next.has(sourceId)) {
        next.delete(sourceId);
      } else if (next.size < 32) {
        next.add(sourceId);
      } else {
        setNotice(uiText.notices.agentSourceLimit);
      }
      return next;
    });
  }, [crossLanguagePolicy, selectedProject, sourceDocuments]);
  const changeCrossLanguagePolicy = useCallback(
    (policy: CrossLanguagePolicy) => {
      setCrossLanguagePolicy(policy);
      if (policy !== "project_only") return;
      const projectLanguage = outputLanguageOrNull(selectedProject?.language);
      const allowedIds = new Set(
        sourceDocuments
          .filter((source) => source.language === projectLanguage)
          .map((source) => source.id)
      );
      setSelectedAgentSourceIds(
        (current) => new Set(Array.from(current).filter((id) => allowedIds.has(id)))
      );
    },
    [selectedProject, sourceDocuments]
  );
  const runEditCommand = useCallback((command: "undo" | "redo") => {
    const active = document.activeElement;
    if (
      active instanceof HTMLInputElement ||
      active instanceof HTMLTextAreaElement
    ) {
      document.execCommand(command);
    }
  }, []);
  const backendStatusLabel = desktopBackend ? formatDesktopBackendLabel(desktopBackend) : localizedTerms.fastApi;
  const backendStatusTone = desktopBackend ? desktopBackendTone(desktopBackend) : "good";

  return (
    <div className="workbench">
      <header className="topbar">
        <div className="brand">
          <div className="mark"><GitBranch size={18} /></div>
          <div>
            <strong>{appText.brandName}</strong>
            <span>{appText.tagline}</span>
          </div>
        </div>
        <div className="command-bar" aria-label={uiText.commandBar.ariaLabel}>
          <button
            type="button"
            onClick={() => runAction("save", saveDraft)}
            disabled={!canGenerate || !hasScene || busy !== null}
            title={uiText.commandBar.saveDraftTitle}
          >
            <Save size={15} /> {uiText.common.save}
          </button>
          <button type="button" onClick={() => runEditCommand("undo")} title={uiText.commandBar.undoTitle}>
            <Undo2 size={15} /> {uiText.common.undo}
          </button>
          <button type="button" onClick={() => runEditCommand("redo")} title={uiText.commandBar.redoTitle}>
            <Redo2 size={15} /> {uiText.common.redo}
          </button>
          <button
            type="button"
            onClick={() =>
              runAction("workspace", async () => {
                await refreshWorkspace(projectId, sceneId);
              })
            }
            disabled={busy !== null}
            title={uiText.commandBar.refreshTitle}
          >
            <RefreshCw size={15} /> {uiText.common.refresh}
          </button>
          <button type="button" onClick={() => setWorkspaceTab("sources")} title={uiText.commandBar.sourcesTitle}>
            <Library size={15} /> {uiText.tabs.sources}
          </button>
          <button type="button" onClick={() => setWorkspaceTab("proposals")} title={uiText.commandBar.proposalsTitle}>
            <SplitSquareVertical size={15} /> {uiText.proposals.title}
          </button>
          <button type="button" onClick={() => setWorkspaceTab("agent")} title={uiText.commandBar.agentTitle}>
            <MessageSquare size={15} /> {uiText.tabs.agent}
          </button>
          <button
            type="button"
            onClick={() => runAction("run", runScene)}
            disabled={!canRunScene || busy !== null}
            title={uiText.commandBar.runTitle}
          >
            <Play size={15} /> {uiText.common.writing}
          </button>
        </div>
        <label className="api-control">
          <Database size={15} />
          <input
            value={apiBase}
            onChange={(event) => setApiBase(event.target.value)}
            aria-label={uiText.runtime.apiAddressAria}
          />
        </label>
        <div className="top-actions">
          <StatusDot label={backendStatusLabel} tone={backendStatusTone} />
          <StatusDot label={permissionLabels[agentSettings?.permission_level ?? "full"]} tone={permissionTone(agentSettings?.permission_level)} />
          <StatusDot label={`v${APP_VERSION}`} tone="neutral" />
          <button className="icon-button" title={uiText.tabs.settings} type="button" onClick={() => setActiveTab("settings")}>
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
            onUpdateChapter={() => runAction("update-chapter", updateChapter)}
            onUpdateScene={() => runAction("update-scene", updateScene)}
            onWorldRuleFormChange={setWorldRuleForm}
            projectForm={projectForm}
            projectId={projectId}
            projects={projects}
            sceneForm={sceneForm}
            sceneId={sceneId}
            selectedChapter={selectedChapter}
            selectedProject={selectedProject}
            selectedScene={selectedScene}
            storyCharacters={storyCharacters}
            storyLocations={storyLocations}
            workspaceLoaded={workspaceLoaded}
            worldRuleForm={worldRuleForm}
          />
        </aside>

        <main className="editor">
          <section className="scene-toolbar">
            <div>
              <h1>
                {selectedScene?.title ||
                  (hasWorkspace ? uiText.workspace.importedStructureTitle : uiText.workspace.emptyWorkspaceTitle)}
              </h1>
              <p>
                {hasScene
                  ? `${sceneId} / ${uiText.editor.pov} ${contextPack?.pov_character_id || selectedScene?.pov_character_id || uiText.common.notSet}`
                  : hasWorkspace
                    ? uiText.workspace.noSceneWithWorkspace
                    : uiText.workspace.noSceneEmptyWorkspace}
              </p>
            </div>
            <div className="toolbar-actions">
              <button
                onClick={() => runAction("context", buildContext)}
                type="button"
                disabled={!hasScene}
              >
                <RefreshCw size={16} /> {uiText.editor.contextButton}
              </button>
              <button
                onClick={() => runAction("save", saveDraft)}
                type="button"
                disabled={!canGenerate || !hasScene}
              >
                <Save size={16} /> {uiText.editor.saveButton}
              </button>
              <button
                onClick={() => runAction("draft", generateDraft)}
                type="button"
                disabled={missingCritical || !canRunScene}
                title={uiText.editor.generateDraftTitle}
              >
                <FileText size={16} /> {uiText.editor.generateDraftButton}
              </button>
              <button
                className="primary"
                onClick={() => runAction("run", runScene)}
                type="button"
                disabled={!canRunScene}
                title={uiText.editor.runWorkflowTitle}
              >
                <Play size={16} /> {uiText.editor.runWorkflowButton}
              </button>
            </div>
          </section>

          <section className="state-strip" aria-label={uiText.workspace.workflowStatusAria}>
            <StatusDot
              label={`${uiText.stateStrip.projectPrefix}: ${selectedProject?.title || uiText.common.notCreated}`}
              tone={hasWorkspace ? "good" : "warning"}
            />
            <StatusDot
              label={`${uiText.stateStrip.writerPrefix}: ${formatWriter(agentSettings)}`}
              tone={writerNeedsKey ? "danger" : canGenerate ? "good" : "neutral"}
            />
            <StatusDot
              label={writerNeedsKey ? uiText.stateStrip.llmIncomplete : uiText.stateStrip.safetyBoundary}
              tone={writerNeedsKey ? "danger" : "neutral"}
            />
          </section>

          <section className="workspace-tabs" aria-label={uiText.workspace.mainWorkspaceAria}>
            <TabButton active={workspaceTab === "write"} onClick={() => setWorkspaceTab("write")} icon={<FileText size={15} />} label={uiText.tabs.write} />
            <TabButton active={workspaceTab === "sources"} onClick={() => setWorkspaceTab("sources")} icon={<Library size={15} />} label={uiText.tabs.sources} />
            <TabButton active={workspaceTab === "agent"} onClick={() => setWorkspaceTab("agent")} icon={<MessageSquare size={15} />} label={uiText.tabs.agent} />
            <TabButton active={workspaceTab === "proposals"} onClick={() => setWorkspaceTab("proposals")} icon={<SplitSquareVertical size={15} />} label={uiText.tabs.proposals} />
            <TabButton active={workspaceTab === "workflow"} onClick={() => setWorkspaceTab("workflow")} icon={<Activity size={15} />} label={uiText.tabs.workflow} />
          </section>

          {(error || notice) && (
            <div className={`message ${error ? "error" : "notice"}`}>
              {error ? <AlertTriangle size={16} /> : <Check size={16} />}
              <div>
                <span>{error ?? notice}</span>
                {error && technicalError && (
                  <details>
                    <summary>{uiText.errors.technicalDetails}</summary>
                    <code>{technicalError}</code>
                  </details>
                )}
              </div>
            </div>
          )}

          {!hasWorkspace && (
            <section className="empty-workspace">
              <EmptyState
                icon={<Database />}
                title={uiText.workspace.emptyTitle}
                text={uiText.workspace.emptyText}
              />
            </section>
          )}

          {workspaceTab === "write" && (
            <section className="meta-grid" aria-label={uiText.workspace.sceneMetadataAria}>
              <Meta label={uiText.editor.goal} value={contextPack?.scene_goal || selectedScene?.goal || ""} />
              <Meta label={uiText.editor.conflict} value={contextPack?.conflict || selectedScene?.conflict || ""} />
              <Meta
                label={uiText.editor.timeline}
                value={contextPack?.timeline_position || selectedScene?.timeline_position || ""}
              />
              <Meta label={uiText.editor.location} value={contextPack?.location_id || selectedScene?.location_id || ""} />
            </section>
          )}

          {workspaceTab === "sources" && (
          <section
            className={`library-panel ${sourceImportProgress ? "has-import-progress" : ""}`}
            aria-label={uiText.library.ariaLabel}
          >
            <div className="library-header">
              <div>
                <span><Library size={15} /> {uiText.library.title}</span>
                <small>{uiText.library.summary(sourceDocuments.length)}</small>
              </div>
              <div className="library-actions">
                <label className={`import-button ${!projectId || !canGenerate || busy !== null ? "disabled" : ""}`}>
                  <FileUp size={15} />
                  {uiText.library.fileButton}
                  <input
                    accept=".txt,.md,.markdown,.docx"
                    disabled={!projectId || !canGenerate || busy !== null}
                    multiple
                    onChange={handleLibraryInputChange}
                    type="file"
                  />
                </label>
                <label className={`import-button ${!projectId || !canGenerate || busy !== null ? "disabled" : ""}`}>
                  <FolderOpen size={15} />
                  {uiText.library.folderButton}
                  <DirectoryInput
                    accept=".txt,.md,.markdown,.docx"
                    directory=""
                    disabled={!projectId || !canGenerate || busy !== null}
                    multiple
                    onChange={handleLibraryInputChange}
                    type="file"
                    webkitdirectory=""
                  />
                </label>
                <button
                  onClick={() => runAction("source-refresh", async () => {
                    await refreshSources(projectId);
                  })}
                  type="button"
                  disabled={!projectId || busy !== null}
                >
                  <RefreshCw size={15} /> {uiText.library.refreshButton}
                </button>
              </div>
            </div>
            {sourceImportProgress && (
              <SourceImportStatus progress={sourceImportProgress} />
            )}
            <div className="library-grid">
              <div className="library-tree-panel">
                {sourceDocuments.length ? (
                  <LibraryTree
                    expandedPaths={expandedLibraryPaths}
                    node={libraryTree}
                    onSelectDocument={setSelectedSourceDocumentId}
                    onToggleFolder={toggleLibraryPath}
                    selectedDocumentId={selectedSourceDocumentId}
                  />
                ) : (
                  <EmptyState
                    icon={<FolderOpen />}
                    title={uiText.library.emptyTitle}
                    text={uiText.library.emptyText}
                  />
                )}
              </div>
              <DocumentReader
                busy={busy}
                canGenerate={canGenerate}
                document={selectedSourceDocument}
                hasProject={Boolean(projectId)}
                hasScene={hasScene}
                loading={sourceDetailLoading}
                onAnalyzeStructure={(document) =>
                  runAction("document-structure", () => analyzeDocumentStructure(document))
                }
                onArchive={(document) =>
                  runAction("source-archive", () => archiveSourceDocument(document))
                }
                onRetry={(document, file) =>
                  runAction("source-retry", () => importSourceFiles([file], document))
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
                onUpdateLanguage={(document, language) =>
                  runAction("source-language", () =>
                    updateSourceDocumentLanguage(document, language)
                  )
                }
                onPolicyChange={changeCrossLanguagePolicy}
                crossLanguagePolicy={crossLanguagePolicy}
                projectLanguage={outputLanguageOrNull(selectedProject?.language)}
                summary={selectedSourceSummary}
              />
            </div>
          </section>
          )}

          {workspaceTab === "agent" && (
          <AgentDiscussionPanel
            busy={busy}
            canDiscuss={canDiscussWithAgent}
            draftSelection={draftSelection}
            form={agentDiscussionForm}
            hasScene={hasScene}
            llmConfigured={llmConfigured}
            onFormChange={setAgentDiscussionForm}
            onOpenProposal={() => setWorkspaceTab("proposals")}
            onPolicyChange={changeCrossLanguagePolicy}
            onSubmit={() => runAction("agent-discussion", requestAgentDiscussion)}
            onToggleSource={toggleAgentSource}
            onUseDraftSelection={useDraftSelectionForAgent}
            result={agentDiscussionResult}
            selectedSourceIds={selectedAgentSourceIds}
            selectedProposal={selectedProposal}
            sources={sourceDocuments}
            crossLanguagePolicy={crossLanguagePolicy}
            projectLanguage={outputLanguageOrNull(selectedProject?.language)}
          />
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
            setNotice(uiText.notices.openedFactReview);
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
              <span>{uiText.editor.draftTitle}</span>
              <div className="draft-header-actions">
                <small>
                  {draft
                    ? `v${draft.version} / ${draft.id} / ${formatArtifactLanguage(draft.content_language, draft.language_inferred)}`
                    : uiText.editor.unsavedDraft}
                </small>
                <button
                  disabled={!draftText.trim() || busy !== null}
                  onClick={useDraftSelectionForAgent}
                  title={uiText.editor.markSelectionForAgentTitle}
                  type="button"
                >
                  <MessageSquare size={13} /> {uiText.editor.markSelectionForAgent}
                </button>
              </div>
            </summary>
            <textarea
              ref={draftTextareaRef}
              value={draftText}
              onChange={handleDraftTextChange}
              onKeyUp={captureDraftSelection}
              onMouseUp={captureDraftSelection}
              onSelect={captureDraftSelection}
              spellCheck={false}
              aria-label={uiText.editor.draftBodyAria}
            />
            <input
              className="summary-input"
              value={draftSummary}
              onChange={handleDraftSummaryChange}
              aria-label={uiText.editor.draftSummaryAria}
            />
          </details>
          )}

          {workspaceTab === "workflow" && (
          <details className="run-panel collapsible-panel" open>
            <summary className="run-head">
              <div>
                <span>{uiText.editor.runTitle}</span>
                <small>{run?.id ?? uiText.editor.runNotStarted}</small>
              </div>
              <StatusDot label={formatStatus(run?.status ?? "idle")} tone={statusTone(run?.status)} />
            </summary>
            <div className="step-track">
              {(runEvents.length ? runEvents : fallbackSteps).map((step) => (
                <div key={step.name} className={`step ${step.status}`}>
                  <span>{formatWorkflowStep(step.name)}</span>
                  <small>{formatStatus(step.status)}</small>
                </div>
              ))}
            </div>
          </details>
          )}
        </main>

        <aside className="inspector">
          <div className="tabs" role="tablist">
            <TabButton active={activeTab === "context"} onClick={() => setActiveTab("context")} icon={<Boxes size={15} />} label={uiText.tabs.context} />
            <TabButton active={activeTab === "continuity"} onClick={() => setActiveTab("continuity")} icon={<Activity size={15} />} label={uiText.tabs.continuity} />
            <TabButton active={activeTab === "facts"} onClick={() => setActiveTab("facts")} icon={<ShieldCheck size={15} />} label={uiText.tabs.facts} />
            <TabButton active={activeTab === "settings"} onClick={() => setActiveTab("settings")} icon={<Settings size={15} />} label={uiText.tabs.settings} />
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
              locale={uiLocale}
              onApiKeyChange={setApiKeyInput}
              onClearApiKeyChange={setClearApiKey}
              onFormChange={setAgentForm}
              onLocaleChange={setUiLocale}
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

function AgentDiscussionPanel({
  busy,
  canDiscuss,
  crossLanguagePolicy,
  draftSelection,
  form,
  hasScene,
  llmConfigured,
  onFormChange,
  onOpenProposal,
  onPolicyChange,
  onSubmit,
  onToggleSource,
  onUseDraftSelection,
  result,
  selectedProposal,
  selectedSourceIds,
  sources,
  projectLanguage
}: {
  busy: string | null;
  canDiscuss: boolean;
  crossLanguagePolicy: CrossLanguagePolicy;
  draftSelection: string;
  form: AgentDiscussionForm;
  hasScene: boolean;
  llmConfigured: boolean;
  onFormChange: React.Dispatch<React.SetStateAction<AgentDiscussionForm>>;
  onOpenProposal: () => void;
  onPolicyChange: (policy: CrossLanguagePolicy) => void;
  onSubmit: () => void;
  onToggleSource: (sourceId: string) => void;
  onUseDraftSelection: () => void;
  result: AgentDiscussionResult | null;
  selectedProposal: ProposalArtifact | null;
  selectedSourceIds: Set<string>;
  sources: SourceDocumentSummary[];
  projectLanguage: AppLocale | null;
}) {
  const selectedRequired = form.mode === "revise_selection";
  const draftRequired = form.mode !== "discuss";
  const canSubmit =
    canDiscuss &&
    busy === null &&
    form.instruction.trim().length > 0 &&
    (!draftRequired || form.includeLatestDraft) &&
    (!selectedRequired || form.selectedText.trim().length > 0);
  return (
    <section className="agent-panel" aria-label={uiText.agentDiscussion.ariaLabel}>
      <div className="agent-compose">
        <div className="agent-head">
          <div>
            <span><MessageSquare size={15} /> {uiText.agentDiscussion.title}</span>
            <small>{uiText.agentDiscussion.description}</small>
          </div>
          <StatusDot
            label={llmConfigured ? uiText.agentDiscussion.llmConfigured : uiText.agentDiscussion.llmNotConfigured}
            tone={llmConfigured ? "good" : "danger"}
          />
        </div>
        <div className="agent-mode-row">
          <label>
            <span>{uiText.agentDiscussion.mode}</span>
            <select
              value={form.mode}
              onChange={(event) =>
                onFormChange((current) => ({
                  ...current,
                  mode: event.target.value as AgentDiscussionMode
                }))
              }
            >
              <option value="discuss">{uiText.agentDiscussion.modes.discuss}</option>
              <option value="revise_selection">{uiText.agentDiscussion.modes.revise_selection}</option>
              <option value="revise_scene">{uiText.agentDiscussion.modes.revise_scene}</option>
            </select>
          </label>
          <button type="button" onClick={onUseDraftSelection} disabled={!draftSelection || busy !== null}>
            <MessageSquare size={14} /> {uiText.agentDiscussion.useDraftSelection}
          </button>
        </div>
        <label className="agent-field">
          <span>{uiText.agentDiscussion.instructionLabel}</span>
          <textarea
            value={form.instruction}
            onChange={(event) =>
              onFormChange((current) => ({ ...current, instruction: event.target.value }))
            }
            placeholder={uiText.agentDiscussion.instructionPlaceholder}
          />
        </label>
        <label className="agent-field selection">
          <span>{uiText.agentDiscussion.selectionLabel}</span>
          <textarea
            disabled={!form.includeLatestDraft}
            value={form.selectedText}
            onChange={(event) =>
              onFormChange((current) => ({ ...current, selectedText: event.target.value }))
            }
            placeholder={uiText.agentDiscussion.selectionPlaceholder}
          />
        </label>
        <div className="agent-actions">
          <button type="button" className="primary" onClick={onSubmit} disabled={!canSubmit}>
            <Wand2 size={15} /> {uiText.agentDiscussion.submit}
          </button>
          <button type="button" onClick={onOpenProposal} disabled={!selectedProposal}>
            <SplitSquareVertical size={14} /> {uiText.agentDiscussion.openProposal}
          </button>
        </div>
      </div>
      <div className="agent-context">
        <div className="agent-options">
          <label>
            <input
              checked={crossLanguagePolicy === "explicit_reference"}
              onChange={(event) =>
                onPolicyChange(event.target.checked ? "explicit_reference" : "project_only")
              }
              type="checkbox"
            />
            {uiText.language.explicitReference}
          </label>
          <small className="agent-language-policy">
            {crossLanguagePolicy === "explicit_reference"
              ? uiText.language.explicitReferenceHelp
              : uiText.language.projectOnly}
          </small>
          <label>
            <input
              type="checkbox"
              checked={form.includeContextPack}
              onChange={(event) =>
                onFormChange((current) => ({
                  ...current,
                  includeContextPack: event.target.checked
                }))
              }
            />
            {uiText.agentDiscussion.includeContextPack}
          </label>
          <label>
            <input
              type="checkbox"
              checked={form.includeLatestDraft}
              onChange={(event) =>
                onFormChange((current) => ({
                  ...current,
                  includeLatestDraft: event.target.checked,
                  mode: event.target.checked ? current.mode : "discuss",
                  selectedText: event.target.checked ? current.selectedText : ""
                }))
              }
            />
            {uiText.agentDiscussion.includeLatestDraft}
          </label>
          <label>
            <input
              type="checkbox"
              checked={form.allowWebSearch}
              onChange={(event) =>
                onFormChange((current) => ({
                  ...current,
                  allowWebSearch: event.target.checked
                }))
              }
            />
            <Search size={13} /> {uiText.agentDiscussion.allowWebSearch}
          </label>
          <input
            value={form.webSearchQuery}
            onChange={(event) =>
              onFormChange((current) => ({ ...current, webSearchQuery: event.target.value }))
            }
            placeholder={uiText.agentDiscussion.webSearchPlaceholder}
            disabled={!form.allowWebSearch}
          />
        </div>
        {draftRequired && !form.includeLatestDraft && (
          <div className="agent-context-note warning">
            <AlertTriangle size={14} />
            <span>{uiText.agentDiscussion.revisionNeedsDraft}</span>
          </div>
        )}
        <div className="agent-source-picker">
          <div className="agent-source-head">
            <div>
              <strong>{uiText.agentDiscussion.sourcePickerTitle}</strong>
              <span>{uiText.agentDiscussion.sourcePickerCount(selectedSourceIds.size)}</span>
            </div>
            <small>{uiText.agentDiscussion.sourcePickerDefault}</small>
          </div>
          {sources.length ? (
            <div className="agent-source-list" aria-label={uiText.agentDiscussion.sourcePickerAria}>
              {sources.map((source) => {
                const ready = source.extraction_status === "ready";
                const languageKnown = source.language !== "und";
                const languageAllowed =
                  projectLanguage !== null &&
                  (source.language === projectLanguage ||
                    crossLanguagePolicy === "explicit_reference");
                const selectable = ready && languageKnown && languageAllowed;
                const languageTitle = !languageKnown
                  ? uiText.language.sourceUnknownDisabled
                  : !languageAllowed
                    ? uiText.language.sourceMismatchDisabled
                    : undefined;
                return (
                  <label className={!selectable ? "disabled" : ""} key={source.id} title={languageTitle}>
                    <input
                      checked={selectedSourceIds.has(source.id)}
                      disabled={!selectable || busy !== null}
                      onChange={() => onToggleSource(source.id)}
                      type="checkbox"
                    />
                    <span>
                      <strong>{source.title}</strong>
                      <small>
                        {source.relative_path} · {formatSourceLanguage(source.language)} · {formatStatus(source.extraction_status)} · {source.id}
                      </small>
                    </span>
                  </label>
                );
              })}
            </div>
          ) : (
            <p className="agent-source-empty">{uiText.agentDiscussion.sourcePickerEmpty}</p>
          )}
          <small className="agent-source-safety">{uiText.agentDiscussion.sourcePickerSafety}</small>
        </div>
        {!hasScene && (
          <EmptyState
            icon={<MessageSquare />}
            title={uiText.agentDiscussion.noSceneTitle}
            text={uiText.agentDiscussion.noSceneText}
          />
        )}
        {result && (
          <div className="agent-result">
            <MetricRow label={uiText.agentDiscussion.proposalMetric} value={`${result.proposal.title} / v${result.proposal.version}`} />
            <MetricRow
              label={uiText.agentDiscussion.replacementMetric}
              value={result.replacement_applied ? uiText.agentDiscussion.fullSceneDraft : uiText.agentDiscussion.discussionOnly}
            />
            <p>{result.reply}</p>
            {result.truncated_sources.length > 0 && (
              <ListBlock title={uiText.agentDiscussion.truncatedSources} items={result.truncated_sources} tone="warning" />
            )}
            {result.web_results.length > 0 && (
              <ListBlock
                title={uiText.agentDiscussion.webResults}
                items={result.web_results.map((item) => `${item.title}: ${item.snippet}`)}
              />
            )}
          </div>
        )}
      </div>
    </section>
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
    <section className="proposal-panel" aria-label={uiText.proposals.ariaLabel}>
      <div className="proposal-header">
        <div>
          <span><SplitSquareVertical size={15} /> {uiText.proposals.title}</span>
          <small>{proposals.length} {uiText.proposals.countSuffix}</small>
        </div>
        <div className="proposal-header-actions">
          <select
            value={filter}
            onChange={(event) => onFilterChange(event.target.value as ProposalStatus | "all")}
            aria-label={uiText.proposals.filterAria}
          >
            <option value="all">{uiText.common.all}</option>
            {proposalStatuses.map((status) => (
              <option key={status} value={status}>{proposalStatusLabels[status]}</option>
            ))}
          </select>
          <button type="button" onClick={onCreateNew} disabled={busy !== null}>
            <FileText size={14} /> {uiText.common.newItem}
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
              title={uiText.proposals.emptyTitle}
              text={uiText.proposals.emptyText}
            />
          )}
        </div>
        <div className="proposal-editor">
          <div className="proposal-fields">
            <select
              value={proposalType}
              disabled={Boolean(selectedProposal)}
              onChange={(event) => onTypeChange(event.target.value as ProposalArtifactType)}
              aria-label={uiText.proposals.typeAria}
            >
              {proposalTypes.map((type) => (
                <option key={type} value={type}>{proposalTypeLabels[type]}</option>
              ))}
            </select>
            <input
              value={proposalTitle}
              onChange={(event) => onTitleChange(event.target.value)}
              placeholder={uiText.proposals.titlePlaceholder}
              aria-label={uiText.proposals.titleAria}
              disabled={locked}
            />
          </div>
          <textarea
            className="proposal-textarea"
            value={proposalText}
            onChange={(event) => onTextChange(event.target.value)}
            spellCheck={false}
            aria-label={uiText.proposals.bodyAria}
            disabled={locked}
          />
          <div className="proposal-actions">
            <button type="button" onClick={onSave} disabled={!canSave}>
              <Save size={14} /> {uiText.proposals.save}
            </button>
            <button type="button" onClick={onRequestAgent} disabled={!canGenerate || busy !== null || !hasScene}>
              <Wand2 size={14} /> {uiText.proposals.requestAgent}
            </button>
            <button type="button" onClick={onExtractFactDraft} disabled={!canGenerate || busy !== null || !hasScene}>
              <ShieldCheck size={14} /> {uiText.proposals.extractFactDraft}
            </button>
            <button type="button" onClick={onSubmitReview} disabled={!canSubmit}>
              <Clock3 size={14} /> {uiText.proposals.submitReview}
            </button>
            <button type="button" onClick={onAccept} disabled={!canDecide}>
              <Check size={14} /> {uiText.proposals.accept}
            </button>
            <button type="button" onClick={onReject} disabled={!canDecide}>
              <X size={14} /> {uiText.proposals.reject}
            </button>
            <button type="button" onClick={onPromoteDraft} disabled={!canPromoteDraft}>
              <FileText size={14} /> {uiText.proposals.promoteDraft}
            </button>
            <button type="button" onClick={onApplyProjectStructure} disabled={!canApplyProjectStructure}>
              <BookOpen size={14} /> {uiText.proposals.applyStructure}
            </button>
          </div>
        </div>
        <div className="proposal-meta">
          <MetricRow label={uiText.proposals.metadataStatus} value={selectedProposal ? proposalStatusLabels[selectedProposal.status] : uiText.proposals.unselected} />
          <MetricRow label={uiText.proposals.metadataType} value={proposalTypeLabels[proposalType]} />
          <MetricRow label={uiText.proposals.metadataVersion} value={selectedProposal ? `v${selectedProposal.version}` : uiText.proposals.newVersion} />
          <MetricRow
            label={uiText.language.artifactLanguageLabel}
            value={
              selectedProposal
                ? formatArtifactLanguage(selectedProposal.content_language, selectedProposal.language_inferred)
                : uiText.common.none
            }
          />
          <MetricRow label={uiText.proposals.metadataCreatedVia} value={formatProvenanceMethod(selectedProposal?.provenance.created_via)} />
          <label>
            <span>{uiText.proposals.sourceDraft}</span>
            <input
              value={effectiveSourceDraftId}
              onChange={(event) => onSourceDraftChange(event.target.value)}
              placeholder={uiText.proposals.sourceDraftPlaceholder}
            />
          </label>
          <div className="proposal-side-actions">
            <button type="button" onClick={onExtractCandidates} disabled={!canPromoteCandidates}>
              <ShieldCheck size={14} /> {uiText.proposals.extractCandidates}
            </button>
            <button type="button" onClick={onOpenCanonReview} disabled={busy !== null}>
              <ShieldCheck size={14} /> {uiText.proposals.openCanonReview}
            </button>
          </div>
          <ListBlock
            title={uiText.proposals.refsSource}
            items={formatProposalRefs(selectedProposal?.source_refs ?? [])}
          />
          <ListBlock
            title={uiText.proposals.refsTarget}
            items={formatProposalRefs(selectedProposal?.target_refs ?? [])}
          />
          <ListBlock
            title={uiText.proposals.refsDerived}
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
  onUpdateChapter,
  onUpdateScene,
  onWorldRuleFormChange,
  projectForm,
  projectId,
  projects,
  sceneForm,
  sceneId,
  selectedChapter,
  selectedProject,
  selectedScene,
  storyCharacters,
  storyLocations,
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
  onUpdateChapter: () => void;
  onUpdateScene: () => void;
  onWorldRuleFormChange: React.Dispatch<React.SetStateAction<WorldRuleForm>>;
  projectForm: ProjectForm;
  projectId: string;
  projects: ProjectOutline[];
  sceneForm: SceneForm;
  sceneId: string;
  selectedChapter: ChapterOutline | null;
  selectedProject: ProjectOutline | null;
  selectedScene: SceneOutline | null;
  storyCharacters: GraphNodePayload[];
  storyLocations: GraphNodePayload[];
  workspaceLoaded: boolean;
  worldRuleForm: WorldRuleForm;
}) {
  const chapters = selectedProject?.chapters ?? [];
  const sceneChapterId = sceneForm.chapter_id || currentChapterId;
  const selectedBuiltinDemo = selectedProject?.id === "project_fantasy_demo";
  const [projectPanelMode, setProjectPanelMode] = useState<"view" | "create" | "edit">("view");
  const projectScenes = selectedProject ? flattenScenes(selectedProject) : [];
  const projectSceneCount = projectScenes.length;
  const importedPovLabel = stringProperty(selectedScene?.properties, "pov_label");
  const importedLocationLabel = stringProperty(selectedScene?.properties, "location_label");
  const matchedImportedPovCharacter = findGraphNodeByLabel(storyCharacters, importedPovLabel);
  const matchedImportedLocation = findGraphNodeByLabel(storyLocations, importedLocationLabel);

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

  const loadSelectedScene = () => {
    if (!selectedScene) return;
    onSceneFormChange(sceneToForm(selectedScene, currentChapterId));
  };

  const loadSelectedChapter = () => {
    if (!selectedChapter) return;
    onChapterFormChange(chapterToForm(selectedChapter));
  };

  const fillCharacterFromImportedHint = () => {
    if (!importedPovLabel) return;
    onCharacterFormChange((current) => ({
      ...current,
      name: importedPovLabel
    }));
  };

  const fillLocationFromImportedHint = () => {
    if (!importedLocationLabel) return;
    onLocationFormChange((current) => ({
      ...current,
      name: importedLocationLabel
    }));
  };

  const useExistingPovCharacter = () => {
    if (!matchedImportedPovCharacter) return;
    onSceneFormChange((current) => ({
      ...current,
      pov_character_id: matchedImportedPovCharacter.id,
      required_characters: appendLineIfMissing(
        current.required_characters,
        matchedImportedPovCharacter.id
      )
    }));
  };

  const useExistingLocation = () => {
    if (!matchedImportedLocation) return;
    onSceneFormChange((current) => ({
      ...current,
      location_id: matchedImportedLocation.id
    }));
  };

  return (
    <>
      <div className="sidebar-scroll">
        <details className="sidebar-section workspace-section" open>
          <summary className="section-title">{uiText.sidebar.workspaceTitle}</summary>
          {workspaceLoaded && hasWorkspace ? (
            <>
              <select
                className="sidebar-select"
                disabled={busy !== null}
                value={projectId}
                onChange={(event) => onSelectProject(event.target.value)}
              >
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.title}
                  </option>
                ))}
              </select>
              <div className="project-id">{projectId}</div>
              {selectedProject && (
                <div className="project-card">
                  <strong>{selectedProject.title}</strong>
                  <span>
                    {selectedProject.genre ?? uiText.sidebar.uncategorized} / {formatProjectLanguage(selectedProject)}
                  </span>
                  <span>
                    {chapters.length} {uiText.sidebar.chapterCount} / {projectSceneCount} {uiText.sidebar.sceneCount}
                  </span>
                  <span>{String(selectedProject.properties.narrative_pov ?? uiText.sidebar.povUnset)}</span>
                </div>
              )}
            </>
          ) : (
            <div className="project-empty">
              {workspaceLoaded ? uiText.sidebar.projectEmpty : uiText.sidebar.projectLoading}
            </div>
          )}
          <div className="sidebar-button-row">
            <button
              disabled={busy !== null}
              onClick={onRefresh}
              title={uiText.sidebar.refreshTitle}
              type="button"
            >
              <RefreshCw size={15} /> {uiText.common.refresh}
            </button>
            <button
              disabled={!canReview || busy !== null}
              onClick={startProjectCreate}
              title={canReview ? uiText.sidebar.createProjectTitle : uiText.sidebar.requireFullPermission}
              type="button"
            >
              <Database size={15} /> {uiText.sidebar.createProject}
            </button>
            <button
              disabled={!canReview || !selectedProject || busy !== null}
              onClick={startProjectEdit}
              title={canReview ? uiText.sidebar.editProjectTitle : uiText.sidebar.requireFullPermission}
              type="button"
            >
              <Settings size={15} /> {uiText.sidebar.editProject}
            </button>
            {selectedBuiltinDemo && (
              <button
                disabled={!canReview || busy !== null}
                onClick={onArchiveDemo}
                title={canReview ? uiText.sidebar.archiveDemoTitle : uiText.sidebar.requireFullPermission}
                type="button"
              >
                <X size={15} /> {uiText.sidebar.archiveDemo}
              </button>
            )}
          </div>

        <nav className="scene-tree" aria-label={uiText.sidebar.projectTreeAria}>
          {selectedProject ? (
            selectedProject.chapters.map((chapter) => (
              <div key={chapter.id} className="chapter">
                <div className="chapter-row">
                  <BookOpen size={15} />
                  <span>{chapter.title}</span>
                  <small>{formatStatus(chapter.status ?? "planned")}</small>
                </div>
                {chapter.scenes.length ? (
                  chapter.scenes.map((scene) => (
                    <button
                      key={scene.id}
                      className={`scene-row ${scene.id === sceneId ? "selected" : ""}`}
                      disabled={busy !== null}
                      onClick={() => onSelectScene(scene.id)}
                      type="button"
                    >
                      <ChevronRight size={14} />
                      <span>{scene.title}</span>
                      <small>{formatStatus(scene.status ?? "planned")}</small>
                    </button>
                  ))
                ) : (
                  <p className="tree-empty">{uiText.sidebar.noChapterScenes}</p>
                )}
              </div>
            ))
          ) : (
            <EmptyState
              icon={<BookOpen />}
              title={uiText.sidebar.noProjectTreeTitle}
              text={uiText.sidebar.noProjectTreeText}
            />
          )}
        </nav>
        </details>

        {projectPanelMode !== "view" && (
          <details className="sidebar-section seed-panel" open>
            <summary className="section-title">
              {projectPanelMode === "edit" ? uiText.sidebar.editProjectTitleText : uiText.sidebar.createProjectTitleText}
            </summary>
            <input
              placeholder={uiText.sidebar.projectNamePlaceholder}
              value={projectForm.title}
              onChange={(event) =>
                onProjectFormChange((current) => ({ ...current, title: event.target.value }))
              }
            />
            <div className="compact-grid">
              <input
                placeholder={uiText.sidebar.genrePlaceholder}
                value={projectForm.genre}
                onChange={(event) =>
                  onProjectFormChange((current) => ({ ...current, genre: event.target.value }))
                }
              />
              <select
                aria-label={uiText.language.projectLanguageLabel}
                value={
                  projectForm.language === "zh-CN" || projectForm.language === "en-US"
                    ? projectForm.language
                    : ""
                }
                onChange={(event) => {
                  const language = normalizeAppLocale(event.target.value);
                  onProjectFormChange((current) => ({ ...current, language }));
                }}
              >
                {projectForm.language !== "zh-CN" && projectForm.language !== "en-US" && (
                  <option value="" disabled>{uiText.language.projectLanguageNeedsReview}</option>
                )}
                <option value="zh-CN">{uiText.language.chinese}</option>
                <option value="en-US">{uiText.language.english}</option>
              </select>
            </div>
            <small className="field-help">{uiText.language.projectLanguageHelp}</small>
            <input
              placeholder={uiText.sidebar.targetLengthPlaceholder}
              value={projectForm.target_length}
              onChange={(event) =>
                onProjectFormChange((current) => ({
                  ...current,
                  target_length: event.target.value
                }))
              }
            />
            <input
              placeholder={uiText.sidebar.narrativePovPlaceholder}
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
                <Save size={15} /> {projectPanelMode === "edit" ? uiText.sidebar.saveProjectInfo : uiText.sidebar.createProjectButton}
              </button>
              {hasWorkspace && (
                <button
                  className="sidebar-action"
                  disabled={busy !== null}
                  onClick={() => setProjectPanelMode("view")}
                  type="button"
                >
                  <X size={15} /> {uiText.common.cancel}
                </button>
              )}
            </div>
          </details>
        )}

        <details className="sidebar-section seed-panel" open>
          <summary className="section-title">{uiText.sidebar.outlineTitle}</summary>
          <input
            placeholder={uiText.sidebar.chapterTitlePlaceholder}
            value={chapterForm.title}
            onChange={(event) =>
              onChapterFormChange((current) => ({ ...current, title: event.target.value }))
            }
          />
          <div className="compact-grid">
            <input
              placeholder={uiText.sidebar.volumeIndexPlaceholder}
              value={chapterForm.volume_index}
              onChange={(event) =>
                onChapterFormChange((current) => ({
                  ...current,
                  volume_index: event.target.value
                }))
              }
            />
            <input
              placeholder={uiText.sidebar.chapterIndexPlaceholder}
              value={chapterForm.chapter_index}
              onChange={(event) =>
                onChapterFormChange((current) => ({
                  ...current,
                  chapter_index: event.target.value
                }))
              }
            />
          </div>
          <div className="compact-grid">
            <select
              value={chapterForm.status}
              onChange={(event) =>
                onChapterFormChange((current) => ({
                  ...current,
                  status: event.target.value
                }))
              }
              aria-label={uiText.sidebar.chapterStatusAria}
            >
              {chapterStatusOptions.map((status) => (
                <option key={status} value={status}>{formatStatus(status)}</option>
              ))}
            </select>
            <button
              disabled={!canReview || !projectId || busy !== null}
              onClick={onCreateChapter}
              type="button"
            >
              <Save size={15} /> {uiText.sidebar.addChapter}
            </button>
          </div>
          <input
            placeholder={uiText.sidebar.chapterPurposePlaceholder}
            value={chapterForm.purpose}
            onChange={(event) =>
              onChapterFormChange((current) => ({ ...current, purpose: event.target.value }))
            }
          />
          <input
            placeholder={uiText.sidebar.chapterSummaryPlaceholder}
            value={chapterForm.summary}
            onChange={(event) =>
              onChapterFormChange((current) => ({ ...current, summary: event.target.value }))
            }
          />
          <div className="compact-grid">
            <button
              disabled={!selectedChapter || busy !== null}
              onClick={loadSelectedChapter}
              type="button"
              title={uiText.sidebar.loadChapterTitle}
            >
              <BookOpen size={15} /> {uiText.sidebar.loadChapter}
            </button>
            <button
              disabled={!canReview || !selectedChapter || busy !== null}
              onClick={onUpdateChapter}
              type="button"
              title={canReview ? uiText.sidebar.saveChapterMetadataTitle : uiText.sidebar.requireFullPermission}
            >
              <Save size={15} /> {uiText.sidebar.saveChapterMetadata}
            </button>
          </div>
          <select
            value={sceneChapterId}
            onChange={(event) =>
              onSceneFormChange((current) => ({ ...current, chapter_id: event.target.value }))
            }
          >
            <option value="">{uiText.sidebar.chooseChapter}</option>
            {chapters.map((chapter) => (
              <option key={chapter.id} value={chapter.id}>
                {chapter.title}
              </option>
            ))}
          </select>
          <input
            placeholder={uiText.sidebar.sceneTitlePlaceholder}
            value={sceneForm.title}
            onChange={(event) =>
              onSceneFormChange((current) => ({ ...current, title: event.target.value }))
            }
          />
          <div className="compact-grid">
            <input
              placeholder={uiText.sidebar.sceneIndexPlaceholder}
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
              <Save size={15} /> {uiText.sidebar.addScene}
            </button>
          </div>
          <div className="compact-grid">
            <button
              disabled={!selectedScene || busy !== null}
              onClick={loadSelectedScene}
              type="button"
              title={uiText.sidebar.loadSceneTitle}
            >
              <FileText size={15} /> {uiText.sidebar.loadScene}
            </button>
            <button
              disabled={!canReview || !selectedScene || busy !== null}
              onClick={onUpdateScene}
              type="button"
              title={canReview ? uiText.sidebar.saveSceneMetadataTitle : uiText.sidebar.requireFullPermission}
            >
              <Save size={15} /> {uiText.sidebar.saveSceneMetadata}
            </button>
          </div>
          {(importedPovLabel || importedLocationLabel) && (
            <div className="scene-hints">
              {importedPovLabel && (
                <div className="scene-hint-row">
                  <span className="scene-hint-label">
                    {uiText.sidebar.importedPovLabel}: {importedPovLabel}
                    {matchedImportedPovCharacter && (
                      <small>{uiText.sidebar.matchedPrefix} {matchedImportedPovCharacter.id}</small>
                    )}
                  </span>
                  <div className="scene-hint-actions">
                    {matchedImportedPovCharacter && (
                      <button
                        disabled={busy !== null}
                        onClick={useExistingPovCharacter}
                        title={uiText.sidebar.useExistingTitle}
                        type="button"
                      >
                        <Check size={13} /> {uiText.sidebar.useExisting}
                      </button>
                    )}
                    <button
                      disabled={busy !== null}
                      onClick={fillCharacterFromImportedHint}
                      title={uiText.sidebar.fillCharacterTitle}
                      type="button"
                    >
                      <UserRound size={13} /> {uiText.sidebar.fillCharacter}
                    </button>
                  </div>
                </div>
              )}
              {importedLocationLabel && (
                <div className="scene-hint-row">
                  <span className="scene-hint-label">
                    {uiText.sidebar.importedLocationLabel}: {importedLocationLabel}
                    {matchedImportedLocation && <small>{uiText.sidebar.matchedPrefix} {matchedImportedLocation.id}</small>}
                  </span>
                  <div className="scene-hint-actions">
                    {matchedImportedLocation && (
                      <button
                        disabled={busy !== null}
                        onClick={useExistingLocation}
                        title={uiText.sidebar.useExistingTitle}
                        type="button"
                      >
                        <Check size={13} /> {uiText.sidebar.useExisting}
                      </button>
                    )}
                    <button
                      disabled={busy !== null}
                      onClick={fillLocationFromImportedHint}
                      title={uiText.sidebar.fillLocationTitle}
                      type="button"
                    >
                      <MapPin size={13} /> {uiText.sidebar.fillLocation}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
          <datalist id="story-character-options">
            {storyCharacters.map((node) => (
              <option key={node.id} value={node.id} label={graphNodeOptionLabel(node)} />
            ))}
          </datalist>
          <datalist id="story-location-options">
            {storyLocations.map((node) => (
              <option key={node.id} value={node.id} label={graphNodeOptionLabel(node)} />
            ))}
          </datalist>
          <datalist id="project-scene-options">
            {projectScenes
              .filter((scene) => scene.id !== selectedScene?.id)
              .map((scene) => (
                <option key={scene.id} value={scene.id} label={scene.title} />
              ))}
          </datalist>
          <div className="compact-grid">
            <select
              value={sceneForm.status}
              onChange={(event) =>
                onSceneFormChange((current) => ({
                  ...current,
                  status: event.target.value
                }))
              }
              aria-label={uiText.sidebar.sceneStatusAria}
            >
              {sceneStatusOptions.map((status) => (
                <option key={status} value={status}>
                  {formatStatus(status)}
                </option>
              ))}
            </select>
            <input
              list="project-scene-options"
              placeholder={uiText.sidebar.previousScenePlaceholder}
              value={sceneForm.previous_scene_id}
              onChange={(event) =>
                onSceneFormChange((current) => ({
                  ...current,
                  previous_scene_id: event.target.value
                }))
              }
            />
          </div>
          <input
            list="story-character-options"
            placeholder={uiText.sidebar.povCharacterPlaceholder}
            value={sceneForm.pov_character_id}
            onChange={(event) =>
              onSceneFormChange((current) => ({
                ...current,
                pov_character_id: event.target.value
              }))
            }
          />
          <input
            list="story-location-options"
            placeholder={uiText.sidebar.locationPlaceholder}
            value={sceneForm.location_id}
            onChange={(event) =>
              onSceneFormChange((current) => ({
                ...current,
                location_id: event.target.value
              }))
            }
          />
          <input
            placeholder={uiText.sidebar.timelinePlaceholder}
            value={sceneForm.timeline_position}
            onChange={(event) =>
              onSceneFormChange((current) => ({
                ...current,
                timeline_position: event.target.value
              }))
            }
          />
          <input
            placeholder={uiText.sidebar.sceneGoalPlaceholder}
            value={sceneForm.goal}
            onChange={(event) =>
              onSceneFormChange((current) => ({ ...current, goal: event.target.value }))
            }
          />
          <input
            placeholder={uiText.sidebar.sceneConflictPlaceholder}
            value={sceneForm.conflict}
            onChange={(event) =>
              onSceneFormChange((current) => ({ ...current, conflict: event.target.value }))
            }
          />
          <div className="compact-grid">
            <input
              placeholder={uiText.sidebar.sceneOutcomePlaceholder}
              value={sceneForm.outcome}
              onChange={(event) =>
                onSceneFormChange((current) => ({ ...current, outcome: event.target.value }))
              }
            />
            <input
              placeholder={uiText.sidebar.emotionalTurnPlaceholder}
              value={sceneForm.emotional_turn}
              onChange={(event) =>
                onSceneFormChange((current) => ({
                  ...current,
                  emotional_turn: event.target.value
                }))
              }
            />
          </div>
          <div className="compact-grid">
            <input
              placeholder={uiText.sidebar.stylePovPlaceholder}
              value={sceneForm.style_pov}
              onChange={(event) =>
                onSceneFormChange((current) => ({ ...current, style_pov: event.target.value }))
              }
            />
            <input
              placeholder={uiText.sidebar.tensePlaceholder}
              value={sceneForm.style_tense}
              onChange={(event) =>
                onSceneFormChange((current) => ({ ...current, style_tense: event.target.value }))
              }
            />
          </div>
          <div className="compact-grid">
            <input
              placeholder={uiText.sidebar.tonePlaceholder}
              value={sceneForm.style_tone}
              onChange={(event) =>
                onSceneFormChange((current) => ({ ...current, style_tone: event.target.value }))
              }
            />
            <input
              placeholder={uiText.sidebar.rhythmPlaceholder}
              value={sceneForm.style_sentence_rhythm}
              onChange={(event) =>
                onSceneFormChange((current) => ({
                  ...current,
                  style_sentence_rhythm: event.target.value
                }))
              }
            />
          </div>
          <div className="compact-grid">
            <input
              placeholder={uiText.sidebar.dictionPlaceholder}
              value={sceneForm.style_diction}
              onChange={(event) =>
                onSceneFormChange((current) => ({ ...current, style_diction: event.target.value }))
              }
            />
            <input
              placeholder={uiText.sidebar.dialogueStylePlaceholder}
              value={sceneForm.style_dialogue_style}
              onChange={(event) =>
                onSceneFormChange((current) => ({
                  ...current,
                  style_dialogue_style: event.target.value
                }))
              }
            />
          </div>
          <textarea
            className="mini-textarea"
            placeholder={uiText.sidebar.bannedPatternsPlaceholder}
            value={sceneForm.style_banned_patterns}
            onChange={(event) =>
              onSceneFormChange((current) => ({
                ...current,
                style_banned_patterns: event.target.value
              }))
            }
          />
          <textarea
            className="mini-textarea"
            placeholder={uiText.sidebar.requiredCharactersPlaceholder}
            value={sceneForm.required_characters}
            onChange={(event) =>
              onSceneFormChange((current) => ({
                ...current,
                required_characters: event.target.value
              }))
            }
          />
          <textarea
            className="mini-textarea"
            placeholder={uiText.sidebar.mustIncludePlaceholder}
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
            placeholder={uiText.sidebar.mustNotViolatePlaceholder}
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
          <summary className="section-title">{uiText.sidebar.storyBibleTitle}</summary>
          <input
            placeholder={uiText.sidebar.characterNamePlaceholder}
            value={characterForm.name}
            onChange={(event) =>
              onCharacterFormChange((current) => ({ ...current, name: event.target.value }))
            }
          />
          <div className="compact-grid">
            <input
              placeholder={uiText.sidebar.characterRolePlaceholder}
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
              <Save size={15} /> {uiText.sidebar.createCharacter}
            </button>
          </div>
          <input
            placeholder={uiText.sidebar.locationNamePlaceholder}
            value={locationForm.name}
            onChange={(event) =>
              onLocationFormChange((current) => ({ ...current, name: event.target.value }))
            }
          />
          <div className="compact-grid">
            <input
              placeholder={uiText.sidebar.locationTypePlaceholder}
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
              <Save size={15} /> {uiText.sidebar.createLocation}
            </button>
          </div>
          <input
            placeholder={uiText.sidebar.ruleDomainPlaceholder}
            value={worldRuleForm.domain}
            onChange={(event) =>
              onWorldRuleFormChange((current) => ({ ...current, domain: event.target.value }))
            }
          />
          <input
            placeholder={uiText.sidebar.worldRulePlaceholder}
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
              <option value="low">{formatSeverity("low")}</option>
              <option value="medium">{formatSeverity("medium")}</option>
              <option value="high">{formatSeverity("high")}</option>
              <option value="critical">{formatSeverity("critical")}</option>
            </select>
            <button
              disabled={!canReview || !projectId || busy !== null}
              onClick={onCreateWorldRule}
              type="button"
            >
              <Save size={15} /> {uiText.sidebar.createRule}
            </button>
          </div>
        </details>
      </div>
      <div className="sidebar-footer">
        <ShieldCheck size={16} />
        {uiText.sidebar.footer}
      </div>
    </>
  );
}

function DirectoryInput(props: DirectoryInputProps) {
  return <input {...props} />;
}

function SourceImportStatus({ progress }: { progress: SourceImportProgress }) {
  return (
    <div
      aria-live="polite"
      className={`source-import-progress ${progress.active ? "active" : "complete"}`}
    >
      <div>
        {progress.active ? <RefreshCw className="spin" size={15} /> : <Check size={15} />}
        <strong>
          {progress.active
            ? uiText.library.importProgress(progress.current, progress.total)
            : uiText.library.importComplete}
        </strong>
        {progress.currentName && <span title={progress.currentName}>{progress.currentName}</span>}
      </div>
      <div className="source-import-metrics">
        <span>{uiText.library.importCreated(progress.created)}</span>
        <span>{uiText.library.importUpdated(progress.updated)}</span>
        <span>{uiText.library.importUnchanged(progress.unchanged)}</span>
        <span>{uiText.library.importFailed(progress.failed)}</span>
        <span>{uiText.library.importSkipped(progress.skipped)}</span>
      </div>
      {progress.issues.length > 0 && (
        <div className="source-import-issues">
          {progress.issues.map((issue, index) => (
            <span key={`${issue.name}:${index}`}>
              <AlertTriangle size={13} /> {issue.name}: {issue.message}
              {issue.technicalDetails && (
                <details>
                  <summary>{uiText.errors.technicalDetails}</summary>
                  <code>{issue.technicalDetails}</code>
                </details>
              )}
            </span>
          ))}
        </div>
      )}
    </div>
  );
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
      className={`library-node document ${document.id === selectedDocumentId ? "selected" : ""} ${document.extraction_status}`}
      onClick={() => onSelectDocument(document.id)}
      style={indent}
      title={`${document.relative_path} · ${document.id}`}
      type="button"
    >
      {document.media_type.includes("wordprocessingml") ? <FileText size={15} /> : <FileIcon size={15} />}
      <span>{document.title}</span>
      <small>
        {document.extraction_status === "ready"
          ? sourceMediaTypeLabel(document.media_type)
          : formatStatus(document.extraction_status)}
      </small>
    </button>
  );
}

function DocumentReader({
  busy,
  canGenerate,
  crossLanguagePolicy,
  document: doc,
  hasProject,
  hasScene,
  loading,
  onAnalyzeStructure,
  onArchive,
  onPolicyChange,
  onRetry,
  onSaveDraft,
  onSaveProposal,
  onSaveStyle,
  onUpdateLanguage,
  projectLanguage,
  summary
}: {
  busy: string | null;
  canGenerate: boolean;
  crossLanguagePolicy: CrossLanguagePolicy;
  document: SourceDocument | null;
  hasProject: boolean;
  hasScene: boolean;
  loading: boolean;
  onAnalyzeStructure: (document: SourceDocumentSummary) => void;
  onArchive: (document: SourceDocumentSummary) => void;
  onPolicyChange: (policy: CrossLanguagePolicy) => void;
  onRetry: (document: SourceDocumentSummary, file: File) => void;
  onSaveDraft: (document: SourceDocument) => void;
  onSaveProposal: (document: SourceDocument) => void;
  onSaveStyle: (document: SourceDocument) => void;
  onUpdateLanguage: (document: SourceDocumentSummary, language: "zh-CN" | "en-US") => void;
  projectLanguage: AppLocale | null;
  summary: SourceDocumentSummary | null;
}) {
  const [languageDraft, setLanguageDraft] = useState<"zh-CN" | "en-US">("zh-CN");
  useEffect(() => {
    if (summary?.language === "zh-CN" || summary?.language === "en-US") {
      setLanguageDraft(summary.language);
    } else {
      setLanguageDraft(projectLanguage ?? "zh-CN");
    }
  }, [projectLanguage, summary?.id, summary?.language]);
  if (!summary) {
    return (
      <div className="document-reader empty">
        <EmptyState
          icon={<Library />}
          title={uiText.library.readerEmptyTitle}
          text={uiText.library.readerEmptyText}
        />
      </div>
    );
  }

  if (loading || !doc || doc.id !== summary.id) {
    return (
      <div className="document-reader empty">
        <EmptyState
          icon={<RefreshCw className={loading ? "spin" : undefined} />}
          title={loading ? uiText.library.readerLoadingTitle : uiText.library.readerLoadFailedTitle}
          text={loading ? uiText.library.readerLoadingText : uiText.library.readerLoadFailedText}
        />
      </div>
    );
  }

  const ready = doc.extraction_status === "ready";
  const sameLanguage = doc.language === projectLanguage;
  const canManageSource = canGenerate && hasProject && busy === null;
  const canSceneBridge = ready && sameLanguage && canGenerate && hasScene && busy === null;
  const canProjectBridge = ready && sameLanguage && canGenerate && hasProject && busy === null;
  const canAnalyzeStructure =
    ready && canManageSource &&
    projectLanguage !== null &&
    doc.language !== "und" &&
    (doc.language === projectLanguage || crossLanguagePolicy === "explicit_reference");
  const canArchive = hasProject && canGenerate && busy === null;
  const contentBridgeLanguageTitle = doc.language === "und"
    ? uiText.language.sourceUnknownDisabled
    : !sameLanguage
      ? uiText.errors.sourceContentLanguageMismatch
      : null;
  const structureLanguageTitle = doc.language === "und"
    ? uiText.language.sourceUnknownDisabled
    : !canAnalyzeStructure && doc.language !== projectLanguage
      ? uiText.language.sourceMismatchDisabled
      : null;

  return (
    <div className="document-reader">
      <div className="reader-head">
        <div>
          <strong>{doc.title}</strong>
          <span>{doc.relative_path}</span>
        </div>
        <div className="reader-tags">
          <span>{sourceMediaTypeLabel(doc.media_type)}</span>
          <span>{formatSourceLanguage(doc.language)}</span>
          <span>{formatFileSize(doc.byte_size)}</span>
          <span>{formatStatus(doc.extraction_status)}</span>
          <span title={doc.id}>{doc.id}</span>
        </div>
      </div>
      <div className="source-language-editor">
        <label>
          <span>{uiText.language.sourceLanguageLabel}</span>
          <select
            value={languageDraft}
            onChange={(event) => setLanguageDraft(normalizeAppLocale(event.target.value))}
            disabled={!canManageSource}
          >
            <option value="zh-CN">{uiText.language.chinese}</option>
            <option value="en-US">{uiText.language.english}</option>
          </select>
        </label>
        <button
          type="button"
          disabled={!canManageSource || languageDraft === doc.language}
          onClick={() => onUpdateLanguage(summary, languageDraft)}
        >
          {uiText.language.saveSourceLanguage}
        </button>
        {doc.language === "und" && (
          <small className="warning">{uiText.language.sourceUnknownDisabled}</small>
        )}
        <label className="checkbox-row source-language-policy">
          <input
            checked={crossLanguagePolicy === "explicit_reference"}
            onChange={(event) =>
              onPolicyChange(event.target.checked ? "explicit_reference" : "project_only")
            }
            type="checkbox"
          />
          <span>{uiText.language.explicitReference}</span>
        </label>
        <small>
          {crossLanguagePolicy === "explicit_reference"
            ? uiText.language.explicitReferenceHelp
            : uiText.language.projectOnly}
        </small>
      </div>
      <div className="reader-bridge">
        <span>{uiText.library.bridgeText}</span>
        <div>
          <button
            className="primary"
            disabled={!canAnalyzeStructure}
            onClick={() => onAnalyzeStructure(summary)}
            title={
              !hasProject
                ? uiText.errors.selectProjectOrCreate
                : structureLanguageTitle ?? uiText.library.buildStructureTitle
            }
            type="button"
          >
            <BookOpen size={14} /> {uiText.library.buildStructure}
          </button>
          <button
            disabled={!canSceneBridge}
            onClick={() => onSaveDraft(doc)}
            title={contentBridgeLanguageTitle ?? uiText.library.saveDraftTitle}
            type="button"
          >
            <FileText size={14} /> {uiText.library.saveDraft}
          </button>
          <button
            disabled={!canSceneBridge}
            onClick={() => onSaveProposal(doc)}
            title={contentBridgeLanguageTitle ?? uiText.library.saveProposalTitle}
            type="button"
          >
            <SplitSquareVertical size={14} /> {uiText.library.saveProposal}
          </button>
          <button
            disabled={!canProjectBridge}
            onClick={() => onSaveStyle(doc)}
            title={contentBridgeLanguageTitle ?? uiText.library.saveStyleTitle}
            type="button"
          >
            <Wand2 size={14} /> {uiText.library.saveStyle}
          </button>
          {doc.extraction_status === "failed" && (
            <label
              className={`import-button reader-retry ${!canArchive ? "disabled" : ""}`}
              title={uiText.library.retryTitle}
            >
              <RefreshCw size={14} /> {uiText.library.retry}
              <input
                accept={sourceFileAccept(doc.media_type)}
                disabled={!canArchive}
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0];
                  event.currentTarget.value = "";
                  if (file) onRetry(summary, file);
                }}
                type="file"
              />
            </label>
          )}
          <button
            className="archive"
            disabled={!canArchive}
            onClick={() => {
              if (window.confirm(uiText.library.archiveConfirm(doc.title))) onArchive(summary);
            }}
            title={uiText.library.archiveTitle}
            type="button"
          >
            <X size={14} /> {uiText.library.archive}
          </button>
        </div>
      </div>
      {doc.extraction_status === "failed" ? (
        <div className="reader-error">
          <AlertTriangle size={17} />
          <strong>{uiText.library.readErrorTitle}</strong>
          <span>{uiText.library.unknownReadError}</span>
          {doc.error && (
            <details>
              <summary>{uiText.errors.technicalDetails}</summary>
              <code>{doc.error}</code>
            </details>
          )}
        </div>
      ) : (
        <div className="reader-content">
          {doc.warnings.length > 0 && (
            <div className="reader-warning">
              <AlertTriangle size={15} />
              <span>{uiText.library.sourceWarningTitle}</span>
              <details>
                <summary>{uiText.errors.technicalDetails}</summary>
                <code>{doc.warnings.slice(0, 2).join("\n")}</code>
              </details>
            </div>
          )}
          <pre>{doc.extracted_text}</pre>
        </div>
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
  locale,
  onApiKeyChange,
  onBackendRefresh,
  onBackendStart,
  onBackendStop,
  onClearApiKeyChange,
  onFormChange,
  onLocaleChange,
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
  locale: AppLocale;
  onApiKeyChange: (value: string) => void;
  onBackendRefresh: () => void;
  onBackendStart: () => void;
  onBackendStop: () => void;
  onClearApiKeyChange: (value: boolean) => void;
  onFormChange: React.Dispatch<React.SetStateAction<AgentSettingsUpdate>>;
  onLocaleChange: (locale: AppLocale) => void;
  onRefresh: () => void;
  onSave: () => void;
  onInstallUpdate: () => void;
  onUpdateCheck: () => void;
  settings: AgentSettings | null;
  updateStatus: UpdateStatus;
}) {
  const descriptions = settings?.permission_descriptions ?? defaultPermissionDescriptions;
  const apiKeyStatus = settings?.api_key_configured
    ? `${uiText.settings.configuredKey} (${settings.api_key_preview ?? uiText.settings.hiddenKey})`
    : uiText.common.notConfigured;
  const updateTarget = updateStatus.installerUrl ?? updateStatus.releaseUrl;

  return (
    <div className="settings-panel">
      <section className="settings-block">
        <div className="settings-title"><BookOpen size={15} /> {uiText.language.uiLocaleLabel}</div>
        <label>
          <span>{uiText.language.uiLocaleLabel}</span>
          <select
            aria-label={uiText.language.uiLocaleLabel}
            disabled={busy !== null}
            value={locale}
            onChange={(event) => onLocaleChange(normalizeAppLocale(event.target.value))}
          >
            <option value="zh-CN">{uiText.language.chinese}</option>
            <option value="en-US">{uiText.language.english}</option>
          </select>
        </label>
      </section>
      {isDesktopRuntime() && (
        <section className="settings-block">
          <div className="settings-title"><Database size={15} /> {uiText.settings.desktopBackend}</div>
          <MetricRow label={uiText.settings.apiAddress} value={desktopSettings?.backendUrl ?? uiText.common.loading} />
          <MetricRow label={uiText.settings.configuredWorkspace} value={desktopSettings?.workspacePath ?? uiText.common.loading} />
          <MetricRow label={uiText.settings.backendStatus} value={formatDesktopBackendDetail(desktopBackend)} />
          <MetricRow
            label={uiText.settings.healthWorkspace}
            value={desktopBackend?.healthWorkspacePath ?? (desktopBackend?.reachable ? uiText.settings.notReturned : uiText.settings.notConnected)}
          />
          <MetricRow
            label={uiText.settings.process}
            value={
              desktopBackend?.pid
                ? `${desktopBackend.managed ? uiText.settings.managedProcess : uiText.settings.externalProcess} PID ${desktopBackend.pid}`
                : desktopBackend?.reachable
                  ? uiText.settings.externalOrUnknownProcess
                  : uiText.settings.notRunning
            }
          />
          {desktopBackend?.error && (
            <div className={`desktop-backend-card ${desktopBackend.workspaceCompatible ? "warning" : "danger"}`}>
              <AlertTriangle size={15} />
              <span>{uiText.runtime.backendWorkspaceConflict}</span>
              <details>
                <summary>{uiText.errors.technicalDetails}</summary>
                <code>{desktopBackend.error}</code>
              </details>
            </div>
          )}
          {desktopBackend?.reachable && !desktopBackend.managed && desktopBackend.workspaceCompatible && (
            <div className="desktop-backend-card warning">
              <AlertTriangle size={15} />
              <span>{uiText.settings.externalBackendWarning}</span>
            </div>
          )}
          <div className="settings-actions compact">
            <button onClick={onBackendRefresh} type="button" disabled={busy !== null}>
              <RefreshCw size={15} /> {uiText.settings.refreshBackend}
            </button>
            <button onClick={onBackendStart} type="button" disabled={busy !== null}>
              <Play size={15} /> {uiText.settings.startOrConnect}
            </button>
            <button onClick={onBackendStop} type="button" disabled={busy !== null || !desktopBackend?.managed}>
              <X size={15} /> {uiText.settings.stopManagedBackend}
            </button>
          </div>
        </section>
      )}

      <section className="settings-block">
        <div className="settings-title"><Wand2 size={15} /> {uiText.settings.modelSection}</div>
        <label>
          <span>{uiText.settings.writerMode}</span>
          <select
            value={form.scene_writer}
            onChange={(event) =>
              onFormChange((current) => ({
                ...current,
                scene_writer: event.target.value as AgentSettingsUpdate["scene_writer"]
              }))
            }
          >
            <option value="rule_based">{uiText.settings.ruleBasedMode}</option>
            <option value="llm">{uiText.settings.llmMode}</option>
          </select>
        </label>
        <label>
          <span>{uiText.settings.providerName}</span>
          <input
            value={form.provider_label}
            onChange={(event) =>
              onFormChange((current) => ({ ...current, provider_label: event.target.value }))
            }
          />
        </label>
        <label>
          <span>{uiText.settings.baseUrl}</span>
          <input
            placeholder="https://provider.example/v1"
            value={form.llm_base_url}
            onChange={(event) =>
              onFormChange((current) => ({ ...current, llm_base_url: event.target.value }))
            }
          />
        </label>
        <label>
          <span>{uiText.settings.model}</span>
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
          <span>{uiText.settings.requestJsonMode}</span>
        </label>
      </section>

      <section className="settings-block">
        <div className="settings-title"><KeyRound size={15} /> {uiText.settings.apiKeySection}</div>
        <MetricRow label={uiText.settings.currentKey} value={apiKeyStatus} />
        <label>
          <span>{uiText.settings.replaceKey}</span>
          <input
            autoComplete="off"
            placeholder={uiText.settings.keyPlaceholder}
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
          <span>{uiText.settings.clearKey}</span>
        </label>
      </section>

      <section className="settings-block">
        <div className="settings-title"><Lock size={15} /> {uiText.settings.permissionSection}</div>
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
          <span>{uiText.settings.permissionWarning}</span>
        </div>
      </section>

      <section className="settings-block">
        <div className="settings-title"><Download size={15} /> {uiText.settings.versionSection}</div>
        <MetricRow label={uiText.settings.currentVersion} value={`v${APP_VERSION}`} />
        <div className={`update-card ${updateStatus.state}`}>
          <span>{updateStatus.message()}</span>
          {updateStatus.technicalDetails && (
            <details>
              <summary>{uiText.errors.technicalDetails}</summary>
              <code>{updateStatus.technicalDetails}</code>
            </details>
          )}
          {updateStatus.publishedAt && (
            <small>{uiText.settings.publishedAt}: {formatDateTime(updateStatus.publishedAt)}</small>
          )}
          {updateStatus.channel === "desktop" && (
            <small>{uiText.settings.desktopUpdateNote}</small>
          )}
          {updateStatus.state === "available" && updateStatus.canInstall && (
            <button
              className="inline-update-button"
              onClick={onInstallUpdate}
              type="button"
              disabled={busy !== null}
            >
              <Download size={14} /> {uiText.settings.installUpdate}
            </button>
          )}
          {updateStatus.state === "available" && !updateStatus.canInstall && updateTarget && (
            <a href={updateTarget} target="_blank" rel="noreferrer">
              <Download size={14} /> {uiText.settings.downloadInstaller}
            </a>
          )}
        </div>
      </section>

      <div className="settings-actions">
        <button onClick={onRefresh} type="button" disabled={busy !== null}>
          <RefreshCw size={15} /> {uiText.settings.refreshSettings}
        </button>
        <button onClick={onUpdateCheck} type="button" disabled={busy !== null}>
          <RefreshCw size={15} /> {uiText.settings.checkUpdates}
        </button>
        <button className="primary" onClick={onSave} type="button" disabled={busy !== null}>
          <Save size={15} /> {uiText.settings.saveSettings}
        </button>
      </div>
    </div>
  );
}

function ContextInspector({ pack }: { pack: ContextPack | null }) {
  if (!pack) {
    return <EmptyState icon={<SplitSquareVertical />} title={uiText.inspector.noContextTitle} text={uiText.inspector.noContextText} />;
  }
  return (
    <div className="inspector-body">
      <MetricRow label={uiText.inspector.budget} value={`${pack.budget.estimated_tokens}/${pack.budget.target_tokens}`} />
      <MetricRow
        label={uiText.language.artifactLanguageLabel}
        value={formatArtifactLanguage(pack.output_language, false)}
      />
      <MetricRow label={uiText.inspector.graphQueries} value={String(pack.provenance.graph_query_ids.length)} />
      <ListBlock title={uiText.inspector.mustInclude} items={pack.must_include} />
      <ListBlock title={uiText.inspector.mustNotViolate} items={pack.must_not_violate} tone="danger" />
      <ListBlock title={uiText.inspector.relationships} items={pack.active_relationships} />
      <ListBlock title={uiText.inspector.foreshadowing} items={pack.unresolved_foreshadowing} />
      <ListBlock title={uiText.inspector.missingContext} items={pack.missing_context.map((gap) => `${formatSeverity(gap.severity)}: ${gap.ref} - ${formatKnownMessage(gap.message)}`)} tone="warning" />
      <ListBlock title={uiText.inspector.droppedItems} items={pack.budget.dropped_items} />
    </div>
  );
}

function ContinuityInspector({ run, report }: { run: WorkflowRun | null; report: ContinuityReport | null }) {
  const blockingCount = report?.issues.filter((issue) => issue.blocking).length ?? 0;
  return (
    <div className="inspector-body">
      <MetricRow label={uiText.inspector.currentStep} value={stepLabels[run?.current_step as keyof typeof stepLabels] ?? uiText.common.none} />
      <MetricRow
        label={uiText.language.artifactLanguageLabel}
        value={
          run || report
            ? formatArtifactLanguage(run?.output_language ?? report?.output_language, run?.language_inferred)
            : uiText.common.none
        }
      />
      <MetricRow label={uiText.inspector.reviewPayload} value={formatStatus(run?.review_payload.status ?? "none")} />
      <MetricRow label={uiText.inspector.continuity} value={formatStatus(report?.status ?? "not checked")} />
      <MetricRow label={uiText.inspector.blockingIssues} value={String(blockingCount)} />
      {report ? (
        <>
          <ListBlock title={uiText.inspector.summary} items={[report.summary]} />
          <ListBlock title={uiText.inspector.checkedDimensions} items={report.checked_dimensions.map(formatDimension)} />
          <ListBlock
            title={uiText.inspector.issues}
            items={report.issues.map((issue) => `${formatSeverity(issue.severity)}: ${formatIssueType(issue.issue_type)} - ${formatKnownMessage(issue.description)} ${uiText.inspector.suggestion}: ${formatKnownMessage(issue.suggestion)}`)}
            tone={blockingCount > 0 ? "danger" : "warning"}
          />
        </>
      ) : (
        <EmptyState icon={<Activity />} title={uiText.inspector.noReportTitle} text={uiText.inspector.noReportText} />
      )}
      <ListBlock
        title={uiText.inspector.runSteps}
        items={(run?.steps ?? fallbackSteps).map((step) => `${stepLabels[step.name as keyof typeof stepLabels] ?? step.name}: ${formatStatus(step.status)}${step.message ? ` - ${formatKnownMessage(step.message)}` : ""}`)}
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
    return <EmptyState icon={<ShieldCheck />} title={uiText.inspector.noFactsTitle} text={uiText.inspector.noFactsText} />;
  }
  return (
    <div className="fact-list">
      {facts.map((fact) => (
        <div className="fact-row" key={fact.id}>
          <div>
            <strong>{localizeSystemValue(fact.fact_type)}</strong>
            <span>{fact.subject_id} {localizeSystemValue(fact.relation)} {fact.object_id}</span>
          </div>
          <p>{fact.rationale}</p>
          <div className="fact-actions">
            <button onClick={() => onReview(fact.id, "accept")} disabled={busy !== null || !canReview} type="button"><Check size={14} />{reviewActionLabels.accept}</button>
            <button onClick={() => onReview(fact.id, "defer")} disabled={busy !== null || !canReview} type="button"><Clock3 size={14} />{reviewActionLabels.defer}</button>
            <button onClick={() => onReview(fact.id, "reject")} disabled={busy !== null || !canReview} type="button"><X size={14} />{reviewActionLabels.reject}</button>
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
        <div className="preview-title"><Network size={15} /> {uiText.graph.title}</div>
        <EmptyState
          icon={<Network />}
          title={uiText.graph.emptyTitle}
          text={uiText.graph.emptyText}
        />
      </div>
    );
  }

  return (
    <div className="graph-preview">
      <div className="preview-title"><Network size={15} /> {uiText.graph.title}</div>
      <div className="graph-lines">
        {preview.relationships.length ? (
          preview.relationships.map((edge) => (
            <div key={edge.id}>
              <span title={edge.source_id}>{edge.source_label}</span>
              <b>{localizeSystemValue(edge.type)}</b>
              <span title={edge.target_id}>{edge.target_label}</span>
            </div>
          ))
        ) : (
          <p className="muted">{uiText.graph.noRelationships}</p>
        )}
      </div>
      {preview.truncated && <p className="muted">{uiText.graph.truncated}</p>}
      <div className="timeline">
        {preview.timeline.length ? (
          preview.timeline.map((item) => (
            <div
              key={item.id}
              className={item.id === selectedSceneId ? "current" : item.state}
            >
              {item.label}
            </div>
          ))
        ) : (
          <div>{uiText.graph.noScenes}</div>
        )}
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return <div className="meta"><span>{label}</span><strong>{value || uiText.common.missing}</strong></div>;
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return <div className="metric-row"><span>{label}</span><strong>{value}</strong></div>;
}

function ListBlock({ title, items, tone }: { title: string; items: string[]; tone?: "danger" | "warning" }) {
  return (
    <section className={`list-block ${tone ?? ""}`}>
      <div className="list-title">{title}</div>
      {items.length ? items.map((item) => <p key={item}>{item}</p>) : <p className="muted">{uiText.common.none}</p>}
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
  return refs.map(
    (ref) => `${formatRefKind(ref.kind)}: ${ref.ref}${ref.note ? ` / ${ref.note}` : ""}`
  );
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

const chapterStatusOptions = ["planned", "drafting", "completed", "archived"];
const sceneStatusOptions = ["planned", "drafting", "completed", "archived"];

function flattenScenes(project: ProjectOutline): SceneOutline[] {
  return project.chapters.flatMap((chapter) => chapter.scenes);
}

function projectToForm(project: ProjectOutline): ProjectForm {
  return {
    title: project.title ?? "",
    genre: project.genre ?? String(project.properties.genre ?? ""),
    language: outputLanguageOrNull(project.language) ?? "",
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

function findSceneChapterId(
  projects: ProjectOutline[],
  projectId: string,
  sceneId: string
): string | null {
  const project = projects.find((item) => item.id === projectId);
  if (!project) return null;
  const chapter = project.chapters.find((item) =>
    item.scenes.some((scene) => scene.id === sceneId)
  );
  return chapter?.id ?? null;
}

function sceneToForm(scene: SceneOutline, chapterId: string): SceneForm {
  const styleConstraints = validObject(scene.style_constraints)
    ? scene.style_constraints
    : objectProperty(scene.properties, "style_constraints");
  return {
    chapter_id: chapterId,
    title: scene.title ?? "",
    scene_index: String(scene.scene_index ?? 1),
    pov_character_id: scene.pov_character_id ?? "",
    location_id: scene.location_id ?? "",
    timeline_position: scene.timeline_position ?? "",
    goal: scene.goal ?? "",
    conflict: scene.conflict ?? "",
    outcome: scene.outcome ?? stringProperty(scene.properties, "outcome"),
    emotional_turn: scene.emotional_turn ?? stringProperty(scene.properties, "emotional_turn"),
    previous_scene_id: scene.previous_scene_id ?? stringProperty(scene.properties, "previous_scene_id"),
    status: (scene.status ?? stringProperty(scene.properties, "status")) || "planned",
    style_pov: stringProperty(styleConstraints, "pov"),
    style_tense: stringProperty(styleConstraints, "tense"),
    style_tone: stringProperty(styleConstraints, "tone"),
    style_sentence_rhythm: stringProperty(styleConstraints, "sentence_rhythm"),
    style_diction: stringProperty(styleConstraints, "diction"),
    style_dialogue_style: stringProperty(styleConstraints, "dialogue_style"),
    style_banned_patterns: stringArrayProperty(styleConstraints, "banned_patterns").join("\n"),
    required_characters: stringArrayProperty(scene.properties, "required_characters").join("\n"),
    must_include: stringArrayProperty(scene.properties, "must_include").join("\n"),
    must_not_violate: stringArrayProperty(scene.properties, "must_not_violate").join("\n")
  };
}

function chapterToForm(chapter: ChapterOutline): ChapterForm {
  return {
    title: chapter.title ?? "",
    volume_index: String(chapter.volume_index ?? 1),
    chapter_index: String(chapter.chapter_index ?? 1),
    summary: chapter.summary ?? "",
    purpose: chapter.purpose ?? "",
    status: chapter.status ?? "planned"
  };
}

function sceneStyleConstraints(form: SceneForm): Record<string, unknown> {
  const constraints: Record<string, unknown> = {};
  sceneStyleFieldMap.forEach(([formKey, constraintKey]) => {
    const value = form[formKey].trim();
    if (value) {
      constraints[constraintKey] = value;
    }
  });
  const bannedPatterns = splitLines(form.style_banned_patterns);
  if (bannedPatterns.length) {
    constraints.banned_patterns = bannedPatterns;
  }
  return constraints;
}

function validObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function objectProperty(
  properties: Record<string, unknown> | undefined,
  key: string
): Record<string, unknown> {
  const value = properties?.[key];
  return validObject(value) ? value : {};
}

function stringProperty(
  properties: Record<string, unknown> | undefined,
  key: string
): string {
  const value = properties?.[key];
  return typeof value === "string" ? value : "";
}

function stringArrayProperty(
  properties: Record<string, unknown>,
  key: string
): string[] {
  const value = properties[key];
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string");
}

function graphNodeOptionLabel(node: GraphNodePayload): string {
  const label = graphNodeDisplayName(node);
  return label === node.id ? node.id : `${label} / ${node.id}`;
}

function graphNodeDisplayName(node: GraphNodePayload): string {
  return String(node.properties.name ?? node.properties.title ?? node.properties.rule ?? node.id);
}

function findGraphNodeByLabel(nodes: GraphNodePayload[], label: string): GraphNodePayload | null {
  const normalizedLabel = normalizeMatchLabel(label);
  if (!normalizedLabel) return null;
  return (
    nodes.find((node) => {
      const nodeName = normalizeMatchLabel(graphNodeDisplayName(node));
      const nodeId = normalizeMatchLabel(node.id);
      return nodeName === normalizedLabel || nodeId === normalizedLabel;
    }) ?? null
  );
}

function normalizeMatchLabel(value: string): string {
  return value.trim().toLocaleLowerCase();
}

function splitLines(value: string): string[] {
  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function appendLineIfMissing(value: string, item: string): string {
  const lines = splitLines(value);
  return lines.includes(item) ? lines.join("\n") : [...lines, item].join("\n");
}

function toPositiveInteger(value: string, fallback: number): number {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function formatWriter(settings: AgentSettings | null): string {
  if (!settings) return uiText.common.loading;
  if (settings.scene_writer === "llm") {
    return settings.api_key_configured
      ? `${localizedTerms.llm} ${settings.llm_model}`
      : uiText.runtime.modelKeyMissing;
  }
  return uiText.runtime.localRules;
}

function formatWorkflowStep(stepName: string): string {
  return stepLabels[stepName as keyof typeof stepLabels] ?? stepName;
}

function formatDesktopBackendLabel(status: DesktopBackendStatus): string {
  if (!status.reachable) return uiText.runtime.backendNotConnected;
  if (!status.workspaceCompatible) return uiText.runtime.backendWorkspaceConflict;
  return status.managed ? uiText.runtime.backendManaged : uiText.runtime.backendExternal;
}

function formatDesktopBackendDetail(status: DesktopBackendStatus | null): string {
  if (!status) return uiText.common.loading;
  if (!status.reachable) return uiText.settings.notConnected;
  if (!status.workspaceCompatible) return uiText.runtime.backendWorkspaceConflict;
  return status.managed ? uiText.runtime.backendConnectedManaged : uiText.runtime.backendConnectedExternal;
}

function desktopBackendTone(status: DesktopBackendStatus): "good" | "warning" | "danger" | "neutral" {
  if (!status.reachable || !status.workspaceCompatible) return "danger";
  if (!status.managed) return "warning";
  return "good";
}

async function prepareSourceDocumentImport(
  file: File,
  mediaType: SourceMediaType,
  languageOverride?: SourceLanguage
): Promise<SourceDocumentImportRequest> {
  const arrayBuffer = await file.arrayBuffer();
  const checksum = await sha256Hex(arrayBuffer);
  const warnings: string[] = [];
  let extractedText: string | null = null;
  let extractionStatus: "ready" | "failed" = "ready";
  let extractionError: string | null = null;

  try {
    if (mediaType.includes("wordprocessingml")) {
      const result = await readDocxText(arrayBuffer);
      extractedText = normalizeImportedText(result.text);
      warnings.push(...result.warnings);
    } else {
      extractedText = normalizeImportedText(new TextDecoder("utf-8").decode(arrayBuffer));
    }
    if (!extractedText) throw new Error("Source text is empty.");
  } catch (exc) {
    extractionStatus = "failed";
    extractedText = null;
    const message = toErrorMessage(exc);
    extractionError = sanitizeSourceMetadata(
      mediaType.includes("wordprocessingml") ? `DOCX extraction failed: ${message}` : message,
      500
    );
  }

  const language = languageOverride ?? detectSourceLanguage(extractedText ?? "");
  return {
    title: file.name,
    relative_path: getImportPath(file),
    media_type: mediaType,
    language,
    byte_size: file.size,
    checksum_sha256: checksum,
    extraction_status: extractionStatus,
    extracted_text: extractedText,
    warnings: boundSourceWarnings(warnings),
    error: extractionError,
    provenance: {
      imported_by: "author",
      imported_via: "local_file",
      source_last_modified_ms: file.lastModified,
      note: "workbench.source.import"
    }
  };
}

function formatProjectLanguage(project: ProjectOutline): string {
  if (project.language_status === "needs_review") {
    return uiText.language.projectLanguageNeedsReview;
  }
  const label = outputLanguageOrNull(project.language) === "zh-CN"
    ? uiText.language.chinese
    : outputLanguageOrNull(project.language) === "en-US"
      ? uiText.language.english
      : null;
  if (label) {
    return project.language_status === "inferred"
      ? `${label}${uiText.language.inferredLanguage}`
      : label;
  }
  return uiText.sidebar.languageUnset;
}

function formatSourceLanguage(language: SourceLanguage): string {
  if (language === "zh-CN") return uiText.language.chinese;
  if (language === "en-US") return uiText.language.english;
  return uiText.language.undetermined;
}

function formatArtifactLanguage(
  language: AppLocale | null | undefined,
  inferred: boolean | undefined
): string {
  if (!language) return uiText.language.historicalLanguageUnknown;
  const label = language === "zh-CN" ? uiText.language.chinese : uiText.language.english;
  return `${label}${inferred ? uiText.language.inferredLanguage : ""}`;
}

async function sha256Hex(arrayBuffer: ArrayBuffer): Promise<string> {
  if (!globalThis.crypto?.subtle) throw new Error(uiText.errors.webCryptoUnavailable);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", arrayBuffer);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function readDocxText(arrayBuffer: ArrayBuffer): Promise<{ text: string; warnings: string[] }> {
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
  const result = await mammoth.extractRawText({ arrayBuffer });

  return {
    text: result.value,
    warnings: boundSourceWarnings(result.messages.map((message) => message.message))
  };
}

function boundSourceWarnings(values: string[]): string[] {
  const warnings: string[] = [];
  let remainingCharacters = 2000;
  for (const value of values) {
    if (warnings.length >= 32 || remainingCharacters <= 0) break;
    const warning = sanitizeSourceMetadata(value, Math.min(200, remainingCharacters));
    if (!warning) continue;
    warnings.push(warning);
    remainingCharacters -= warning.length;
  }
  return warnings;
}

function sanitizeSourceMetadata(value: string, maxLength: number): string {
  return value
    .replace(/(?:\b[a-zA-Z]:[\\/]|\\\\)[^\s"'<>]+/g, uiText.library.redactedLocalPath)
    .trim()
    .slice(0, maxLength);
}

function buildLibraryTree(documents: SourceDocumentSummary[]): LibraryTreeNode {
  const root: LibraryTreeNode = {
    id: "library",
    name: uiText.library.localRoot,
    path: "library",
    type: "folder",
    children: []
  };

  for (const document of documents) {
    const parts = document.relative_path.split("/").filter(Boolean);
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
      name: document.title,
      path: document.relative_path,
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
  const slashPath = path.replace(/\\/g, "/");
  if (slashPath.startsWith("/") || /^[a-zA-Z]:/.test(slashPath)) {
    throw new Error(uiText.errors.sourceUnsafePath);
  }
  const parts = slashPath.split("/").filter(Boolean);
  if (parts.some((part) => part === "." || part === "..")) {
    throw new Error(uiText.errors.sourceUnsafePath);
  }
  const normalized = parts.join("/");
  if (!normalized) {
    throw new Error(uiText.errors.sourceUnsafePath);
  }
  return normalized;
}

function getSourceMediaType(fileName: string): SourceMediaType | null {
  const normalizedName = fileName.toLowerCase();
  if (normalizedName.endsWith(".txt")) return "text/plain";
  if (normalizedName.endsWith(".md") || normalizedName.endsWith(".markdown")) {
    return "text/markdown";
  }
  if (normalizedName.endsWith(".docx")) {
    return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  }
  return null;
}

function normalizeImportedText(text: string): string {
  return text.replace(/^\uFEFF/, "").replace(/\r\n?/g, "\n").trim();
}

function detectSourceLanguage(text: string): SourceLanguage {
  const sample = text.slice(0, 100_000);
  const hanCount = sample.match(/\p{Script=Han}/gu)?.length ?? 0;
  const latinCount = sample.match(/[A-Za-z]/g)?.length ?? 0;
  if (hanCount >= 8 && hanCount >= latinCount * 0.15) return "zh-CN";
  if (latinCount >= 20 && hanCount <= latinCount * 0.02) return "en-US";
  return "und";
}

function requireReadySourceText(document: SourceDocument): string {
  const text = normalizeImportedText(document.extracted_text ?? "");
  if (document.extraction_status !== "ready" || !text) {
    throw new Error(uiText.errors.sourceDetailNotReady);
  }
  return text;
}

function requireProjectContentLanguage(
  document: SourceDocumentSummary,
  projectLanguage: string | null | undefined
): void {
  if (document.language === "und") throw new Error(uiText.errors.sourceLanguageRequired);
  if (document.language !== outputLanguageOrNull(projectLanguage)) {
    throw new Error(uiText.errors.sourceContentLanguageMismatch);
  }
}

function outputLanguageOrNull(value: string | null | undefined): AppLocale | null {
  return value === "zh-CN" || value === "en-US" ? value : null;
}

function sourceMediaTypeLabel(mediaType: SourceMediaType): string {
  if (mediaType === "text/plain") return uiText.library.formats.txt;
  if (mediaType === "text/markdown") return uiText.library.formats.markdown;
  return uiText.library.formats.docx;
}

function sourceFileAccept(mediaType: SourceMediaType): string {
  if (mediaType === "text/plain") return ".txt";
  if (mediaType === "text/markdown") return ".md,.markdown";
  return ".docx";
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
    return "Local FastAPI backend is unreachable. Check the configured backend and port.";
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
    return new Intl.DateTimeFormat(APP_LOCALE, {
      dateStyle: "medium",
      timeStyle: "short"
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function technicalErrorMessage(exc: unknown): string {
  return exc instanceof ApiRequestError ? exc.technicalDetails : toErrorMessage(exc);
}

function isLocalizedUserError(message: string): boolean {
  return Object.values(uiText.errors).some(
    (value) => typeof value === "string" && value === message
  );
}

function loadUiLocale(): AppLocale {
  if (typeof window === "undefined") return "zh-CN";
  try {
    return normalizeAppLocale(window.localStorage.getItem(UI_LOCALE_STORAGE_KEY));
  } catch {
    return "zh-CN";
  }
}

const fallbackSteps: WorkflowStep[] = [
  { name: "build_context", status: "pending", artifact_refs: {} },
  { name: "write_draft", status: "pending", artifact_refs: {} },
  { name: "check_continuity", status: "pending", artifact_refs: {} },
  { name: "extract_state", status: "pending", artifact_refs: {} },
  { name: "human_review", status: "pending", artifact_refs: {} }
];
