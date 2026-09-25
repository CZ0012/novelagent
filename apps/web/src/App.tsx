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
import { OutlineLanguagePreview } from "./OutlineLanguagePreview";
import { canApplyOutlineLanguagePatch, outlineLanguageApplicationRecorded, outlineLanguageFailureKey, outlineLanguageScopeMatches, parseOutlineLanguagePatch } from "./outlineLanguage";
import {
  AgentDiscussionMode,
  AgentDiscussionRequest,
  AgentDiscussionResult,
  AgentPermissionLevel,
  AgentSettings,
  AgentSettingsUpdate,
  ModelExecution,
  ApiRequestError,
  isGeneratedLanguageConflict,
  isInvalidModelOutput,
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
  loadLocaleCatalog,
  localeRegistry,
  SUPPORTED_UI_LOCALES,
  localizedTerms,
  localizeGraphLabel,
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
import { APP_VERSION, GITHUB_LATEST_RELEASE_API, GITHUB_REPOSITORY } from "./version";
import {
  DEFAULT_SOURCE_PANE_LAYOUT,
  SOURCE_PANE_STACK_BREAKPOINT_PX,
  type SourcePaneBounds,
  type SourcePaneLayout,
  clampSourcePaneLayout,
  readSourcePaneLayout,
  resetSourcePaneLayoutDimension,
  separatorKeyboardValue,
  sourcePaneBounds,
  writeSourcePaneLayout
} from "./sourcePaneLayout";
import {
  type PromotionTargetPolicy,
  type SourceAgentEligibility,
  type UniqueRefResolution,
  addStableSourceSelection,
  agentIncludedDraftPolicy,
  type ProposalEditorSnapshot,
  canOpenPromotedDraft,
  canRestoreSavedDraft,
  continueAfterSuccessfulSave,
  draftIsDirty,
  exactDraftMatchesEditorScene,
  promotionTargetPolicy,
  proposalActionPolicy,
  proposalAutoSelection,
  proposalIsDirty,
  projectRequestIsCurrent,
  resolveUniqueProposalRef,
  shouldHydrateProposalEditor,
  sourceCanHandoff,
  sourceAgentEligibility
} from "./reviewPolicies";
import { canHydrateDraftLoad, draftSaveCompletionPolicy, draftScopesMatch, type DraftScope } from "./draftProtection";
import { AgentPresets } from "./AgentPresets";
import { classifyDocumentFile, extractDocumentFile } from "./documentImport";
import { importErrorCode, importFailureMessage, sourceImportFailureMessage, sourceImportWarningMessage } from "./documentImportMessages";
import { ModelRoutingSettings, modelExecutionLabel } from "./ModelRoutingSettings";
import { modelProviderFailureKey } from "./modelProviderErrors";
import { discussionTask, resolvedTask, taskConnectionReady, settingsToForm, settingsSavePayload, settingsRequestIsCurrent } from "./modelRouting";
import { exportAuthorText } from "./exportText";
import { DEFAULT_API_BASE, loadBrowserApiBase, normalizeApiBase, saveBrowserApiBase } from "./clientPreferences";
import { backendVersionCompatibility, backendVersionRequestIsCurrent, readBackendVersion, type BackendVersion } from "./backendVersion";
import { DesktopUpdateFailure, isWindowsUpdateFileLock, runSafeDesktopUpdate } from "./safeDesktopUpdate";
import { ProjectTree } from "./ProjectTree";
import { ChapterManuscript, ManuscriptProse, selectedManuscriptRange, type ManuscriptSelection } from "./ManuscriptReader";
import { CompositionComposer, CompositionPreview, parseComposition, compositionApplicationRecorded, canApplyComposition as compositionCanApply, type CompositionInput } from "./CompositionPanel";
import { ManuscriptDiff } from "./ManuscriptDiff";
import { proposalCreationMethod } from "./proposalProvenance";
import { genreLabel } from "./genreLabels";
import { changedMetadataFields, chapterEditorMatches, chapterTitleIsDirty, chapterTitleUpdate, type ChapterTitleEditor, type ChapterEditorScope } from "./chapterEditing";
import "./styles.css";

type InspectorTab = "agent" | "context" | "continuity" | "facts" | "settings";
type WorkspaceTab = "write" | "sources" | "proposals" | "workflow";

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

type ExactDraftLookup =
  | { status: "idle" | "none" | "ambiguous" | "missing_target" | "loading"; ref: string | null; draft: null }
  | { status: "ready"; ref: string; draft: Draft }
  | { status: "error"; ref: string; draft: null };

type PendingProposalNavigation = {
  label: string;
  kind: "proposal" | "draft";
};

type ProposalNavigationAction = () => void;

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
  selectedStart?: number;
  selectedEnd?: number;
  selectedDraftId?: string;
  includeContextPack: boolean;
  includeLatestDraft: boolean;
  allowWebSearch: boolean;
  webSearchQuery: string;
};

type UpdateStatus = {
  state: "idle" | "checking" | "current" | "available" | "downloading" | "awaiting_edits" | "installing" | "error";
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
  const [localeLoading, setLocaleLoading] = useState(false);
  const localeRequestRef = useRef(0);
  const [apiBase, setApiBase] = useState(() => isDesktopRuntime() ? DEFAULT_API_BASE : loadBrowserApiBase());
  const [projects, setProjects] = useState<ProjectOutline[]>([]);
  const [workspaceLoaded, setWorkspaceLoaded] = useState(false);
  const [workspaceLoadError, setWorkspaceLoadError] = useState(false);
  const [projectId, setProjectId] = useState("");
  const [sceneId, setSceneId] = useState("");
  const [chapterSelection, setChapterSelection] = useState<{ projectId: string; id: string } | null>(null);
  const [activeTab, setInspectorTab] = useState<InspectorTab>("agent");
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const setActiveTab = useCallback((tab: InspectorTab) => {
    setInspectorTab(tab);
    setInspectorOpen(true);
  }, []);
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("write");
  const [contextPack, setContextPack] = useState<ContextPack | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const currentDraftRef = useRef(draft);
  currentDraftRef.current = draft;
  const [draftText, setDraftText] = useState("");
  const [draftSummary, setDraftSummary] = useState("");
  const [draftLoading, setDraftLoading] = useState(false);
  const [proposals, setProposals] = useState<ProposalArtifact[]>([]);
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null);
  const [creatingNewProposal, setCreatingNewProposal] = useState(false);
  const [proposalTitle, setProposalTitle] = useState("");
  const [proposalText, setProposalText] = useState("");
  const [proposalArtifactType, setProposalArtifactType] =
    useState<ProposalArtifactType>("scene_draft");
  const [proposalStatusFilter, setProposalStatusFilter] = useState<ProposalStatus | "all">("all");
  const [proposalSourceDraftId, setProposalSourceDraftId] = useState("");
  const [proposalVersions, setProposalVersions] = useState<ProposalArtifact[]>([]);
  const [proposalVersionsLoading, setProposalVersionsLoading] = useState(false);
  const [reviewProposalVersion, setReviewProposalVersion] = useState<number | null>(null);
  const reviewProposalOwnerRef = useRef<string | null>(null);
  const [proposalBaseline, setProposalBaseline] = useState<ExactDraftLookup>({
    status: "idle",
    ref: null,
    draft: null
  });
  const [proposalBaselineOwnerKey, setProposalBaselineOwnerKey] = useState("");
  const [proposalPromotedDraft, setProposalPromotedDraft] = useState<ExactDraftLookup>({
    status: "idle",
    ref: null,
    draft: null
  });
  const [pendingProposalNavigation, setPendingProposalNavigation] =
    useState<PendingProposalNavigation | null>(null);
  const pendingProposalNavigationRef = useRef<ProposalNavigationAction | null>(null);
  const pendingNavigationCancelRef = useRef<(() => void) | null>(null);
  const proposalEditorSnapshotRef = useRef<ProposalEditorSnapshot | null>(null);
  const selectedProposalStableRef = useRef<ProposalArtifact | null>(null);
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [runEvents, setRunEvents] = useState<WorkflowStep[]>([]);
  const [continuityReport, setContinuityReport] = useState<ContinuityReport | null>(null);
  const [facts, setFacts] = useState<CandidateFact[]>([]);
  const [graphPreview, setGraphPreview] = useState<ProjectGraphPreview | null>(null);
  const [storyCharacters, setStoryCharacters] = useState<GraphNodePayload[]>([]);
  const [storyLocations, setStoryLocations] = useState<GraphNodePayload[]>([]);
  const [agentSettings, setAgentSettings] = useState<AgentSettings | null>(null);
  const [agentForm, setAgentForm] = useState<AgentSettingsUpdate>(defaultAgentForm);
  const settingsRequestSequenceRef = useRef(0);
  const settingsEditRevisionRef = useRef(0);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [projectForm, setProjectForm] = useState<ProjectForm>(defaultProjectForm);
  const [chapterForm, setChapterForm] = useState<ChapterForm>(defaultChapterForm);
  const [chapterTitleEditor, setChapterTitleEditor] = useState<ChapterTitleEditor | null>(null);
  const [chapterMetadataTarget, setChapterMetadataTarget] = useState<(ChapterEditorScope & { baseline: ChapterForm }) | null>(null);
  const chapterTitleDirty = chapterTitleIsDirty(chapterTitleEditor);
  const chapterMetadataDirty = Boolean(chapterMetadataTarget && JSON.stringify(chapterForm) !== JSON.stringify(chapterMetadataTarget.baseline));
  const chapterEditsDirty = chapterTitleDirty || chapterMetadataDirty;
  const [sceneForm, setSceneForm] = useState<SceneForm>(defaultSceneForm);
  const [sceneTitleEditor, setSceneTitleEditor] = useState<{ apiBase: string; projectId: string; sceneId: string; title: string; originalTitle: string } | null>(null);
  const sceneTitleDirty = Boolean(sceneTitleEditor && sceneTitleEditor.title !== sceneTitleEditor.originalTitle);
  const [sceneMetadataTarget, setSceneMetadataTarget] = useState<{ apiBase: string; projectId: string; sceneId: string; baseline: SceneForm } | null>(null);
  const sceneMetadataDirty = Boolean(sceneMetadataTarget && JSON.stringify(sceneForm) !== JSON.stringify(sceneMetadataTarget.baseline));
  const sceneEditsDirty = sceneTitleDirty || sceneMetadataDirty;
  const metadataEditorsRef = useRef({ chapterDirty: false, sceneDirty: false, chapterEditing: false, sceneEditing: false });
  metadataEditorsRef.current = {
    chapterDirty: chapterEditsDirty, sceneDirty: sceneEditsDirty,
    chapterEditing: Boolean(chapterMetadataTarget || chapterTitleEditor), sceneEditing: Boolean(sceneMetadataTarget || sceneTitleEditor)
  };
  const [characterForm, setCharacterForm] = useState<CharacterForm>(defaultCharacterForm);
  const [locationForm, setLocationForm] = useState<LocationForm>(defaultLocationForm);
  const [worldRuleForm, setWorldRuleForm] = useState<WorldRuleForm>(defaultWorldRuleForm);
  const [agentDiscussionForm, setAgentDiscussionForm] =
    useState<AgentDiscussionForm>(defaultAgentDiscussionForm);
  const [agentDiscussionResult, setAgentDiscussionResult] =
    useState<AgentDiscussionResult | null>(null);
  const [draftSelection, setDraftSelection] = useState("");
  const [draftSelectionRange, setDraftSelectionRange] = useState<ManuscriptSelection | null>(null);
  const [manuscriptMode, setManuscriptMode] = useState<"preview" | "edit">("preview");
  const [readingChapterId, setReadingChapterId] = useState<string | null>(null);
  const [agentTarget, setAgentTarget] = useState<"scene" | "composition">("scene");
  const pendingManuscriptSelectionRef = useRef<{ projectId: string; draft: Draft; range: ManuscriptSelection } | null>(null);
  const draftTextareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [desktopUpdate, setDesktopUpdate] = useState<TauriUpdate | null>(null);
  const updateInProgressRef = useRef(false);
  const [backendVersionState, setBackendVersionState] = useState<{ apiBase: string; value: BackendVersion }>({ apiBase: "", value: { version: null, source: "unknown" } });
  const backendVersionSequenceRef = useRef(0);
  const backendVersion = backendVersionState.apiBase === apiBase ? backendVersionState.value : { version: null, source: "unknown" as const };
  const versionCompatibility = backendVersionCompatibility(APP_VERSION, backendVersion);
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
  const libraryPanelRef = useRef<HTMLElement | null>(null);
  const libraryGridRef = useRef<HTMLDivElement | null>(null);
  const [sourcePaneLayout, setSourcePaneLayout] = useState<SourcePaneLayout>(() =>
    loadSourcePaneLayout()
  );
  const [sourcePaneBoundsState, setSourcePaneBoundsState] = useState<SourcePaneBounds>(() =>
    sourcePaneBounds({
      viewportHeight: typeof window === "undefined" ? 900 : window.innerHeight,
      panelTop: 160,
      containerWidth: typeof window === "undefined" ? 980 : window.innerWidth
    })
  );
  const [sourcePaneStacked, setSourcePaneStacked] = useState(() =>
    typeof window !== "undefined" && window.innerWidth <= SOURCE_PANE_STACK_BREAKPOINT_PX
  );
  const sourceListRequestSequenceRef = useRef(0);
  const draftRequestSequenceRef = useRef(0);
  const draftEditRevisionRef = useRef(0);
  const draftEditorScopeRef = useRef<DraftScope | null>(null);
  const draftContextInitializedRef = useRef<string | null>(null);
  const draftDirtyRef = useRef(false);
  const proposalListRequestSequenceRef = useRef(0);
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
    settingsRequestSequenceRef.current += 1; settingsEditRevisionRef.current += 1;
    setApiKeyInput(""); setClearApiKey(false); setAgentSettings(null); setAgentForm(defaultAgentForm);
  }, [apiBase]);

  const changeUiLocale = useCallback(async (locale: AppLocale) => {
    const request = ++localeRequestRef.current;
    setLocaleLoading(true);
    try {
      await loadLocaleCatalog(locale);
      if (request !== localeRequestRef.current) return;
      await activateLocale(locale);
      setUiLocale(locale);
    } catch {
      setError(uiText.errors.requestFailed);
    } finally {
      if (request === localeRequestRef.current) setLocaleLoading(false);
    }
  }, []);

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

  useEffect(() => {
    if (typeof window === "undefined") return;
    const media = window.matchMedia(`(max-width: ${SOURCE_PANE_STACK_BREAKPOINT_PX}px)`);
    const recompute = () => {
      const stacked = media.matches;
      setSourcePaneStacked(stacked);
      if (stacked || !libraryPanelRef.current || !libraryGridRef.current) return;
      const bounds = sourcePaneBounds({
        viewportHeight: window.innerHeight,
        panelTop: libraryPanelRef.current.getBoundingClientRect().top,
        containerWidth: libraryGridRef.current.clientWidth
      });
      setSourcePaneBoundsState(bounds);
    };
    recompute();
    window.addEventListener("resize", recompute);
    media.addEventListener("change", recompute);
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(recompute);
    if (libraryGridRef.current) observer?.observe(libraryGridRef.current);
    return () => {
      window.removeEventListener("resize", recompute);
      media.removeEventListener("change", recompute);
      observer?.disconnect();
    };
  }, [workspaceTab]);

  const changeSourcePaneDimension = useCallback(
    (dimension: keyof SourcePaneLayout, value: number, commit: boolean) => {
      setSourcePaneLayout((current) => {
        const next = clampSourcePaneLayout({ ...current, [dimension]: value }, sourcePaneBoundsState);
        if (commit) persistSourcePaneLayout(next);
        return next;
      });
    },
    [sourcePaneBoundsState]
  );

  const resetSourcePaneDimension = useCallback(
    (dimension: keyof SourcePaneLayout) => {
      setSourcePaneLayout((current) => {
        const next = resetSourcePaneLayoutDimension(current, dimension, sourcePaneBoundsState);
        persistSourcePaneLayout(next);
        return next;
      });
    },
    [sourcePaneBoundsState]
  );

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
      (chapterSelection?.projectId === projectId && selectedProject?.chapters.some((chapter) => chapter.id === chapterSelection.id) ? chapterSelection.id : null) ??
      findSceneChapterId(projects, projectId, sceneId) ??
      selectedProject?.chapters[0]?.id ??
      "",
    [chapterSelection, projectId, projects, sceneId, selectedProject]
  );
  const selectedChapter = useMemo(
    () => selectedProject?.chapters.find((chapter) => chapter.id === currentChapterId) ?? null,
    [currentChapterId, selectedProject]
  );
  const readingChapter = selectedProject?.chapters.find((chapter) => chapter.id === readingChapterId) ?? null;
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
    () => proposals.find((proposal) => proposal.id === selectedProposalId) ?? (
      selectedProposalStableRef.current?.id === selectedProposalId
        ? selectedProposalStableRef.current
        : null
    ),
    [proposals, selectedProposalId]
  );
  const visibleProposals = useMemo(
    () =>
      proposalStatusFilter === "all"
        ? proposals
        : proposals.filter((proposal) => proposal.status === proposalStatusFilter),
    [proposalStatusFilter, proposals]
  );
  const proposalDirty = useMemo(
    () => proposalIsDirty(selectedProposal, proposalTitle, proposalText),
    [proposalText, proposalTitle, selectedProposal]
  );
  const draftDirty = useMemo(
    () => draftIsDirty(draft, draftText, draftSummary),
    [draft, draftSummary, draftText]
  );
  draftDirtyRef.current = draftDirty;
  const proposalTarget = useMemo(
    () => promotionTargetPolicy(selectedProposal?.target_refs ?? [], sceneId),
    [sceneId, selectedProposal]
  );
  const proposalTargetScene = useMemo(() => {
    const targetId = proposalTarget.targetSceneId;
    return targetId && selectedProject
      ? flattenScenes(selectedProject).find((scene) => scene.id === targetId) ?? null
      : null;
  }, [proposalTarget, selectedProject]);
  const proposalTargetRef = useMemo(
    () => resolveUniqueProposalRef(selectedProposal?.target_refs ?? [], "scene"),
    [selectedProposal]
  );
  const proposalPromotedDraftTargetRef = useMemo<UniqueRefResolution>(
    () => proposalTargetRef.status === "none" && sceneId
      ? { status: "unique", ref: sceneId }
      : proposalTargetRef,
    [proposalTargetRef, sceneId]
  );
  const proposalDerivedDraftRef = useMemo(
    () => resolveUniqueProposalRef(selectedProposal?.derived_refs ?? [], "draft"),
    [selectedProposal]
  );
  const selectedReviewProposal = useMemo(
    () =>
      proposalVersions.find((version) => version.id === selectedProposal?.id && version.version === reviewProposalVersion) ??
      selectedProposal,
    [proposalVersions, reviewProposalVersion, selectedProposal]
  );
  const proposalReviewTargetRef = useMemo(
    () => resolveUniqueProposalRef(selectedReviewProposal?.target_refs ?? [], "scene"),
    [selectedReviewProposal]
  );
  const proposalBaselineRef = useMemo(
    () => resolveUniqueProposalRef(selectedReviewProposal?.source_refs ?? [], "draft"),
    [selectedReviewProposal]
  );
  const proposalBaselineKey = JSON.stringify([apiBase, projectId, selectedReviewProposal?.id, selectedReviewProposal?.version, proposalBaselineRef, proposalReviewTargetRef]);
  const effectiveProposalBaseline: ExactDraftLookup = proposalBaselineOwnerKey === proposalBaselineKey ? proposalBaseline : { status: "loading", ref: null, draft: null };
  const effectiveSourcePaneLayout = useMemo(
    () => clampSourcePaneLayout(sourcePaneLayout, sourcePaneBoundsState),
    [sourcePaneBoundsState, sourcePaneLayout]
  );

  const hydrateProposalEditor = useCallback((proposal: ProposalArtifact | null) => {
    if (!proposal) {
      proposalEditorSnapshotRef.current = null;
      selectedProposalStableRef.current = null;
      setProposalTitle("");
      setProposalText("");
      setProposalArtifactType("scene_draft");
      setProposalSourceDraftId("");
      return;
    }
    proposalEditorSnapshotRef.current = {
      id: proposal.id,
      version: proposal.version,
      title: proposal.title,
      body: proposal.body
    };
    selectedProposalStableRef.current = proposal;
    setProposalTitle(proposal.title);
    setProposalText(proposal.body);
    setProposalArtifactType(proposal.artifact_type);
    const sourceDraftRef = resolveUniqueProposalRef(proposal.source_refs, "draft");
    setProposalSourceDraftId(sourceDraftRef.status === "unique" ? sourceDraftRef.ref : "");
  }, []);

  const resetProposalScope = useCallback(() => {
    proposalListRequestSequenceRef.current += 1;
    setProposals([]);
    setCreatingNewProposal(false);
    setSelectedProposalId(null);
    hydrateProposalEditor(null);
  }, [hydrateProposalEditor]);

  const runAction = useCallback(async (label: string, action: () => Promise<unknown>) => {
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
        const providerKey = modelProviderFailureKey(exc);
        setError(manuscriptFailureMessage(exc) ?? (providerKey ? uiText.errors[providerKey] : null) ?? outlineLanguageFailureMessage(exc) ?? (isInvalidModelOutput(exc) ? uiText.errors.invalidModelOutput : isGeneratedLanguageConflict(exc) ? uiText.errors.generatedLanguageConflict : uiText.errors.requestFailed));
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
      const currentScope = () => activeApiBaseRef.current === apiBase && activeProjectIdRef.current === projectId;
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
        if (!currentScope()) return;
        progress.current = index + 1;
        progress.currentName = file.name;
        setSourceImportProgress({ ...progress });
        const classified = classifyDocumentFile(file.name);
        if (classified.kind === "temporary") { progress.skipped += 1; setSourceImportProgress({ ...progress }); continue; }
        const mediaType = classified.kind === "supported" ? classified.mediaType : null;
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
          if (!currentScope()) return;
          if (retryTarget) {
            request.title = retryTarget.title;
            request.relative_path = retryTarget.relative_path;
          }
          const result = await apiPost<SourceDocumentImportResult>(
            apiBase,
            `/projects/${projectId}/sources`,
            request
          );
          if (!currentScope()) return;
          firstPersistedId ??= result.document.id;
          if (result.created) progress.created += 1;
          else if (result.updated) progress.updated += 1;
          else progress.unchanged += 1;
          if (result.document.extraction_status === "failed") {
            progress.failed += 1;
            progress.issues.push({
              name: result.document.title,
              message: sourceImportFailureMessage(result.document),
              technicalDetails: importErrorCode(result.document.error) ? undefined : result.document.error ?? undefined
            });
          }
          for (const path of getAncestorFolderPaths(result.document.relative_path)) {
            setExpandedLibraryPaths((current) => new Set(current).add(path));
          }
        } catch (exc) {
          if (!currentScope()) return;
          progress.failed += 1;
          const detail = exc instanceof ApiRequestError ? exc.technicalDetails : toErrorMessage(exc);
          progress.issues.push({
            name: file.name,
            message: importFailureMessage(exc) ?? (isLocalizedUserError(detail) ? detail : uiText.documentImport.unknown_error),
            technicalDetails: importFailureMessage(exc) || isLocalizedUserError(detail) ? undefined : detail
          });
        }
        setSourceImportProgress({ ...progress });
      }
      progress.active = false;
      progress.currentName = "";
      setSourceImportProgress({ ...progress });
      await refreshSources(projectId);
      if (!currentScope()) return;
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
      setWorkspaceLoadError(false);
      let payload: { projects: ProjectOutline[] };
      try {
        payload = await apiGet<{ projects: ProjectOutline[] }>(apiBase, "/projects");
      } catch (error) {
        if (activeApiBaseRef.current === apiBase) { setWorkspaceLoadError(true); setWorkspaceLoaded(false); }
        throw error;
      }
      if (activeApiBaseRef.current !== apiBase) return { projectId: activeProjectIdRef.current, sceneId: activeSceneIdRef.current };
      const nextProjects = payload.projects;
      setProjects(nextProjects);
      setWorkspaceLoaded(true);

      if (!nextProjects.length) {
        resetProposalScope();
        setProjectId("");
        setSceneId("");
        setContextPack(null);
        setDraft(null);
        setDraftText("");
        setDraftSummary("");
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
      if (activeProjectIdRef.current !== nextProject.id) resetProposalScope();
      setProjectId(nextProject.id);
      setSceneId(nextScene?.id ?? "");
      return { projectId: nextProject.id, sceneId: nextScene?.id ?? "" };
    },
    [apiBase, resetProposalScope]
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
      const request = { scope: { apiBase, projectId: targetProjectId, sceneId: targetSceneId }, sequence: requestSequence, editorRevision: draftEditRevisionRef.current };
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
      setDraftLoading(true);
      try {
        payload = await apiGet<{ draft: Draft | null }>(
          requestApiBase,
          `/projects/${targetProjectId}/scenes/${targetSceneId}/draft`
        );
      } catch (exc) {
        if (!requestIsCurrent()) return;
        throw exc;
      } finally {
        if (requestIsCurrent()) setDraftLoading(false);
      }
      if (!canHydrateDraftLoad(request, {
        scope: { apiBase: activeApiBaseRef.current, projectId: activeProjectIdRef.current, sceneId: activeSceneIdRef.current },
        sequence: draftRequestSequenceRef.current, editorRevision: draftEditRevisionRef.current
      }, draftEditorScopeRef.current, draftDirtyRef.current)) return;
      draftEditorScopeRef.current = request.scope;
      const contextScope = JSON.stringify(request.scope);
      if (draftContextInitializedRef.current !== contextScope) {
        draftContextInitializedRef.current = contextScope;
        setAgentDiscussionForm((current) => ({ ...current, includeLatestDraft: Boolean(payload.draft?.text.trim()) }));
      }
      setDraft(payload.draft);
      setDraftText(payload.draft?.text ?? "");
      setDraftSummary(payload.draft?.summary ?? "");
    },
    [apiBase, projectId, sceneId]
  );

  const refreshProposals = useCallback(
    async (targetProjectId = projectId) => {
      const requestSequence = ++proposalListRequestSequenceRef.current;
      const requestApiBase = apiBase;
      const requestIsCurrent = () => projectRequestIsCurrent(
        requestSequence,
        proposalListRequestSequenceRef.current,
        requestApiBase,
        activeApiBaseRef.current,
        targetProjectId,
        activeProjectIdRef.current
      );
      if (!targetProjectId) {
        if (requestIsCurrent()) setProposals([]);
        return [];
      }
      let payload: { proposals: ProposalArtifact[] };
      try {
        payload = await apiGet<{ proposals: ProposalArtifact[] }>(
          requestApiBase,
          `/projects/${targetProjectId}/proposals`
        );
      } catch (exc) {
        if (!requestIsCurrent()) return [];
        throw exc;
      }
      if (!requestIsCurrent()) return [];
      setProposals(payload.proposals);
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

  const changeAgentForm: React.Dispatch<React.SetStateAction<AgentSettingsUpdate>> = useCallback((update) => {
    settingsEditRevisionRef.current += 1; setAgentForm(update);
  }, []);
  const changeApiKeyInput = useCallback((value: string) => { settingsEditRevisionRef.current += 1; setApiKeyInput(value); }, []);
  const changeClearApiKey = useCallback((value: boolean) => { settingsEditRevisionRef.current += 1; setClearApiKey(value); }, []);

  const refreshAgentSettings = useCallback(async () => {
    const request = { apiBase, sequence: ++settingsRequestSequenceRef.current, revision: settingsEditRevisionRef.current };
    const settings = await apiGet<AgentSettings>(apiBase, "/settings/agent");
    if (activeApiBaseRef.current !== apiBase || settingsRequestSequenceRef.current !== request.sequence) return;
    setAgentSettings(settings);
    if (!settingsRequestIsCurrent(request, { apiBase: activeApiBaseRef.current, sequence: settingsRequestSequenceRef.current, revision: settingsEditRevisionRef.current })) return;
    setAgentForm(settingsToForm(settings)); setApiKeyInput(""); setClearApiKey(false);
  }, [apiBase]);

  const saveAgentSettings = useCallback(async () => {
    if (!agentSettings) return;
    const request = { apiBase, sequence: ++settingsRequestSequenceRef.current, revision: settingsEditRevisionRef.current };
    const payload = settingsSavePayload(agentForm, apiKeyInput, clearApiKey);
    const settings = await apiPut<AgentSettings>(apiBase, "/settings/agent", payload);
    if (activeApiBaseRef.current !== apiBase || settingsRequestSequenceRef.current !== request.sequence) return;
    setAgentSettings(settings);
    if (settingsRequestIsCurrent(request, { apiBase: activeApiBaseRef.current, sequence: settingsRequestSequenceRef.current, revision: settingsEditRevisionRef.current })) {
      setAgentForm(settingsToForm(settings)); setApiKeyInput(""); setClearApiKey(false);
    }
    setNotice(uiText.notices.settingsSaved);
  }, [agentForm, agentSettings, apiBase, apiKeyInput, clearApiKey]);

  const refreshBackendVersion = useCallback(async () => {
    const sequence = ++backendVersionSequenceRef.current;
    const requestApiBase = apiBase;
    setBackendVersionState({ apiBase: requestApiBase, value: { version: null, source: "unknown" } });
    const value = await readBackendVersion(async (path) => {
      const controller = new AbortController();
      const timeout = window.setTimeout(() => controller.abort(), 4000);
      try {
        const response = await fetch(`${requestApiBase}${path}`, { signal: controller.signal });
        if (!response.ok) throw new Error(`Version metadata HTTP ${response.status}`);
        return await response.json();
      } finally { window.clearTimeout(timeout); }
    });
    if (backendVersionRequestIsCurrent(sequence, backendVersionSequenceRef.current, requestApiBase, activeApiBaseRef.current)) {
      setBackendVersionState({ apiBase: requestApiBase, value });
    }
    return value;
  }, [apiBase]);

  const checkForUpdates = useCallback(async (silent = false) => {
    if (updateInProgressRef.current) return;
    await refreshBackendVersion();
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
  }, [refreshBackendVersion]);

  const createProject = useCallback(async () => {
    if (!projectForm.title.trim()) {
      throw new Error(uiText.errors.projectNameRequired);
    }
    const result = await apiPost<{ project_id: string }>(apiBase, "/projects", {
      title: projectForm.title.trim(),
      genre: projectForm.genre.trim() || (await loadLocaleCatalog(projectForm.language)).contentDefaults.genre,
      language: normalizeAppLocale(projectForm.language),
      target_length: projectForm.target_length.trim() || null,
      narrative_pov:
        projectForm.narrative_pov.trim() ||
        (await loadLocaleCatalog(projectForm.language)).contentDefaults.narrativePov
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
    if (!chapterEditorMatches(chapterMetadataTarget, apiBase, projectId)) throw new Error(uiText.errors.chooseChapterForEdit);
    const targetChapterId = chapterMetadataTarget!.chapterId;
    if (!chapterForm.title.trim()) throw new Error(uiText.errors.chapterTitleRequired);
    await apiPatch<GraphNodePayload>(apiBase, `/projects/${projectId}/chapters/${targetChapterId}`, {
      ...Object.fromEntries(Object.entries(changedMetadataFields(chapterForm, chapterMetadataTarget!.baseline)).map(([key, value]) => [key, key === "volume_index" || key === "chapter_index" ? toPositiveInteger(value, 1) : value?.trim() || null])),
      reviewer: "author",
      rationale: auditText.updateChapter,
      source_ref: "author_seed:workbench_chapter_metadata"
    });
    await refreshWorkspace(projectId, sceneId);
    await refreshGraphPreview(projectId);
    setChapterMetadataTarget((current) => current?.chapterId === targetChapterId && chapterEditorMatches(current, apiBase, projectId) ? { ...current, baseline: { ...chapterForm } } : current);
    setNotice(uiText.notices.chapterUpdated);
  }, [
    apiBase,
    chapterForm,
    chapterMetadataTarget,
    projectId,
    refreshGraphPreview,
    refreshWorkspace,
    sceneId
  ]);

  const saveChapterTitle = useCallback(async () => {
    if (!chapterTitleEditor) return;
    const update = chapterTitleUpdate(chapterTitleEditor, apiBase, projectId);
    await apiPatch(apiBase, update.path, update.body);
    setChapterTitleEditor((current) => current?.chapterId === chapterTitleEditor.chapterId ? { ...current, originalTitle: update.body.title, title: update.body.title } : current);
    await refreshWorkspace(projectId, sceneId);
    setNotice(uiText.notices.chapterUpdated);
  }, [apiBase, chapterTitleEditor, projectId, refreshWorkspace, sceneId]);

  const saveSceneTitle = useCallback(async () => {
    const editor = sceneTitleEditor;
    if (!editor || editor.apiBase !== apiBase || editor.projectId !== projectId || !editor.title.trim()) throw new Error(uiText.errors.selectScene);
    await apiPatch(apiBase, `/projects/${encodeURIComponent(editor.projectId)}/scenes/${encodeURIComponent(editor.sceneId)}`, {
      title: editor.title.trim(), reviewer: "author", rationale: "workbench.scene.rename", source_ref: "author_seed:workbench_scene_title"
    });
    setSceneTitleEditor(null);
    await refreshWorkspace(projectId, sceneId);
    setNotice(uiText.notices.sceneUpdated);
  }, [apiBase, projectId, refreshWorkspace, sceneId, sceneTitleEditor]);

  const discardChapterEditors = useCallback(() => {
    if ((chapterEditsDirty || sceneEditsDirty) && !window.confirm(uiText.authorWorkspace.discardMetadataEdits)) return false;
    setSceneTitleEditor(null);
    setSceneMetadataTarget(null);
    setSceneForm(defaultSceneForm);
    setChapterTitleEditor(null);
    setChapterMetadataTarget(null);
    setChapterForm(defaultChapterForm);
    return true;
  }, [chapterEditsDirty, sceneEditsDirty]);

  const loadChapterMetadata = useCallback((chapter: ChapterOutline) => {
    if (actionInFlightRef.current) return;
    if (chapterEditsDirty && !window.confirm(uiText.authorWorkspace.discardMetadataEdits)) return;
    const form = chapterToForm(chapter);
    setChapterTitleEditor(null);
    setChapterForm(form);
    setChapterMetadataTarget({ apiBase, projectId, chapterId: chapter.id, baseline: form });
  }, [apiBase, chapterEditsDirty, projectId]);

  const loadSceneMetadata = useCallback((scene: SceneOutline) => {
    if (actionInFlightRef.current) return;
    if (sceneEditsDirty && !window.confirm(uiText.authorWorkspace.discardMetadataEdits)) return;
    const form = sceneToForm(scene, findSceneChapterId(projects, projectId, scene.id) ?? "");
    setSceneTitleEditor(null);
    setSceneForm(form);
    setSceneMetadataTarget({ apiBase, projectId, sceneId: scene.id, baseline: form });
  }, [apiBase, projectId, projects, sceneEditsDirty]);

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
    setChapterMetadataTarget(null);
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
    setSceneMetadataTarget(null);
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
    const target = sceneMetadataTarget;
    if (!target || target.apiBase !== apiBase || target.projectId !== projectId || target.sceneId !== sceneId) throw new Error(uiText.errors.chooseSceneForEdit);
    if (!sceneForm.title.trim()) throw new Error(uiText.errors.sceneTitleRequired);
    await apiPatch<GraphNodePayload>(apiBase, `/projects/${encodeURIComponent(target.projectId)}/scenes/${encodeURIComponent(target.sceneId)}`, {
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
    setSceneMetadataTarget((current) => current?.apiBase === target.apiBase && current.projectId === target.projectId && current.sceneId === target.sceneId ? { ...current, baseline: { ...sceneForm } } : current);
    setContextPack(null);
    setNotice(uiText.notices.sceneUpdated);
  }, [
    apiBase,
    projectId,
    refreshGraphPreview,
    refreshWorkspace,
    sceneForm,
    sceneMetadataTarget,
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
        summary: `${(await loadLocaleCatalog(selectedProject?.language)).ui.library.importedDraftSummaryPrefix}${document.title}`
      });
      draftEditorScopeRef.current = { apiBase, projectId, sceneId };
      draftEditRevisionRef.current += 1;
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
        summary: `${(await loadLocaleCatalog(selectedProject?.language)).ui.library.importedStyleSummaryPrefix}${document.title}`
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
      if (!proposalDirty) {
        setCreatingNewProposal(false);
        setSelectedProposalId(result.proposal.id);
        setWorkspaceTab("proposals");
      }
      const sceneCount = result.outline.chapters.reduce(
        (total, chapter) => total + chapter.scenes.length,
        0
      );
      setNotice(
        proposalDirty
          ? uiText.notices.proposalCreatedNotOpened(result.proposal.id)
          : uiText.notices.sourceStructureCreated(
            result.outline.chapters.length,
            sceneCount,
            result.truncated
          )
      );
    },
    [apiBase, crossLanguagePolicy, projectId, proposalDirty, refreshProposals, selectedProject]
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
          title: `${(await loadLocaleCatalog(selectedProject?.language)).ui.library.importedProposalTitlePrefix}${document.title}`,
          body: sourceText,
          target_refs: [{ kind: "scene", ref: sceneId }],
          source_refs: [{ kind: "source_document", ref: document.id, note: document.title }],
          created_by: "author",
          created_via: "import",
          provenance_note: `${(await loadLocaleCatalog(selectedProject?.language)).ui.library.importedProposalNotePrefix}${document.title}`
        }
      );
      await refreshProposals(projectId);
      if (!proposalDirty) {
        setCreatingNewProposal(false);
        setSelectedProposalId(proposal.id);
        setWorkspaceTab("proposals");
      }
      setNotice(
        proposalDirty
          ? uiText.notices.proposalCreatedNotOpened(proposal.id)
          : uiText.notices.sourceSavedAsProposal(document.title)
      );
    },
    [apiBase, projectId, proposalDirty, refreshProposals, sceneId, selectedProject]
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
      await refreshSources(projectId);
      setSelectedSourceDocumentId(updated.id);
    },
    [apiBase, projectId, refreshSources]
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
    if (draftLoading || !draftEditorScopeRef.current || !draftScopesMatch(draftEditorScopeRef.current, { apiBase, projectId, sceneId })) throw new Error(uiText.errors.agentDraftScopeMismatch);
    if (!endpoint) throw new Error(uiText.errors.selectScene);
    const request = { scope: { apiBase, projectId, sceneId }, sequence: ++draftRequestSequenceRef.current, editorRevision: draftEditRevisionRef.current };
    const saved = await apiPost<Draft>(apiBase, `${endpoint}/draft`, {
      text: draftText,
      summary: draftSummary
    });
    const completion = draftSaveCompletionPolicy(request, {
      scope: { apiBase: activeApiBaseRef.current, projectId: activeProjectIdRef.current, sceneId: activeSceneIdRef.current },
      sequence: draftRequestSequenceRef.current, editorRevision: draftEditRevisionRef.current
    });
    if (!completion.applySavedDraft) return false;
    draftEditorScopeRef.current = request.scope;
    setDraft(saved);
    if (completion.replaceEditor) {
      setDraftText(saved.text);
      setDraftSummary(saved.summary ?? "");
      draftDirtyRef.current = false;
    }
    setNotice(completion.replaceEditor ? uiText.runtime.draftSaved(saved.version) : uiText.navigation.editsDuringSave);
    setWorkspaceTab("write");
    return completion.continueNavigation;
  }, [apiBase, draftLoading, draftSummary, draftText, endpoint, projectId, sceneId]);

  const readDraftSelection = useCallback((target: HTMLTextAreaElement | null) => {
    if (!target) {
      return "";
    }
    const selection = target.value.slice(target.selectionStart, target.selectionEnd);
    return selection;
  }, []);

  const captureDraftSelection = useCallback((event: React.SyntheticEvent<HTMLTextAreaElement>) => {
    const target = event.currentTarget;
    const text = readDraftSelection(target);
    setDraftSelection(text);
    setDraftSelectionRange(text.trim() ? { text, start: target.selectionStart, end: target.selectionEnd } : null);
  }, [readDraftSelection]);

  const refreshDraftSelection = useCallback(() => {
    const selection = readDraftSelection(draftTextareaRef.current);
    setDraftSelection(selection);
    const target = draftTextareaRef.current;
    setDraftSelectionRange(selection.trim() && target ? { text: selection, start: target.selectionStart, end: target.selectionEnd } : null);
    return selection;
  }, [readDraftSelection]);

  const handleDraftTextChange = useCallback((event: React.ChangeEvent<HTMLTextAreaElement>) => {
    draftEditRevisionRef.current += 1;
    draftDirtyRef.current = true;
    setDraftText(event.target.value);
    setDraftSelection("");
    setDraftSelectionRange(null);
    setAgentDiscussionForm((current) => ({ ...current, selectedText: "", selectedStart: undefined, selectedEnd: undefined, selectedDraftId: undefined }));
  }, [readDraftSelection]);

  const handleDraftSummaryChange = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    draftEditRevisionRef.current += 1;
    draftDirtyRef.current = true;
    setDraftSummary(event.target.value);
  }, []);

  const restoreSavedDraft = useCallback(() => {
    if (!draft || !window.confirm(uiText.agentDiscussion.restoreDraftConfirm)) return;
    draftEditRevisionRef.current += 1;
    setDraftText(draft.text);
    setDraftSummary(draft.summary ?? "");
    setDraftSelection("");
    setDraftSelectionRange(null);
    setAgentDiscussionForm((current) => ({ ...current, selectedText: "", selectedStart: undefined, selectedEnd: undefined, selectedDraftId: undefined }));
    setNotice(uiText.notices.savedDraftRestored(draft.id, draft.version));
  }, [draft]);

  const useDraftSelectionForAgent = useCallback(() => {
    const selection = draftSelection;
    if (!selection.trim() || !draftSelectionRange) { setNotice(uiText.notices.draftSelectionRequired); return; }
    setAgentDiscussionForm((current) => ({
      ...current, mode: "discuss", selectedText: selection, selectedStart: draftSelectionRange.start,
      selectedEnd: draftSelectionRange.end, selectedDraftId: draft?.id, includeLatestDraft: true
    }));
    setAgentTarget("scene"); setWorkspaceTab("write"); setActiveTab("agent");
  }, [draftSelection, draftSelectionRange, draft]);

  const beginSceneDraft = useCallback(() => {
    setAgentTarget("scene");
    setAgentDiscussionForm((current) => ({ ...current, mode: "create_scene", selectedText: "", selectedStart: undefined, selectedEnd: undefined, selectedDraftId: undefined, includeLatestDraft: false, includeContextPack: true }));
    setActiveTab("agent");
  }, []);

  const requestAgentDiscussion = useCallback(async () => {
    if (!endpoint || !projectId) throw new Error(uiText.errors.selectScene);
    const instruction = agentDiscussionForm.instruction.trim();
    if (!instruction) throw new Error(uiText.errors.agentInstructionRequired);
    const selectedText = agentDiscussionForm.selectedText;
    if (selectedText && agentDiscussionForm.selectedDraftId && agentDiscussionForm.selectedDraftId !== draft?.id) throw new Error(uiText.manuscript.selectionChanged);
    if (agentDiscussionForm.mode === "revise_selection" && !selectedText) {
      throw new Error(uiText.errors.agentSelectionRequired);
    }
    const includedDraft = agentIncludedDraftPolicy(
      draft,
      agentDiscussionForm.includeLatestDraft,
      draftDirty,
      projectId,
      sceneId
    );
    if (agentDiscussionForm.includeLatestDraft && includedDraft.status !== "ready") {
      throw new Error(
        includedDraft.status === "blocked_scope"
          ? uiText.errors.agentDraftScopeMismatch
          : uiText.errors.agentIncludedDraftMustBeSaved
      );
    }
    if (
      agentDiscussionForm.mode !== "discuss" && agentDiscussionForm.mode !== "create_scene" &&
      !agentDiscussionForm.includeLatestDraft
    ) {
      throw new Error(uiText.errors.agentRevisionRequiresSavedDraft);
    }
    const projectLanguage = outputLanguageOrNull(selectedProject?.language);
    const selectedSourceList = Array.from(selectedAgentSourceIds).map((sourceId) =>
      sourceDocuments.find((source) => source.id === sourceId)
    );
    if (
      selectedSourceList.some(
        (source) => !source || sourceAgentEligibility(
          source,
          projectLanguage,
          crossLanguagePolicy
        ) !== "eligible"
      )
    ) {
      throw new Error(uiText.errors.agentSourcesBlockedByPolicy);
    }
    const payload: AgentDiscussionRequest = {
      mode: agentDiscussionForm.mode,
      instruction,
      selected_text: agentDiscussionForm.includeLatestDraft ? selectedText || null : null,
      selected_start: agentDiscussionForm.includeLatestDraft && selectedText ? agentDiscussionForm.selectedStart ?? null : null,
      selected_end: agentDiscussionForm.includeLatestDraft && selectedText ? agentDiscussionForm.selectedEnd ?? null : null,
      base_text: null,
      include_context_pack: agentDiscussionForm.includeContextPack,
      include_latest_draft: agentDiscussionForm.includeLatestDraft,
      included_draft_id: includedDraft.status === "ready" ? includedDraft.draftId : null,
      local_sources: [],
      source_document_ids: Array.from(selectedAgentSourceIds),
      allow_web_search: agentDiscussionForm.allowWebSearch,
      web_search_query: agentDiscussionForm.webSearchQuery.trim() || null,
      cross_language_policy: crossLanguagePolicy
    };
    const target = { apiBase, projectId, sceneId };
    const currentScope = () => activeApiBaseRef.current === target.apiBase && activeProjectIdRef.current === target.projectId && activeSceneIdRef.current === target.sceneId;
    const result = await apiPost<AgentDiscussionResult>(
      apiBase,
      `${endpoint}/agent-discussion`,
      payload
    );
    if (!currentScope()) return;
    setAgentDiscussionResult(result);
    const refreshed = await refreshProposals(projectId);
    if (!currentScope()) return;
    const created = refreshed.find((proposal) => proposal.id === result.proposal.id);
    if (!proposalDirty) {
      setCreatingNewProposal(false);
      setSelectedProposalId(created?.id ?? result.proposal.id);
    }
    setWorkspaceTab(result.proposal.artifact_type === "scene_draft" && !proposalDirty ? "proposals" : "write"); setActiveTab("agent");
    setNotice(
      proposalDirty
        ? uiText.notices.proposalCreatedNotOpened(result.proposal.id)
        : result.proposal.artifact_type === "scene_draft"
          ? uiText.notices.agentSceneDraftCreated
          : uiText.notices.agentDiscussionCreated
    );
  }, [
    agentDiscussionForm,
    apiBase,
    draft,
    draftDirty,
    endpoint,
    projectId,
    proposalDirty,
    refreshProposals,
    selectedProject,
    selectedAgentSourceIds,
    sourceDocuments,
    crossLanguagePolicy
  ]);

  const generateDraft = useCallback(async () => {
    if (!endpoint) throw new Error(uiText.errors.selectScene);
    const saved = await apiPost<Draft>(apiBase, `${endpoint}/draft`);
    const pack = await apiPost<ContextPack>(apiBase, `${endpoint}/context-pack`);
    setContextPack(pack);
    draftEditorScopeRef.current = { apiBase, projectId, sceneId };
    draftEditRevisionRef.current += 1;
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
    draftEditorScopeRef.current = { apiBase, projectId, sceneId };
    draftEditRevisionRef.current += 1;
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

  const startNewProposal = useCallback(async () => {
    const contentLanguage = outputLanguageOrNull(selectedProject?.language);
    const contentCatalog = await loadLocaleCatalog(contentLanguage);
    if (activeProjectIdRef.current !== projectId) return;
    proposalEditorSnapshotRef.current = null;
    selectedProposalStableRef.current = null;
    setCreatingNewProposal(true);
    setSelectedProposalId(null);
    setProposalArtifactType("scene_draft");
    setProposalTitle(
      selectedScene && contentLanguage
        ? `${selectedScene.title} ${contentCatalog.contentDefaults.proposalSuffix}`
        : ""
    );
    setProposalText("");
    setProposalSourceDraftId(draft?.id ?? "");
  }, [draft, projectId, selectedProject, selectedScene]);

  const saveProposal = useCallback(async () => {
    if (!projectId) throw new Error(uiText.errors.selectProjectOrCreate);
    const contentLanguage = outputLanguageOrNull(selectedProject?.language);
    if (!contentLanguage) throw new Error(uiText.errors.projectLanguageRequired);
    const title =
      proposalTitle.trim() ||
      (await loadLocaleCatalog(contentLanguage)).contentDefaults.untitledProposal;
    const body = proposalText;
    if (selectedProposal) {
      if (!proposalActionPolicy(
        selectedProposal.status,
        proposalDirty,
        selectedProposal.artifact_type
      ).editable) throw new Error(uiText.errors.proposalActionUnavailable);
      const saved = await apiPatch<ProposalArtifact>(
        apiBase,
        `/projects/${projectId}/proposals/${selectedProposal.id}`,
        {
          title,
          body,
          expected_version: selectedProposal.version
        }
      );
      proposalEditorSnapshotRef.current = {
        id: saved.id,
        version: saved.version,
        title: saved.title,
        body: saved.body
      };
      selectedProposalStableRef.current = saved;
      await refreshProposals(projectId);
      setCreatingNewProposal(false);
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
    proposalEditorSnapshotRef.current = {
      id: saved.id,
      version: saved.version,
      title: saved.title,
      body: saved.body
    };
    selectedProposalStableRef.current = saved;
    setCreatingNewProposal(false);
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
    proposalDirty,
    refreshProposals,
    sceneId,
    selectedProject,
    selectedProposal
  ]);

  const requestProposalNavigation = useCallback(
    (label: string, action: () => void, onCancel?: () => void) => {
      if (actionInFlightRef.current) { onCancel?.(); return; }
      if ((chapterEditsDirty || sceneEditsDirty) && !discardChapterEditors()) { onCancel?.(); return; }
      if (!proposalDirty && !draftDirty) {
        action();
        return;
      }
      pendingProposalNavigationRef.current = action;
      pendingNavigationCancelRef.current = onCancel ?? null;
      setPendingProposalNavigation({ label, kind: proposalDirty ? "proposal" : "draft" });
    },
    [chapterEditsDirty, sceneEditsDirty, discardChapterEditors, proposalDirty, draftDirty]
  );

  const cancelProposalNavigation = useCallback(() => {
    pendingNavigationCancelRef.current?.();
    pendingNavigationCancelRef.current = null;
    pendingProposalNavigationRef.current = null;
    setPendingProposalNavigation(null);
  }, []);

  const finishEditorNavigation = useCallback(() => {
    if (pendingProposalNavigation?.kind === "proposal" && draftDirtyRef.current) {
      setPendingProposalNavigation((current) => current ? { ...current, kind: "draft" } : null);
      return;
    }
    const action = pendingProposalNavigationRef.current;
    pendingProposalNavigationRef.current = null;
    pendingNavigationCancelRef.current = null;
    setPendingProposalNavigation(null);
    action?.();
  }, [pendingProposalNavigation]);

  const discardProposalAndNavigate = useCallback(() => {
    if (pendingProposalNavigation?.kind === "draft") {
      draftEditRevisionRef.current += 1;
      draftDirtyRef.current = false;
      setDraftText(draft?.text ?? "");
      setDraftSummary(draft?.summary ?? "");
    } else {
      hydrateProposalEditor(selectedProposal);
      setCreatingNewProposal(false);
    }
    finishEditorNavigation();
  }, [draft, finishEditorNavigation, hydrateProposalEditor, pendingProposalNavigation, selectedProposal]);

  const saveProposalAndNavigate = useCallback(async () => {
    const action = finishEditorNavigation;
    await continueAfterSuccessfulSave(
      async () => {
        let saved = false;
        await runAction("proposal-save-navigation", async () => {
          if (pendingProposalNavigation?.kind === "draft") {
            saved = await saveDraft();
          } else {
            await saveProposal();
            saved = true;
          }
        });
        return saved;
      },
      () => { action?.(); }
    );
  }, [finishEditorNavigation, pendingProposalNavigation, runAction, saveDraft, saveProposal]);

  const installAvailableUpdate = useCallback(async () => {
    if (updateInProgressRef.current || actionInFlightRef.current) return;
    const update = desktopUpdate;
    if (!update) {
      setUpdateStatus({ state: "error", channel: "desktop", message: () => uiText.runtime.noInstallableUpdate });
      return;
    }
    updateInProgressRef.current = true;
    let installed = false;
    let managedBeforePrepare = false;
    const unlockAction = () => { actionInFlightRef.current = false; setBusy(null); };
    try {
      const result = await runSafeDesktopUpdate({
        download: async () => {
          actionInFlightRef.current = true;
          setBusy("update-download");
          setUpdateStatus({ state: "downloading", channel: "desktop", message: () => uiText.runtime.updateDownloading(update.version), latestVersion: update.version });
          try { await update.download(); }
          finally { unlockAction(); }
        },
        confirmSaved: () => {
          setUpdateStatus({ state: "awaiting_edits", channel: "desktop", message: () => uiText.runtime.updateAwaitingEdits, latestVersion: update.version });
          return new Promise<boolean>((resolve) => {
            requestProposalNavigation(uiText.runtime.updateInstallDestination, () => resolve(true), () => resolve(false));
          });
        },
        prepare: async () => {
          if (actionInFlightRef.current) throw new Error("Another workspace action is still running.");
          actionInFlightRef.current = true;
          setBusy("update-install");
          setUpdateStatus({ state: "installing", channel: "desktop", message: () => uiText.runtime.installingUpdate(update.version), latestVersion: update.version });
          const status = await invoke<DesktopBackendStatus>("backend_status");
          managedBeforePrepare = status.managed;
          await invoke("prepare_backend_update");
        },
        install: () => update.install(),
        cancel: () => invoke<void>("cancel_backend_update"),
        get restoreManagedBackend() {
          return managedBeforePrepare ? async () => {
            const status = await invoke<DesktopBackendStatus>("start_backend");
            setDesktopBackend(status);
            setDesktopBackendChecked(true);
            if (!status.reachable || !status.workspaceCompatible) throw new Error(status.error ?? "Managed backend recovery did not become ready.");
          } : null;
        }
      });
      if (result === "cancelled") {
        setUpdateStatus({ state: "available", channel: "desktop", message: () => uiText.runtime.updateDownloaded(update.version), latestVersion: update.version, canInstall: true });
        return;
      }
      installed = true;
      setUpdateStatus({ state: "installing", channel: "desktop", message: () => uiText.runtime.installedRestarting, latestVersion: update.version });
      const { relaunch } = await import("@tauri-apps/plugin-process");
      await relaunch();
    } catch (error) {
      if (installed) {
        setUpdateStatus({ state: "error", channel: "desktop", message: () => uiText.runtime.installedManualRestart, technicalDetails: technicalErrorMessage(error), latestVersion: update.version, canInstall: false });
        return;
      }
      const failure = error instanceof DesktopUpdateFailure ? error : null;
      const fileLocked = isWindowsUpdateFileLock(failure?.cause ?? error);
      setUpdateStatus({
        state: "error", channel: "desktop", latestVersion: update.version,
        message: () => [
          failure?.stage === "download" ? uiText.runtime.updateDownloadFailed : failure?.stage === "preparation" ? uiText.runtime.updatePreparationFailed : uiText.runtime.updateInstallFailed,
          failure?.recovery === "restored" ? uiText.runtime.backendRecovered : failure?.recovery === "restore_failed" ? uiText.runtime.backendRecoveryFailed : failure?.recovery === "cancel_failed" ? uiText.runtime.updateCancelFailed : failure?.recovery === "external_untouched" ? uiText.runtime.updateExternalUntouched : "",
          fileLocked ? uiText.runtime.updateFileLockHelp : ""
        ].filter(Boolean).join(" "),
        technicalDetails: [technicalErrorMessage(failure?.cause ?? error), failure?.recoveryError ? technicalErrorMessage(failure.recoveryError) : null].filter(Boolean).join("\n"),
        releaseUrl: fileLocked ? `https://github.com/${GITHUB_REPOSITORY}/releases/latest` : undefined,
        canInstall: failure?.canRetry ?? true
      });
      void refreshBackendVersion();
    } finally {
      updateInProgressRef.current = false;
      unlockAction();
    }
  }, [desktopUpdate, refreshBackendVersion, requestProposalNavigation]);

  const adoptSourceSelection = useCallback(async (document: SourceDocument, range: ManuscriptSelection) => {
    if (!projectId || !sceneId || document.project_id !== projectId || draftDirtyRef.current) throw new Error(uiText.errors.agentIncludedDraftMustBeSaved);
    const target = { apiBase, projectId, sceneId };
    const currentScope = () => activeApiBaseRef.current === target.apiBase && activeProjectIdRef.current === target.projectId && activeSceneIdRef.current === target.sceneId;
    if (!currentScope()) return;
    if (draftLoading || !draftEditorScopeRef.current || !draftScopesMatch(draftEditorScopeRef.current, target)) throw new Error(uiText.errors.agentDraftScopeMismatch);
    const current = currentDraftRef.current;
    const editorRevision = draftEditRevisionRef.current;
    const saved = await apiPost<Draft>(apiBase, `/projects/${projectId}/scenes/${sceneId}/draft/from-source`, {
      source_document_id: document.id, expected_source_updated_at: document.updated_at, expected_source_checksum: document.checksum_sha256,
      start: range.start, end: range.end, expected_text: range.text, expected_current_draft_id: current?.id ?? null
    });
    if (!currentScope() || draftEditRevisionRef.current !== editorRevision || draftDirtyRef.current) return;
    draftRequestSequenceRef.current += 1; draftEditRevisionRef.current += 1;
    draftEditorScopeRef.current = target; setDraft(saved); setDraftText(saved.text); setDraftSummary(saved.summary ?? "");
    setDraftSelection(""); setDraftSelectionRange(null); setReadingChapterId(null); setManuscriptMode("preview"); setWorkspaceTab("write");
    setNotice(uiText.runtime.draftSaved(saved.version));
  }, [apiBase, projectId, sceneId, draftLoading]);

  const generateComposition = useCallback(async (input: CompositionInput) => {
    if (!projectId) throw new Error(uiText.errors.selectProject);
    const target = { apiBase, projectId };
    const currentScope = () => activeApiBaseRef.current === target.apiBase && activeProjectIdRef.current === target.projectId;
    if (!currentScope()) return;
    const { include_current_draft, include_selected_sources, ...request } = input;
    const sourceIds = include_selected_sources ? Array.from(selectedAgentSourceIds) : [];
    if (sourceIds.length > 8 || sourceIds.some((id) => { const source = sourceDocuments.find((item) => item.id === id); return !source || sourceAgentEligibility(source, outputLanguageOrNull(selectedProject?.language), crossLanguagePolicy) !== "eligible"; })) throw new Error(uiText.errors.agentSourcesBlockedByPolicy);
    if (include_current_draft && (!draft || draftDirty || draft.project_id !== projectId || draft.scene_id !== sceneId)) throw new Error(uiText.errors.agentIncludedDraftMustBeSaved);
    const result = await apiPost<{ proposal: ProposalArtifact; output_language: string }>(apiBase, `/projects/${encodeURIComponent(projectId)}/composition-proposals`, { ...request, source_document_ids: sourceIds, cross_language_policy: crossLanguagePolicy, ...(include_current_draft && draft ? { scene_id: sceneId, included_draft_id: draft.id } : {}) });
    if (!currentScope()) return;
    await refreshProposals(projectId);
    if (!currentScope()) return;
    setProposalStatusFilter("all"); setCreatingNewProposal(false); setSelectedProposalId(result.proposal.id);
    hydrateProposalEditor(result.proposal); setWorkspaceTab("proposals"); setNotice(uiText.manuscript.compositionCreated);
  }, [apiBase, projectId, sceneId, draft, draftDirty, selectedAgentSourceIds, sourceDocuments, selectedProject, crossLanguagePolicy, refreshProposals, hydrateProposalEditor]);

  const applyCompositionProposal = useCallback(async () => {
    if (!selectedProposal || !parseComposition(selectedProposal) || proposalDirty || selectedProposal.status !== "accepted") throw new Error(uiText.errors.proposalActionUnavailable);
    const target = { apiBase, projectId };
    const currentScope = () => activeApiBaseRef.current === target.apiBase && activeProjectIdRef.current === target.projectId;
    if (!currentScope()) return;
    const result = await apiPost<{ proposal: ProposalArtifact; chapters: GraphNodePayload[]; scenes: GraphNodePayload[]; drafts: Draft[]; already_applied: boolean }>(apiBase, `/projects/${encodeURIComponent(projectId)}/proposals/${encodeURIComponent(selectedProposal.id)}/apply/composition`, { expected_version: selectedProposal.version, reviewer: "author", rationale: "workbench.composition.apply" });
    if (!currentScope()) return;
    await refreshWorkspace(projectId, sceneId); await refreshGraphPreview(projectId); await refreshProposals(projectId);
    if (!currentScope()) return;
    setCreatingNewProposal(false); setSelectedProposalId(result.proposal.id); hydrateProposalEditor(result.proposal);
    if (result.chapters[0]) { setReadingChapterId(result.chapters[0].id); setChapterSelection({ projectId, id: result.chapters[0].id }); setWorkspaceTab("write"); setAgentTarget("composition"); }
    setNotice(uiText.manuscript.compositionApplied);
  }, [apiBase, projectId, sceneId, selectedProposal, proposalDirty, refreshWorkspace, refreshGraphPreview, refreshProposals, hydrateProposalEditor]);

  const generateOutlineLanguageProposal = useCallback(async () => {
    if (!projectId) throw new Error(uiText.errors.selectProject);
    const target = { apiBase, projectId };
    const currentScope = () => outlineLanguageScopeMatches(target, activeApiBaseRef.current, activeProjectIdRef.current);
    if (!currentScope()) throw new Error(uiText.errors.outlineLanguageScopeChanged);
    let result: { proposal: ProposalArtifact; output_language: string; change_count: number };
    try {
      result = await apiPost(apiBase, `/projects/${encodeURIComponent(projectId)}/outline/localization-proposal`, {});
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 403) throw new Error(uiText.errors.outlineLanguagePermission);
      throw error;
    }
    if (!currentScope()) return;
    await refreshProposals(projectId);
    if (!currentScope()) return;
    setProposalStatusFilter("all");
    setCreatingNewProposal(false);
    setSelectedProposalId(result.proposal.id);
    hydrateProposalEditor(result.proposal);
    setWorkspaceTab("proposals");
    setNotice(uiText.outlineLanguage.generated(result.change_count));
  }, [apiBase, projectId, refreshProposals, hydrateProposalEditor]);

  const applyOutlineLanguageProposal = useCallback(async () => {
    const proposal = selectedProposal;
    const target = { apiBase, projectId };
    const currentScope = () => outlineLanguageScopeMatches(target, activeApiBaseRef.current, activeProjectIdRef.current);
    if (!currentScope()) throw new Error(uiText.errors.outlineLanguageScopeChanged);
    if (!canApplyOutlineLanguagePatch(proposal, proposalDirty, projectId)) throw new Error(uiText.errors.proposalActionUnavailable);
    let result: { proposal: ProposalArtifact; applied_count: number; already_applied: boolean };
    try {
      result = await apiPost(apiBase, `/projects/${encodeURIComponent(projectId)}/proposals/${encodeURIComponent(proposal!.id)}/apply/outline-language`, {
        expected_version: proposal!.version, reviewer: "author", rationale: "workbench.outline_language.apply"
      });
    } catch (error) {
      if (error instanceof ApiRequestError && error.status === 403) throw new Error(uiText.errors.outlineLanguagePermission);
      throw error;
    }
    if (!currentScope()) return;
    // Refresh only outline/proposal/graph metadata; leave the current Draft and
    // its editor version untouched, including when returning from another tab.
    const [workspace, preview] = await Promise.all([
      apiGet<{ projects: ProjectOutline[] }>(apiBase, "/projects"),
      apiGet<ProjectGraphPreview>(apiBase, `/projects/${encodeURIComponent(projectId)}/graph/preview`)
    ]);
    if (!currentScope()) return;
    setProjects(workspace.projects);
    setGraphPreview(preview);
    setContextPack(null);
    if (metadataEditorsRef.current.chapterEditing && !metadataEditorsRef.current.chapterDirty) {
      setChapterTitleEditor(null);
      setChapterMetadataTarget(null);
      setChapterForm(defaultChapterForm);
    }
    if (metadataEditorsRef.current.sceneEditing && !metadataEditorsRef.current.sceneDirty) {
      setSceneTitleEditor(null);
      setSceneMetadataTarget(null);
      setSceneForm(defaultSceneForm);
    }
    await refreshProposals(projectId);
    if (!currentScope()) return;
    setCreatingNewProposal(false);
    setSelectedProposalId(result.proposal.id);
    hydrateProposalEditor(result.proposal);
    setNotice(uiText.outlineLanguage.applied(result.applied_count, result.already_applied));
  }, [apiBase, projectId, proposalDirty, selectedProposal, refreshProposals, hydrateProposalEditor]);

  const submitProposalReview = useCallback(async () => {
    if (!selectedProposal || !projectId) throw new Error(uiText.errors.selectProposal);
    if (!proposalActionPolicy(
      selectedProposal.status,
      proposalDirty,
      selectedProposal.artifact_type
    ).canSubmit) throw new Error(uiText.errors.proposalActionUnavailable);
    const saved = await apiPost<ProposalArtifact>(
      apiBase,
      `/projects/${projectId}/proposals/${selectedProposal.id}/submit-review`,
      { expected_version: selectedProposal.version }
    );
    await refreshProposals(projectId);
    setCreatingNewProposal(false);
    setSelectedProposalId(saved.id);
    setNotice(uiText.runtime.proposalSubmitted(saved.id));
  }, [apiBase, projectId, proposalDirty, refreshProposals, selectedProposal]);

  const reviewProposal = useCallback(
    async (decision: "accept" | "reject") => {
      if (!selectedProposal || !projectId) throw new Error(uiText.errors.selectProposal);
      if (!proposalActionPolicy(
        selectedProposal.status,
        proposalDirty,
        selectedProposal.artifact_type
      ).canDecide) throw new Error(uiText.errors.proposalActionUnavailable);
      const saved = await apiPost<ProposalArtifact>(
        apiBase,
        `/projects/${projectId}/proposals/${selectedProposal.id}/${decision}`,
        { reviewer: "author", expected_version: selectedProposal.version }
      );
      await refreshProposals(projectId);
      setCreatingNewProposal(false);
      setSelectedProposalId(saved.id);
      setNotice(uiText.runtime.proposalDecided(decision === "accept"));
    },
    [apiBase, projectId, proposalDirty, refreshProposals, selectedProposal]
  );

  const promoteProposalToDraft = useCallback(async () => {
    if (!selectedProposal || !projectId || !sceneId) throw new Error(uiText.errors.selectSceneAndProposal);
    if (!proposalActionPolicy(
      selectedProposal.status,
      proposalDirty,
      selectedProposal.artifact_type
    ).canPromote || selectedProposal.artifact_type !== "scene_draft") {
      throw new Error(uiText.errors.proposalActionUnavailable);
    }
    if (proposalDerivedDraftRef.status !== "none") {
      throw new Error(
        proposalDerivedDraftRef.status === "ambiguous"
          ? uiText.errors.proposalDerivedDraftAmbiguous
          : uiText.errors.proposalAlreadyPromoted
      );
    }
    if (proposalTarget.status !== "ready") {
      throw new Error(
        proposalTarget.status === "ambiguous"
          ? uiText.errors.proposalTargetAmbiguous
          : proposalTarget.status === "missing_scene"
            ? uiText.errors.proposalTargetMissing
            : uiText.errors.proposalTargetMismatch
      );
    }
    const target = { apiBase, projectId, sceneId };
    if (draftLoading || draftDirtyRef.current || !draftEditorScopeRef.current || !draftScopesMatch(draftEditorScopeRef.current, target)) throw new Error(uiText.errors.agentIncludedDraftMustBeSaved);
    const currentDraft = currentDraftRef.current;
    const baseline = resolveUniqueProposalRef(selectedProposal.source_refs, "draft");
    if (baseline.status === "unique" && baseline.ref !== currentDraft?.id) throw new Error(uiText.manuscript.staleProposal);
    const editorRevision = draftEditRevisionRef.current;
    const currentScope = () => activeApiBaseRef.current === apiBase && activeProjectIdRef.current === projectId && activeSceneIdRef.current === sceneId;
    const result = await apiPost<ProposalDraftPromotionResult>(
      apiBase,
      `/projects/${projectId}/proposals/${selectedProposal.id}/promote/draft`,
      { scene_id: sceneId, expected_version: selectedProposal.version, expected_current_draft_id: currentDraft?.id ?? null }
    );
    if (!currentScope() || draftEditRevisionRef.current !== editorRevision || draftDirtyRef.current) return;
    draftRequestSequenceRef.current += 1;
    draftEditorScopeRef.current = { apiBase, projectId, sceneId };
    draftEditRevisionRef.current += 1;
    setDraft(result.draft);
    setDraftText(result.draft.text);
    setDraftSummary(result.draft.summary ?? "");
    setDraftSelection("");
    setAgentDiscussionForm((current) => ({ ...current, selectedText: "" }));
    await refreshProposals(projectId);
    setCreatingNewProposal(false);
    setSelectedProposalId(result.proposal.id);
    if (!currentScope()) return;
    setReadingChapterId(null); setManuscriptMode("preview"); setDraftSelectionRange(null); setWorkspaceTab("write");
    setNotice(uiText.runtime.proposalPromoted(result.draft.version));
  }, [
    apiBase,
    projectId,
    proposalDerivedDraftRef,
    draftLoading,
    proposalDirty,
    proposalTarget,
    refreshProposals,
    sceneId,
    selectedProposal
  ]);

  const applyProjectStructureProposal = useCallback(async () => {
    if (!selectedProposal || !projectId) throw new Error(uiText.errors.selectProjectStructureProposal);
    if (!proposalActionPolicy(
      selectedProposal.status,
      proposalDirty,
      selectedProposal.artifact_type
    ).canPromote || selectedProposal.artifact_type !== "project_structure_draft") {
      throw new Error(uiText.errors.proposalActionUnavailable);
    }
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
    setCreatingNewProposal(false);
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
    proposalDirty,
    refreshGraphPreview,
    refreshProposals,
    refreshWorkspace,
    sceneId,
    selectedProposal
  ]);

  const promoteProposalToCandidates = useCallback(async () => {
    if (!selectedProposal || !projectId) throw new Error(uiText.errors.selectProposal);
    if (!proposalActionPolicy(
      selectedProposal.status,
      proposalDirty,
      selectedProposal.artifact_type
    ).canPromote || selectedProposal.artifact_type !== "fact_draft") {
      throw new Error(uiText.errors.proposalActionUnavailable);
    }
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
    setCreatingNewProposal(false);
    setSelectedProposalId(result.proposal.id);
    setActiveTab("facts");
    setNotice(uiText.runtime.candidatesSubmitted(result.candidates.length));
  }, [
    apiBase,
    draft,
    projectId,
    proposalDirty,
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
      setWorkspaceLoadError(true);
      return;
    }
    if (isDesktopRuntime() && desktopBackend && !desktopBackend.workspaceCompatible) {
      setWorkspaceLoadError(true);
      setError(uiText.runtime.backendWorkspaceConflict);
      setTechnicalError(desktopBackend.error ?? null);
      return;
    }
    refreshWorkspace().catch((exc) => {
      setWorkspaceLoaded(false);
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
    refreshLatestDraft().catch((exc) => {
      setError(uiText.errors.requestFailed);
      setTechnicalError(technicalErrorMessage(exc));
    });
  }, [refreshLatestDraft]);

  useEffect(() => {
    resetProposalScope();
  }, [apiBase, projectId, resetProposalScope]);

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
    draftEditorScopeRef.current = null;
    draftContextInitializedRef.current = null;
    draftDirtyRef.current = false;
    setDraft(null);
    setDraftText("");
    setDraftSummary("");
    setDraftSelectionRange(null); setManuscriptMode("preview"); setAgentTarget(readingChapterId ? "composition" : "scene");
    setAgentDiscussionForm((current) => ({ ...current, mode: "discuss", includeLatestDraft: false, selectedText: "", selectedStart: undefined, selectedEnd: undefined, selectedDraftId: undefined }));
  }, [apiBase, projectId, sceneId]);

  useEffect(() => { setReadingChapterId(null); setAgentTarget("scene"); pendingManuscriptSelectionRef.current = null; }, [apiBase, projectId]);

  useEffect(() => {
    if (draftLoading || !draft || !pendingManuscriptSelectionRef.current) return;
    const pending = pendingManuscriptSelectionRef.current;
    if (pending.projectId !== projectId || pending.draft.scene_id !== sceneId) return;
    pendingManuscriptSelectionRef.current = null;
    if (pending.draft.id !== draft.id || draft.text.slice(pending.range.start, pending.range.end) !== pending.range.text) { setNotice(uiText.manuscript.selectionChanged); return; }
    setAgentDiscussionForm((current) => ({ ...current, mode: "discuss", includeLatestDraft: true, selectedText: pending.range.text, selectedStart: pending.range.start, selectedEnd: pending.range.end, selectedDraftId: draft.id }));
    setAgentTarget("scene"); setActiveTab("agent");
  }, [draft, draftLoading, projectId, sceneId]);

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
    const nextProposalId = proposalAutoSelection(
      proposals.map((proposal) => proposal.id),
      selectedProposalId,
      creatingNewProposal,
      proposalDirty
    );
    if (nextProposalId !== selectedProposalId) {
      setSelectedProposalId(nextProposalId);
    }
  }, [creatingNewProposal, proposalDirty, proposals, selectedProposalId]);

  useEffect(() => {
    if (!selectedProposal) return;
    selectedProposalStableRef.current = selectedProposal;
    if (
      !shouldHydrateProposalEditor(
        proposalEditorSnapshotRef.current,
        selectedProposal,
        proposalTitle,
        proposalText
      )
    ) return;
    hydrateProposalEditor(selectedProposal);
  }, [hydrateProposalEditor, proposalText, proposalTitle, selectedProposal]);

  useEffect(() => {
    if (!projectId || !selectedProposal) {
      reviewProposalOwnerRef.current = null;
      setProposalVersions([]);
      setProposalVersionsLoading(false);
      setReviewProposalVersion(null);
      return;
    }
    let cancelled = false;
    setProposalVersionsLoading(true);
    apiGet<{ versions: ProposalArtifact[] }>(
      apiBase,
      `/projects/${projectId}/proposals/${selectedProposal.id}/versions`
    )
      .then((payload) => {
        if (cancelled) return;
        const proposalChanged = reviewProposalOwnerRef.current !== selectedProposal.id;
        reviewProposalOwnerRef.current = selectedProposal.id;
        setProposalVersions(payload.versions);
        setReviewProposalVersion((current) =>
          !proposalChanged && current !== null && payload.versions.some(
            (version) => version.version === current
          )
            ? current
            : selectedProposal.version
        );
      })
      .catch((exc) => {
        if (cancelled) return;
        setProposalVersions([]);
        setError(uiText.errors.requestFailed);
        setTechnicalError(technicalErrorMessage(exc));
      })
      .finally(() => {
        if (!cancelled) setProposalVersionsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiBase, projectId, selectedProposal]);

  useEffect(() => {
    let cancelled = false;
    const loadExactDraft = async (
      resolution: UniqueRefResolution,
      targetResolution: UniqueRefResolution,
      setLookup: React.Dispatch<React.SetStateAction<ExactDraftLookup>>
    ) => {
      if (resolution.status === "none") {
        setLookup({ status: "none", ref: null, draft: null });
        return;
      }
      if (resolution.status === "ambiguous") {
        setLookup({ status: "ambiguous", ref: null, draft: null });
        return;
      }
      if (targetResolution.status !== "unique" || !projectId) {
        setLookup({ status: "missing_target", ref: resolution.ref, draft: null });
        return;
      }
      setLookup({ status: "loading", ref: resolution.ref, draft: null });
      try {
        const exact = await apiGet<Draft>(
          apiBase,
          `/projects/${projectId}/scenes/${targetResolution.ref}/drafts/${resolution.ref}`
        );
        if (cancelled) return;
        if (
          exact.id !== resolution.ref ||
          exact.project_id !== projectId ||
          exact.scene_id !== targetResolution.ref
        ) {
          setLookup({ status: "error", ref: resolution.ref, draft: null });
          return;
        }
        setLookup({ status: "ready", ref: resolution.ref, draft: exact });
      } catch {
        if (!cancelled) setLookup({ status: "error", ref: resolution.ref, draft: null });
      }
    };

    setProposalBaselineOwnerKey(proposalBaselineKey);
    void loadExactDraft(proposalBaselineRef, proposalReviewTargetRef, setProposalBaseline);
    void loadExactDraft(
      proposalDerivedDraftRef,
      proposalPromotedDraftTargetRef,
      setProposalPromotedDraft
    );
    return () => {
      cancelled = true;
    };
  }, [
    apiBase,
    projectId,
    proposalBaselineRef,
    proposalBaselineKey,
    proposalDerivedDraftRef,
    proposalPromotedDraftTargetRef,
    proposalReviewTargetRef,
    proposalTargetRef
  ]);

  useEffect(() => {
    if (!proposalDirty && !draftDirty && !chapterEditsDirty && !sceneEditsDirty) return;
    const preventUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", preventUnload);
    return () => window.removeEventListener("beforeunload", preventUnload);
  }, [proposalDirty, draftDirty, chapterEditsDirty, sceneEditsDirty]);

  useEffect(() => {
    setChapterSelection(null);
    setChapterTitleEditor(null);
    setChapterMetadataTarget(null);
    setChapterForm(defaultChapterForm);
    setSceneTitleEditor(null);
    setSceneMetadataTarget(null);
    setSceneForm(defaultSceneForm);
  }, [apiBase, projectId]);

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

  useEffect(() => {
    if (desktopBackend?.reachable) void refreshBackendVersion();
  }, [desktopBackend?.reachable, desktopBackend?.pid, refreshBackendVersion]);

  const missingCritical = contextPack?.missing_context.some((gap) => gap.severity === "critical");
  const permission = agentSettings?.permission_level ?? "full";
  const canGenerate = permission === "read_generate" || permission === "full";
  const canReview = permission === "full";
  const writerNeedsKey =
    agentSettings?.scene_writer === "llm" &&
    !taskConnectionReady(agentSettings, "writing");
  const llmConfigured = taskConnectionReady(agentSettings, "writing");
  const discussionConfigured = taskConnectionReady(agentSettings, discussionTask(agentDiscussionForm.mode));
  const planningConfigured = taskConnectionReady(agentSettings, "planning");
  const projectLanguageReady = outputLanguageOrNull(selectedProject?.language) !== null;
  const canRunScene = hasScene && canGenerate && !writerNeedsKey && projectLanguageReady;
  const canDiscussWithAgent = hasScene && canGenerate && discussionConfigured && projectLanguageReady;
  const toggleAgentSource = useCallback((sourceId: string) => {
    if (selectedAgentSourceIds.has(sourceId)) {
      setSelectedAgentSourceIds((current) => {
        const next = new Set(current);
        next.delete(sourceId);
        return next;
      });
      return;
    }
    const source = sourceDocuments.find((item) => item.id === sourceId);
    if (!source) return;
    const eligibility = sourceAgentEligibility(
      source,
      outputLanguageOrNull(selectedProject?.language),
      crossLanguagePolicy
    );
    if (eligibility !== "eligible") {
      setNotice(formatSourceAgentEligibility(eligibility));
      return;
    }
    setSelectedAgentSourceIds((current) => {
      const next = new Set(current);
      if (next.size < 32) {
        next.add(sourceId);
      } else {
        setNotice(uiText.notices.agentSourceLimit);
      }
      return next;
    });
  }, [crossLanguagePolicy, selectedAgentSourceIds, selectedProject, sourceDocuments]);
  const useSourceWithAgent = useCallback(
    (source: SourceDocumentSummary) => {
      if (!hasScene) {
        setNotice(uiText.errors.selectScene);
        return;
      }
      if (!sourceCanHandoff(source)) {
        setNotice(formatSourceAgentEligibility(
          source.extraction_status === "ready" ? "unknown_language" : "not_ready"
        ));
        return;
      }
      if (!outputLanguageOrNull(selectedProject?.language)) {
        setNotice(uiText.errors.projectLanguageRequired);
        return;
      }
      if (!selectedAgentSourceIds.has(source.id) && selectedAgentSourceIds.size >= 32) {
        setNotice(uiText.notices.agentSourceLimit);
        return;
      }
      setSelectedAgentSourceIds((current) => {
        if (current.has(source.id)) return current;
        return addStableSourceSelection(current, source.id);
      });
      setWorkspaceTab("write"); setActiveTab("agent");
      const sendEligibility = sourceAgentEligibility(
        source,
        outputLanguageOrNull(selectedProject?.language),
        crossLanguagePolicy
      );
      setNotice(
        sendEligibility === "eligible"
          ? uiText.notices.sourceAddedToAgent(source.title)
          : uiText.notices.sourceAddedToAgentBlocked(source.title)
      );
    },
    [crossLanguagePolicy, hasScene, selectedAgentSourceIds, selectedProject]
  );
  const changeCrossLanguagePolicy = useCallback(
    (policy: CrossLanguagePolicy) => {
      setCrossLanguagePolicy(policy);
    },
    []
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
  const backendStatusLabel = desktopBackend ? formatDesktopBackendLabel(desktopBackend) : workspaceLoadError ? uiText.navigation.connectionFailed : localizedTerms.fastApi;
  const backendStatusTone = desktopBackend ? desktopBackendTone(desktopBackend) : workspaceLoadError ? "danger" : workspaceLoaded ? "good" : "neutral";

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
          <button type="button" onClick={() => runEditCommand("undo")} title={uiText.commandBar.undoTitle}>
            <Undo2 size={15} /> {uiText.common.undo}
          </button>
          <button type="button" onClick={() => runEditCommand("redo")} title={uiText.commandBar.redoTitle}>
            <Redo2 size={15} /> {uiText.common.redo}
          </button>
          <button
            type="button"
            onClick={() => requestProposalNavigation(
              uiText.proposals.navigateRefresh,
              () => {
                void runAction("workspace", async () => {
                  const refreshed = await refreshWorkspace(projectId, sceneId);
                  await refreshLatestDraft(refreshed.projectId, refreshed.sceneId);
                });
              }
            )}
            disabled={busy !== null}
            title={uiText.commandBar.refreshTitle}
          >
            <RefreshCw size={15} /> {uiText.common.refresh}
          </button>
        </div>
        <div className="top-actions">
          <select className="locale-switch" value={uiLocale} disabled={localeLoading || busy !== null}
            aria-label={uiText.language.uiLocaleLabel} onChange={(event) => { void changeUiLocale(normalizeAppLocale(event.target.value)); }}>
            {SUPPORTED_UI_LOCALES.map((locale) => <option key={locale} value={locale}>{localeRegistry[locale].label}</option>)}
          </select>
          <StatusDot label={backendStatusLabel} tone={backendStatusTone} />
          <StatusDot label={permissionLabels[agentSettings?.permission_level ?? "full"]} tone={permissionTone(agentSettings?.permission_level)} />
          <StatusDot label={`v${APP_VERSION}`} tone="neutral" />
          <StatusDot label={`${uiText.navigation.backendVersion}: ${backendVersion.version ?? uiText.common.notSet}`} tone={versionCompatibility === "mismatch" ? "danger" : versionCompatibility === "match" ? "good" : "warning"} />
          <button className="icon-button" title={uiText.tabs.settings} type="button" onClick={() => setActiveTab("settings")}>
            <Settings size={17} />
          </button>
        </div>
      </header>

      <div className={`layout ${inspectorOpen ? "with-inspector" : "focus-writing"}`}>
        <aside className="sidebar">
          <ProjectSidebar
            busy={busy}
            canReview={canReview && !workspaceLoadError}
            chapterForm={chapterForm}
            characterForm={characterForm}
            currentChapterId={currentChapterId}
            editingChapterId={chapterTitleEditor && chapterEditorMatches(chapterTitleEditor, apiBase, projectId) ? chapterTitleEditor.chapterId : null}
            chapterTitleEditor={chapterTitleEditor}
            onChapterTitleChange={(title) => setChapterTitleEditor((current) => current ? { ...current, title } : current)}
            onSaveChapterTitle={() => runAction("rename-chapter", saveChapterTitle)}
            onCancelChapterTitle={() => setChapterTitleEditor(null)}
            chapterMetadataTarget={chapterMetadataTarget}
            chapterMetadataSaveAllowed={chapterEditorMatches(chapterMetadataTarget, apiBase, projectId) && chapterMetadataDirty}
            onLoadChapterMetadata={loadChapterMetadata}
            onLoadSceneMetadata={loadSceneMetadata}
            sceneMetadataSaveAllowed={sceneMetadataTarget?.apiBase === apiBase && sceneMetadataTarget.projectId === projectId && sceneMetadataTarget.sceneId === sceneId && sceneMetadataDirty}
            readingChapterId={readingChapterId}
            onEditChapter={(id) => {
              const chapter = selectedProject?.chapters.find((item) => item.id === id);
              if (!chapter || actionInFlightRef.current) return;
              if (chapterEditsDirty && !window.confirm(uiText.authorWorkspace.discardMetadataEdits)) return;
              setChapterMetadataTarget(null); setChapterForm(defaultChapterForm);
              setChapterSelection({ projectId, id });
              setChapterTitleEditor({ apiBase, projectId, chapterId: id, title: chapter.title, originalTitle: chapter.title });
            }}
            onSelectChapter={(id) => {
              const chapter = selectedProject?.chapters.find((item) => item.id === id);
              if (!chapter) return;
              requestProposalNavigation(chapter.title, () => {
                setReadingChapterId(id); setChapterSelection({ projectId, id }); setWorkspaceTab("write");
                setManuscriptMode("preview"); setDraftSelection(""); setDraftSelectionRange(null);
                setAgentTarget("composition");
              });
            }}
            hasWorkspace={hasWorkspace}
            locationForm={locationForm}
            onChapterFormChange={setChapterForm}
            onCharacterFormChange={setCharacterForm}
            onCreateChapter={() => runAction("create-chapter", createChapter)}
            onCreateCharacter={() => runAction("create-character", createCharacter)}
            onCreateLocation={() => runAction("create-location", createLocation)}
            onCreateProject={() => requestProposalNavigation(
              uiText.proposals.navigateCreateProject,
              () => { void runAction("create-project", createProject); }
            )}
            onCreateScene={() => requestProposalNavigation(
              uiText.proposals.navigateCreateScene,
              () => { void runAction("create-scene", createScene); }
            )}
            onCreateWorldRule={() => runAction("create-world-rule", createWorldRule)}
            onArchiveDemo={() => requestProposalNavigation(
              uiText.proposals.navigateArchiveDemo,
              () => { void runAction("archive-demo", archiveDemo); }
            )}
            onLocationFormChange={setLocationForm}
            onProjectFormChange={setProjectForm}
            onUpdateProject={() => runAction("update-project", updateProject)}
            onRefresh={() =>
              requestProposalNavigation(
                uiText.proposals.navigateRefresh,
                () => {
                  void runAction("workspace", async () => {
                    const refreshed = await refreshWorkspace(projectId, sceneId);
                  await refreshLatestDraft(refreshed.projectId, refreshed.sceneId);
                  });
                }
              )
            }
            onSceneFormChange={setSceneForm}
            onSelectProject={(nextProjectId) => {
              if (nextProjectId === projectId) return;
              const nextProject = projects.find((project) => project.id === nextProjectId);
              const firstScene = nextProject ? flattenScenes(nextProject)[0] : null;
              requestProposalNavigation(
                uiText.proposals.navigateProject(nextProject?.title ?? nextProjectId),
                () => {
                  setCreatingNewProposal(false);
                  setProposals([]);
                  setSelectedProposalId(null);
                  hydrateProposalEditor(null);
                  setProjectId(nextProjectId);
                  setSceneId(firstScene?.id ?? "");
                  setContextPack(null);
                  setRun(null);
                  setRunEvents([]);
                  setContinuityReport(null);
                }
              );
            }}
            onSelectScene={(nextSceneId) => {
              if (nextSceneId === sceneId) { setReadingChapterId(null); setAgentTarget("scene"); setWorkspaceTab("write"); return; }
              const nextScene = findScene(projects, projectId, nextSceneId);
              requestProposalNavigation(
                uiText.proposals.navigateScene(nextScene?.title ?? nextSceneId),
                () => {
                  setWorkspaceTab("write");
                  setChapterSelection(null); setReadingChapterId(null); setAgentTarget("scene");
                  if (nextSceneId === sceneId) return;
                  setSceneId(nextSceneId);
                  setContextPack(null);
                  setRun(null);
                  setRunEvents([]);
                  setContinuityReport(null);
                }
              );
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
            workspaceLoadError={workspaceLoadError}
            worldRuleForm={worldRuleForm}
          />
          {selectedProject && <details className="outline-language-tools">
            <summary>{uiText.outlineLanguage.tools}</summary>
            <p>{uiText.outlineLanguage.help}</p>
            <p>{modelExecutionLabel(resolvedTask(agentSettings, "planning"))}</p>
            <p>{uiText.language.projectLanguageLabel}: {selectedProject.language === "zh-CN" ? uiText.language.chinese : selectedProject.language === "en-US" ? uiText.language.english : uiText.common.notSet}</p>
            <button type="button" disabled={busy !== null || !canGenerate || !planningConfigured} onClick={() => requestProposalNavigation(uiText.outlineLanguage.generate, () => {
              void runAction("outline-language-generate", generateOutlineLanguageProposal);
            })}><Wand2 size={14} /> {uiText.outlineLanguage.generate}</button>
          </details>}
        </aside>

        <main className="editor">
          <section className="scene-toolbar">
            <div>
              <h1>
                {readingChapter?.title || selectedScene?.title ||
                  (hasWorkspace ? uiText.workspace.importedStructureTitle : uiText.navigation.welcomeTitle)}
              </h1>
              {!readingChapter && selectedScene && <button className="scene-rename-trigger" type="button" disabled={!canReview || busy !== null} onClick={() => {
                if (sceneTitleEditor?.sceneId === sceneId) return;
                if (sceneEditsDirty && !window.confirm(uiText.authorWorkspace.discardMetadataEdits)) return;
                setSceneMetadataTarget(null);
                setSceneForm(defaultSceneForm);
                setSceneTitleEditor({ apiBase, projectId, sceneId, title: selectedScene.title, originalTitle: selectedScene.title });
              }}>{uiText.authorWorkspace.renameScene}</button>}
              {sceneTitleEditor?.apiBase === apiBase && sceneTitleEditor.projectId === projectId && sceneTitleEditor.sceneId === sceneId && <div className="scene-title-editor"><input aria-label={uiText.authorWorkspace.sceneTitle} value={sceneTitleEditor.title} disabled={busy !== null} onChange={(event) => setSceneTitleEditor((current) => current ? { ...current, title: event.target.value } : current)} /><button type="button" disabled={busy !== null || !sceneTitleEditor.title.trim()} onClick={() => runAction("rename-scene", saveSceneTitle)}>{uiText.common.save}</button><button type="button" disabled={busy !== null} onClick={() => setSceneTitleEditor(null)}>{uiText.common.cancel}</button></div>}
              <p>
                {readingChapter ? selectedProject?.title : hasScene
                  ? `${selectedProject?.title ?? ""} / ${selectedProject?.chapters.find((chapter) => chapter.scenes.some((scene) => scene.id === sceneId))?.title ?? ""}`
                  : hasWorkspace
                    ? uiText.workspace.noSceneWithWorkspace
                    : uiText.workspace.noSceneEmptyWorkspace}
              </p>
            </div>
            {workspaceTab === "write" && !readingChapter && <div className="toolbar-actions">
              <button className="primary" onClick={() => runAction("save", saveDraft)} type="button" disabled={!canGenerate || !hasScene || !draftDirty || draftLoading || busy !== null}>
                <Save size={16} /> {uiText.editor.saveButton}
              </button>
              <button onClick={() => { setAgentTarget("scene"); setAgentDiscussionForm((current) => ({ ...current, mode: "continue_scene", includeLatestDraft: true, selectedText: "", selectedStart: undefined, selectedEnd: undefined, selectedDraftId: undefined })); setWorkspaceTab("write"); setActiveTab("agent"); }}
                type="button" disabled={!hasScene || !draft?.text.trim() || busy !== null} title={uiText.navigation.agentHelp}>
                <Wand2 size={16} /> {uiText.navigation.continueScene}
              </button>
              {!inspectorOpen && <button type="button" onClick={() => setActiveTab("agent")}><MessageSquare size={16} /> {uiText.authorWorkspace.openAgent}</button>}
            </div>}
          </section>

          <details className="workspace-status-details"><summary>{uiText.authorWorkspace.workspaceDetails}</summary>
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
          </details>

          <section className="workspace-tabs" aria-label={uiText.workspace.mainWorkspaceAria}>
            <TabButton active={workspaceTab === "write"} onClick={() => setWorkspaceTab("write")} icon={<FileText size={15} />} label={uiText.tabs.write} />
            <TabButton active={workspaceTab === "sources"} onClick={() => setWorkspaceTab("sources")} icon={<Library size={15} />} label={uiText.tabs.sources} />
            <TabButton active={workspaceTab === "proposals"} onClick={() => setWorkspaceTab("proposals")} icon={<SplitSquareVertical size={15} />} label={uiText.tabs.proposals} />
            <details className="tools-menu">
              <summary title={uiText.navigation.toolsHelp}><Settings size={15} /> {uiText.navigation.tools} <ChevronDown size={13} /></summary>
              <div className="tools-menu-items" onClick={(event) => { if ((event.target as HTMLElement).closest("button")) event.currentTarget.closest("details")?.removeAttribute("open"); }}>
                <button type="button" onClick={() => setWorkspaceTab("workflow")}><Activity size={15} /> {uiText.tabs.workflow}</button>
                <button type="button" onClick={() => setActiveTab("context")}><Boxes size={15} /> {uiText.tabs.context}</button>
                <button type="button" onClick={() => setActiveTab("continuity")}><ShieldCheck size={15} /> {uiText.tabs.continuity}</button>
                <button type="button" onClick={() => setActiveTab("facts")}><Database size={15} /> {localizedTerms.canonReview}</button>
                <button type="button" onClick={() => setActiveTab("settings")}><Settings size={15} /> {uiText.tabs.settings}</button>
              </div>
            </details>
          </section>

          <div className="workspace-guide">
            <span>{workspaceTab === "write" ? uiText.authorWorkspace.writingGuide : workspaceTab === "workflow" ? uiText.navigation.workflowHelp : uiText.navigation[`${workspaceTab === "sources" ? "sources" : "proposals"}Help`]}</span>
            {!llmConfigured && <button type="button" onClick={() => setActiveTab("settings")}><KeyRound size={14} /> {uiText.navigation.setupModel}</button>}
          </div>

          {versionCompatibility === "mismatch" && <div className="message error" role="alert"><AlertTriangle size={16} /><span>{uiText.navigation.backendVersionMismatch(APP_VERSION, backendVersion.version!)}</span></div>}

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

          {workspaceLoadError && <section className="empty-workspace"><EmptyState icon={<AlertTriangle />} title={uiText.navigation.connectionFailed} text={uiText.navigation.connectionFailedHelp} /><button type="button" onClick={() => setActiveTab("settings")}><Settings size={15} /> {uiText.tabs.settings}</button></section>}
          {!hasWorkspace && workspaceLoaded && !workspaceLoadError && (
            <section className="empty-workspace">
              <EmptyState
                icon={<Database />}
                title={uiText.navigation.welcomeTitle}
                text={uiText.navigation.welcomeText}
              />
            </section>
          )}

          {workspaceTab === "write" && !readingChapter && (
            <details className="scene-details">
              <summary>{uiText.navigation.sceneDetails}</summary>
              <section className="meta-grid" aria-label={uiText.workspace.sceneMetadataAria}>
              <Meta label={uiText.editor.goal} value={contextPack?.scene_goal || selectedScene?.goal || ""} />
              <Meta label={uiText.editor.conflict} value={contextPack?.conflict || selectedScene?.conflict || ""} />
              <Meta
                label={uiText.editor.timeline}
                value={contextPack?.timeline_position || selectedScene?.timeline_position || ""}
              />
              <Meta label={uiText.editor.location} value={contextPack?.location_id || selectedScene?.location_id || ""} />
              </section>
            </details>
          )}

          {workspaceTab === "sources" && (
          <section
            ref={libraryPanelRef}
            className={`library-panel ${sourceImportProgress ? "has-import-progress" : ""}`}
            aria-label={uiText.library.ariaLabel}
            style={
              sourcePaneStacked
                ? undefined
                : ({
                    "--source-panel-height": `${effectiveSourcePaneLayout.panelHeight}px`,
                    "--source-tree-width": `${effectiveSourcePaneLayout.treeWidth}px`
                  } as React.CSSProperties)
            }
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
                    accept=".txt,.md,.markdown,.rtf,.docx"
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
                    accept=".txt,.md,.markdown,.rtf,.docx"
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
            <div className="library-grid" ref={libraryGridRef}>
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
              {!sourcePaneStacked && (
                <PaneResizeHandle
                  ariaLabel={uiText.library.resizeWidthAria}
                  help={uiText.library.resizeHelp}
                  max={sourcePaneBoundsState.maxTreeWidth}
                  min={sourcePaneBoundsState.minTreeWidth}
                  onChange={(value, commit) =>
                    changeSourcePaneDimension("treeWidth", value, commit)
                  }
                  onReset={() => resetSourcePaneDimension("treeWidth")}
                  orientation="vertical"
                  value={effectiveSourcePaneLayout.treeWidth}
                />
              )}
              <DocumentReader
                canAdoptSources={canReview}
                structureReady={Boolean(agentSettings) && (planningConfigured || !agentSettings?.task_assignments?.planning)}
                structureModelLabel={planningConfigured ? modelExecutionLabel(resolvedTask(agentSettings, "planning")) : agentSettings?.task_assignments?.planning ? uiText.modelRouting.missingAssignment : uiText.runtime.localRules}
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
                onSaveSelection={(document, range) => requestProposalNavigation(uiText.manuscript.useSource, () => { void runAction("source-selection-draft", () => adoptSourceSelection(document, range)); })}
                onSaveDraft={(document) => requestProposalNavigation(uiText.manuscript.saveWholeSource, () => {
                  const text = document.extracted_text ?? "";
                  void runAction("source-whole-draft", () => adoptSourceSelection(document, { text, start: 0, end: text.length }));
                })}
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
                onUseWithAgent={useSourceWithAgent}
                onPolicyChange={changeCrossLanguagePolicy}
                crossLanguagePolicy={crossLanguagePolicy}
                projectLanguage={outputLanguageOrNull(selectedProject?.language)}
                summary={selectedSourceSummary}
              />
            </div>
            {!sourcePaneStacked && (
              <PaneResizeHandle
                ariaLabel={uiText.library.resizeHeightAria}
                help={uiText.library.resizeHelp}
                max={sourcePaneBoundsState.maxPanelHeight}
                min={sourcePaneBoundsState.minPanelHeight}
                onChange={(value, commit) =>
                  changeSourcePaneDimension("panelHeight", value, commit)
                }
                onReset={() => resetSourcePaneDimension("panelHeight")}
                orientation="horizontal"
                value={effectiveSourcePaneLayout.panelHeight}
              />
            )}
          </section>
          )}

          {workspaceTab === "proposals" && (
          <ProposalInbox
            baseline={effectiveProposalBaseline}
            busy={busy}
            canGenerate={canGenerate}
            canReview={canReview}
            currentDraftId={draft?.id ?? ""}
            currentDraftReady={!draftLoading && !draftDirty && Boolean(draftEditorScopeRef.current && draftScopesMatch(draftEditorScopeRef.current, { apiBase, projectId, sceneId }))}
            currentSceneId={sceneId}
            derivedDraftRef={proposalDerivedDraftRef}
            dirty={proposalDirty}
            filter={proposalStatusFilter}
            hasScene={hasScene}
            onAccept={() => runAction("proposal-accept", () => reviewProposal("accept"))}
            onApplyProjectStructure={() =>
              runAction("proposal-structure", applyProjectStructureProposal)
            }
            onApplyComposition={() => requestProposalNavigation(uiText.manuscript.applyComposition, () => { void runAction("composition-apply", applyCompositionProposal); })}
            onApplyOutlineLanguage={() => requestProposalNavigation(uiText.outlineLanguage.apply, () => {
              void runAction("outline-language-apply", applyOutlineLanguageProposal);
            })}
            currentProjectId={projectId}
            onCreateNew={() =>
              requestProposalNavigation(uiText.proposals.navigateNewProposal, () => { void runAction("proposal-new", startNewProposal); })
            }
            onExtractCandidates={() =>
              runAction("proposal-candidates", promoteProposalToCandidates)
            }
            onFilterChange={setProposalStatusFilter}
            onOpenCanonReview={() => {
              setActiveTab("facts");
            setNotice(uiText.notices.openedFactReview);
            }}
            onOpenPromotedDraft={() => {
              if (!canOpenPromotedDraft(
                proposalDerivedDraftRef,
                proposalPromotedDraft.status === "ready"
              ) || proposalPromotedDraft.status !== "ready") return;
              if (!exactDraftMatchesEditorScene(
                proposalPromotedDraft.draft.scene_id,
                sceneId
              )) {
                setNotice(uiText.proposals.openDraftSwitchFirst);
                return;
              }
              requestProposalNavigation(uiText.proposals.openPromotedDraft, () => {
              if (proposalPromotedDraft.status !== "ready") return;
              draftRequestSequenceRef.current += 1;
              draftEditorScopeRef.current = { apiBase, projectId, sceneId };
              draftEditRevisionRef.current += 1;
              setDraft(proposalPromotedDraft.draft);
              setDraftText(proposalPromotedDraft.draft.text);
              setDraftSummary(proposalPromotedDraft.draft.summary ?? "");
              setDraftSelection("");
              setAgentDiscussionForm((current) => ({ ...current, selectedText: "" }));
              setReadingChapterId(null); setManuscriptMode("preview"); setDraftSelectionRange(null);
              setWorkspaceTab("write");
              setNotice(uiText.notices.promotedDraftOpened(
                proposalPromotedDraft.draft.id,
                proposalPromotedDraft.draft.version
              ));
              });
            }}
            onPromoteDraft={() => requestProposalNavigation(uiText.proposals.promoteDraft, () => { void runAction("proposal-draft", promoteProposalToDraft); })}
            onReject={() => runAction("proposal-reject", () => reviewProposal("reject"))}
            onReviewVersion={setReviewProposalVersion}
            onSave={() => runAction("proposal-save", saveProposal)}
            onSelect={(nextProposalId) => {
              if (nextProposalId === selectedProposalId) return;
              const nextProposal = proposals.find((proposal) => proposal.id === nextProposalId);
              requestProposalNavigation(
                uiText.proposals.navigateProposal(nextProposal?.title ?? nextProposalId),
                () => {
                  setCreatingNewProposal(false);
                  setSelectedProposalId(nextProposalId);
                }
              );
            }}
            onSourceDraftChange={setProposalSourceDraftId}
            onSubmitReview={() => runAction("proposal-submit", submitProposalReview)}
            onSwitchTarget={() => {
              if (!proposalTargetScene) return;
              requestProposalNavigation(
                uiText.proposals.navigateScene(proposalTargetScene.title),
                () => {
                  setSceneId(proposalTargetScene.id);
                  setContextPack(null);
                  setRun(null);
                  setRunEvents([]);
                  setContinuityReport(null);
                }
              );
            }}
            onTextChange={setProposalText}
            onTitleChange={setProposalTitle}
            onTypeChange={setProposalArtifactType}
            proposalSourceDraftId={proposalSourceDraftId}
            proposalText={proposalText}
            proposalTitle={proposalTitle}
            proposalType={proposalArtifactType}
            proposals={visibleProposals}
            promotedDraft={proposalPromotedDraft}
            reviewProposal={selectedReviewProposal}
            reviewVersion={reviewProposalVersion}
            selectedProposal={selectedProposal}
            targetPolicy={proposalTarget}
            targetScene={proposalTargetScene}
            versions={proposalVersions.filter((version) => version.id === selectedProposal?.id)}
            versionsLoading={proposalVersionsLoading}
          />
          )}

          {workspaceTab === "write" && readingChapter && <ChapterManuscript apiBase={apiBase} projectId={projectId} chapter={readingChapter} refreshKey={`${draft?.id ?? ""}:${draft?.version ?? ""}`} busy={busy !== null}
            onNewChapter={() => { setAgentTarget("composition"); setActiveTab("agent"); }}
            onOpenScene={(id) => requestProposalNavigation(uiText.manuscript.openScene, () => { setReadingChapterId(null); setChapterSelection(null); setAgentTarget("scene"); setSceneId(id); setWorkspaceTab("write"); })}
            onAskSelection={(selectedDraft, range) => requestProposalNavigation(uiText.manuscript.selectionAction, () => {
              setReadingChapterId(null); setChapterSelection(null); setAgentTarget("scene"); setWorkspaceTab("write"); setActiveTab("agent");
              if (selectedDraft.scene_id === sceneId && draft?.id === selectedDraft.id) setAgentDiscussionForm((current) => ({ ...current, mode: "discuss", includeLatestDraft: true, selectedText: range.text, selectedStart: range.start, selectedEnd: range.end, selectedDraftId: selectedDraft.id }));
              else { pendingManuscriptSelectionRef.current = { projectId, draft: selectedDraft, range }; if (selectedDraft.scene_id === sceneId) { void runAction("chapter-draft-refresh", () => refreshLatestDraft()); } else setSceneId(selectedDraft.scene_id); }
            })} />}
          {workspaceTab === "write" && !readingChapter && hasScene && (
          <section className={`draft-surface manuscript-surface ${manuscriptMode}`}>
            <div className="draft-header">
              <span>{uiText.manuscript.sceneBody}</span>
              <div className="manuscript-mode" role="group" aria-label={uiText.manuscript.sceneBody}>
                <button type="button" className={manuscriptMode === "preview" ? "active" : ""} aria-pressed={manuscriptMode === "preview"} onClick={() => setManuscriptMode("preview")}><Eye size={14} />{uiText.manuscript.preview}</button>
                <button type="button" className={manuscriptMode === "edit" ? "active" : ""} aria-pressed={manuscriptMode === "edit"} disabled={!canGenerate || draftLoading} onClick={() => setManuscriptMode("edit")}><FileText size={14} />{uiText.manuscript.edit}</button>
              </div>
              <div className="draft-header-actions"><button type="button" disabled={!draftText.trim()} onClick={() => exportAuthorText(selectedScene?.title ?? "StoryGraph", draftText)}><Download size={13} />{uiText.navigation.exportText}</button></div>
            </div>
            <div className="draft-status"><span>{uiText.navigation.draftCharacters(Array.from(draftText).length)}{draft ? ` · v${draft.version}` : ""}</span><span className={draftDirty ? "dirty" : ""}>{draftDirty ? uiText.navigation.draftUnsaved : draft ? uiText.navigation.draftSaved : uiText.manuscript.sceneEmpty}</span></div>
            {draftSelection.trim() && <div className="manuscript-selection-bar"><span>{uiText.manuscript.selectionHelp}</span><button type="button" disabled={busy !== null} onClick={useDraftSelectionForAgent}><MessageSquare size={14} />{uiText.manuscript.selectionAction}</button></div>}
            {draftLoading ? <p className="manuscript-empty">{uiText.manuscript.loading}</p> : manuscriptMode === "preview" ? draftText.trim() ?
              <div className="manuscript-page">{draftDirty && <p className="manuscript-reading-hint">{uiText.manuscript.unsavedPreview}</p>}<ManuscriptProse text={draftText} onSelection={(range) => { setDraftSelection(range?.text ?? ""); setDraftSelectionRange(range); }} /></div> :
              <div className="manuscript-empty"><BookOpen size={34} /><h2>{uiText.manuscript.emptyTitle}</h2><p>{uiText.manuscript.emptyHelp}</p><div><button type="button" className="primary" disabled={!canGenerate} onClick={() => setManuscriptMode("edit")}><FileText size={15} />{uiText.manuscript.startWriting}</button><button type="button" disabled={!hasScene || !canGenerate || !llmConfigured || !projectLanguageReady || busy !== null} onClick={beginSceneDraft}><Wand2 size={15} />{uiText.manuscript.generateScene}</button><button type="button" onClick={() => setWorkspaceTab("sources")}><Library size={15} />{uiText.manuscript.openSources}</button></div></div> :
              <div className="manuscript-edit-page"><textarea ref={draftTextareaRef} readOnly={draftLoading || !draftEditorScopeRef.current || !draftScopesMatch(draftEditorScopeRef.current, { apiBase, projectId, sceneId }) || (busy !== null && busy !== "save" && busy !== "proposal-save-navigation")} value={draftText} onChange={handleDraftTextChange} onKeyUp={captureDraftSelection} onMouseUp={captureDraftSelection} onSelect={captureDraftSelection} spellCheck={false} aria-label={uiText.editor.draftBodyAria} /></div>}
            {manuscriptMode === "edit" && <input className="summary-input" readOnly={draftLoading || busy !== null} value={draftSummary} onChange={handleDraftSummaryChange} aria-label={uiText.editor.draftSummaryAria} placeholder={uiText.editor.draftSummaryAria} />}
          </section>
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
            <div className="workflow-actions">
              <button className="primary" onClick={() => requestProposalNavigation(uiText.navigation.startWorkflow, () => { void runAction("run", runScene); })} type="button" disabled={!canRunScene || busy !== null}><Play size={15} /> {uiText.navigation.startWorkflow}</button>
              <button onClick={() => runAction("context", buildContext)} type="button" disabled={!hasScene || busy !== null}><RefreshCw size={15} /> {uiText.editor.contextButton}</button>
              <button onClick={() => requestProposalNavigation(uiText.editor.generateDraftButton, () => { void runAction("draft", generateDraft); })} type="button" disabled={missingCritical || !canRunScene || busy !== null}><FileText size={15} /> {uiText.editor.generateDraftButton}</button>
            </div>
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

        <aside className="inspector" hidden={!inspectorOpen}>
          <div className="inspector-heading"><strong>{activeTab === "agent" ? uiText.authorWorkspace.agentTitle : uiText.authorWorkspace.settingsTitle}</strong><button className="icon-button" type="button" onClick={() => setInspectorOpen(false)} aria-label={uiText.authorWorkspace.closeAgent}><X size={16} /></button></div>
          <div className="tabs inspector-tabs" role="tablist">
            <TabButton active={activeTab === "agent"} onClick={() => setActiveTab("agent")} icon={<MessageSquare size={15} />} label={uiText.tabs.agent} />
            <TabButton active={activeTab === "context"} onClick={() => setActiveTab("context")} icon={<Boxes size={15} />} label={uiText.tabs.context} />
            <TabButton active={activeTab === "continuity"} onClick={() => setActiveTab("continuity")} icon={<Activity size={15} />} label={uiText.tabs.continuity} />
            <TabButton active={activeTab === "facts"} onClick={() => setActiveTab("facts")} icon={<ShieldCheck size={15} />} label={uiText.tabs.facts} />
            <TabButton active={activeTab === "settings"} onClick={() => setActiveTab("settings")} icon={<Settings size={15} />} label={uiText.tabs.settings} />
          </div>
          {activeTab === "agent" && (
          <div className="agent-workspace agent-dock">
          <details className="agent-preset-options"><summary>{uiText.authorWorkspace.presetOptions}</summary>
          <AgentPresets compact apiBase={apiBase} settings={agentSettings} busy={busy !== null} onChange={setAgentSettings} onManage={() => setActiveTab("settings")} />
          </details>
          <div className="agent-target-tabs"><button type="button" className={agentTarget === "scene" ? "active" : ""} onClick={() => { setReadingChapterId(null); setAgentTarget("scene"); }}>{uiText.manuscript.currentScene}</button><button type="button" className={agentTarget === "composition" ? "active" : ""} onClick={() => setAgentTarget("composition")}>{uiText.manuscript.newWork}</button></div>
          {agentTarget === "composition" ? <CompositionComposer key={`${apiBase}:${projectId}`} sourceLabels={Array.from(selectedAgentSourceIds).map((id) => { const source = sourceDocuments.find((item) => item.id === id); return source ? `${source.title} · ${formatSourceLanguage(source.language)} · ${id}` : uiText.agentDiscussion.sourceMissing; })} sourcePolicy={crossLanguagePolicy === "explicit_reference" ? uiText.language.explicitReference : uiText.language.projectOnly} draftLabel={!readingChapter && draft?.text.trim() && !draftDirty && draft.project_id === projectId && draft.scene_id === sceneId ? `${selectedScene?.title ?? ""} · v${draft.version} · ${draft.id}` : null} busy={busy !== null} canGenerate={Boolean(projectId) && canGenerate && planningConfigured} modelLabel={modelExecutionLabel(resolvedTask(agentSettings, "planning"))} onGenerate={(input) => requestProposalNavigation(uiText.manuscript.generate, () => { void runAction("composition-generate", () => generateComposition(input)); })} /> : <AgentDiscussionPanel
            busy={busy}
            canDiscuss={canDiscussWithAgent}
            draft={draft}
            draftDirty={draftDirty}
            draftSelection={draftSelection}
            form={agentDiscussionForm}
            hasScene={hasScene}
            llmConfigured={discussionConfigured}
            modelExecution={resolvedTask(agentSettings, discussionTask(agentDiscussionForm.mode))}
            onFormChange={setAgentDiscussionForm}
            onOpenWriting={() => setWorkspaceTab("write")}
            onOpenProposal={() => {
              const target = agentDiscussionResult?.proposal;
              requestProposalNavigation(uiText.authorWorkspace.reviewResult, () => {
                if (target) { setCreatingNewProposal(false); setSelectedProposalId(target.id); }
                setWorkspaceTab("proposals");
              });
            }}
            onSaveDraft={() => runAction("save", saveDraft)}
            onPolicyChange={changeCrossLanguagePolicy}
            onSubmit={() => runAction("agent-discussion", requestAgentDiscussion)}
            onRestoreDraft={restoreSavedDraft}
            onToggleSource={toggleAgentSource}
            onUseDraftSelection={useDraftSelectionForAgent}
            result={agentDiscussionResult}
            selectedSourceIds={selectedAgentSourceIds}
            selectedProposal={selectedProposal}
            sources={sourceDocuments}
            crossLanguagePolicy={crossLanguagePolicy}
            projectLanguage={outputLanguageOrNull(selectedProject?.language)}
            projectId={projectId}
            sceneId={sceneId}
            sceneTitle={selectedScene?.title ?? ""}
          />}
          </div>
          )}

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
          <div hidden={activeTab !== "settings"} className="settings-inspector-host">
            <AgentSettingsInspector
              apiBase={apiBase}
              onApiBaseChange={(value) => { const normalized = normalizeApiBase(value); if (!normalized) return; if (!isDesktopRuntime()) saveBrowserApiBase(normalized); setApiBase(normalized); }}
              connectionLocked={proposalDirty || draftDirty || chapterEditsDirty || sceneEditsDirty}
              apiKeyInput={apiKeyInput}
              busy={busy}
              clearApiKey={clearApiKey}
              desktopBackend={desktopBackend}
              desktopSettings={desktopSettings}
              form={agentForm}
              locale={uiLocale}
              onApiKeyChange={changeApiKeyInput}
              onClearApiKeyChange={changeClearApiKey}
              onFormChange={changeAgentForm}
              onLocaleChange={(locale) => { void changeUiLocale(locale); }}
              onBackendRefresh={() => runAction("desktop-backend", () => refreshDesktopBackend("status").then(() => undefined))}
              onBackendStart={() => runAction("desktop-backend", () => refreshDesktopBackend("start").then(() => undefined))}
              onBackendStop={() => runAction("desktop-backend", stopDesktopBackend)}
              onRefresh={() => runAction("settings", refreshAgentSettings)}
              onSave={() => runAction("settings", saveAgentSettings)}
              onInstallUpdate={() => { void installAvailableUpdate(); }}
              onUpdateCheck={() => runAction("update-check", () => checkForUpdates(false))}
              backendVersion={backendVersion}
              settings={agentSettings}
              onSettingsChange={setAgentSettings}
              updateStatus={updateStatus}
            />
          </div>
          {activeTab !== "agent" && <GraphPreview preview={graphPreview} selectedSceneId={sceneId} />}
        </aside>
      </div>
      {pendingProposalNavigation && (
        <UnsavedProposalDialog
          busy={busy !== null}
          destination={pendingProposalNavigation.label}
          kind={pendingProposalNavigation.kind}
          onCancel={cancelProposalNavigation}
          onDiscard={discardProposalAndNavigate}
          onSave={saveProposalAndNavigate}
        />
      )}
    </div>
  );
}

function UnsavedProposalDialog({
  busy,
  destination,
  kind,
  onCancel,
  onDiscard,
  onSave
}: {
  busy: boolean;
  destination: string;
  kind: "proposal" | "draft";
  onCancel: () => void;
  onDiscard: () => void;
  onSave: () => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        aria-describedby="proposal-navigation-description"
        aria-labelledby="proposal-navigation-title"
        aria-modal="true"
        className="unsaved-proposal-dialog"
        role="dialog"
      >
        <h2 id="proposal-navigation-title">{kind === "draft" ? uiText.navigation.unsavedDraftTitle : uiText.proposals.unsavedDialogTitle}</h2>
        <p id="proposal-navigation-description">
          {kind === "draft" ? uiText.navigation.unsavedDraftText(destination) : uiText.proposals.unsavedDialogText(destination)}
        </p>
        <div className="dialog-actions">
          <button className="primary" disabled={busy} onClick={onSave} type="button">
            <Save size={14} /> {uiText.proposals.saveAndContinue}
          </button>
          <button className="danger" disabled={busy} onClick={onDiscard} type="button">
            {uiText.proposals.discardAndContinue}
          </button>
          <button disabled={busy} onClick={onCancel} type="button">
            {uiText.common.cancel}
          </button>
        </div>
      </section>
    </div>
  );
}

function AgentDiscussionPanel({
  busy,
  canDiscuss,
  crossLanguagePolicy,
  draft,
  draftDirty,
  draftSelection,
  form,
  hasScene,
  llmConfigured,
  modelExecution,
  onFormChange,
  onOpenWriting,
  onOpenProposal,
  onSaveDraft,
  onPolicyChange,
  onRestoreDraft,
  onSubmit,
  onToggleSource,
  onUseDraftSelection,
  result,
  selectedProposal,
  selectedSourceIds,
  sources,
  projectLanguage,
  projectId,
  sceneId,
  sceneTitle
}: {
  busy: string | null;
  canDiscuss: boolean;
  crossLanguagePolicy: CrossLanguagePolicy;
  draft: Draft | null;
  draftDirty: boolean;
  draftSelection: string;
  form: AgentDiscussionForm;
  hasScene: boolean;
  llmConfigured: boolean;
  modelExecution: ModelExecution | null;
  onFormChange: React.Dispatch<React.SetStateAction<AgentDiscussionForm>>;
  onOpenWriting: () => void;
  onOpenProposal: () => void;
  onSaveDraft: () => void;
  onPolicyChange: (policy: CrossLanguagePolicy) => void;
  onRestoreDraft: () => void;
  onSubmit: () => void;
  onToggleSource: (sourceId: string) => void;
  onUseDraftSelection: () => void;
  result: AgentDiscussionResult | null;
  selectedProposal: ProposalArtifact | null;
  selectedSourceIds: Set<string>;
  sources: SourceDocumentSummary[];
  projectLanguage: AppLocale | null;
  projectId: string;
  sceneId: string;
  sceneTitle: string;
}) {
  const selectedRequired = form.mode === "revise_selection";
  const draftRequired = form.mode !== "discuss" && form.mode !== "create_scene";
  const includedDraft = agentIncludedDraftPolicy(
    draft,
    form.includeLatestDraft,
    draftDirty,
    projectId,
    sceneId
  );
  const selectedSources = sources.filter((source) => selectedSourceIds.has(source.id));
  const missingSourceIds = Array.from(selectedSourceIds).filter(
    (sourceId) => !sources.some((source) => source.id === sourceId)
  );
  const blockedSourceIds = Array.from(selectedSourceIds).filter((sourceId) => {
    const source = sources.find((item) => item.id === sourceId);
    return !source || sourceAgentEligibility(
      source,
      projectLanguage,
      crossLanguagePolicy
    ) !== "eligible";
  });
  const canSubmit =
    canDiscuss &&
    busy === null &&
    blockedSourceIds.length === 0 &&
    form.instruction.trim().length > 0 &&
    (!form.includeLatestDraft || includedDraft.status === "ready") &&
    (!draftRequired || form.includeLatestDraft) &&
    (!selectedRequired || form.selectedText.trim().length > 0);
  const savedDraftManifest = includedDraft.status === "excluded"
    ? uiText.agentDiscussion.manifestExcluded
    : draft
      ? `${draft.id} / v${draft.version}`
      : uiText.agentDiscussion.manifestNoSavedDraft;
  const localDraftState = draftDirty
    ? uiText.agentDiscussion.manifestDraftDirty
    : includedDraft.status === "blocked_scope"
      ? uiText.agentDiscussion.manifestDraftScopeMismatch
    : draft
      ? uiText.agentDiscussion.manifestDraftSynced
      : uiText.agentDiscussion.manifestNoSavedDraft;
  const webState = form.allowWebSearch
    ? form.webSearchQuery.trim()
      ? uiText.agentDiscussion.manifestWebQuery(form.webSearchQuery.trim())
      : uiText.agentDiscussion.manifestWebEnabled
    : uiText.agentDiscussion.manifestWebDisabled;
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
        <div className="agent-input-summary" aria-label={uiText.authorWorkspace.draftContext}>
          <strong>{sceneTitle || uiText.agentDiscussion.noSceneTitle}</strong>
          <span>{projectLanguage ? formatArtifactLanguage(projectLanguage, false) : uiText.language.projectLanguageNeedsReview} · {uiText.agentDiscussion.sourcePickerCount(selectedSourceIds.size)}</span>
          <code>{savedDraftManifest}</code>
          <span className="model-execution-summary">{uiText.modelRouting.effective}: {modelExecutionLabel(modelExecution)}</span>
        </div>
        {form.includeLatestDraft && includedDraft.status !== "ready" && (draftDirty || Boolean(draft) || draftRequired) && <div className="agent-context-note warning">
          <span>{draftDirty ? uiText.authorWorkspace.saveBeforeSend : includedDraft.status === "blocked_scope" ? uiText.errors.agentDraftScopeMismatch : uiText.errors.agentIncludedDraftMustBeSaved}</span>
          <button type="button" onClick={onSaveDraft} disabled={busy !== null || !hasScene}>{uiText.authorWorkspace.saveCurrentDraft}</button>
        </div>}
        {blockedSourceIds.length > 0 && <p className="preset-error">{uiText.errors.agentSourcesBlockedByPolicy}</p>}
        <div className="agent-mode-row">
          <label>
            <span>{uiText.agentDiscussion.mode}</span>
            <select
              value={form.mode}
              onChange={(event) =>
                onFormChange((current) => ({
                  ...current,
                  mode: event.target.value as AgentDiscussionMode,
                  includeLatestDraft: event.target.value === "create_scene" ? false : event.target.value === "discuss" ? current.includeLatestDraft && Boolean(draft) : true
                }))
              }
            >
              {!draft?.text.trim() && <option value="create_scene">{uiText.manuscript.generateScene}</option>}
              <option value="discuss">{uiText.agentDiscussion.modes.discuss}</option>
              <option value="continue_scene">{uiText.navigation.continueScene}</option>
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
        {(selectedRequired || Boolean(form.selectedText)) && <label className="agent-field selection">
          <span>{uiText.agentDiscussion.selectionLabel}</span>
          <textarea
            disabled={!form.includeLatestDraft}
            value={form.selectedText}
            onChange={(event) =>
              onFormChange((current) => ({ ...current, selectedText: event.target.value, selectedStart: undefined, selectedEnd: undefined, selectedDraftId: undefined }))
            }
            placeholder={uiText.agentDiscussion.selectionPlaceholder}
          />
        </label>}
        <div className="agent-actions">
          <button type="button" className="primary" onClick={onSubmit} disabled={!canSubmit}>
            <Wand2 size={15} /> {uiText.agentDiscussion.submit}
          </button>
          <button type="button" onClick={onOpenProposal} disabled={!result && !selectedProposal}>
            <SplitSquareVertical size={14} /> {uiText.authorWorkspace.reviewResult}
          </button>
        </div>
      </div>
      <div className="agent-context">
        <details className="agent-input-manifest"><summary>{uiText.authorWorkspace.inputDetails}</summary>
          <div className="agent-source-head">
            <div>
              <strong>{uiText.agentDiscussion.manifestTitle}</strong>
              <span>{uiText.agentDiscussion.manifestDescription}</span>
            </div>
          </div>
          <MetricRow
            label={uiText.agentDiscussion.manifestTargetScene}
            value={sceneId ? `${sceneTitle || uiText.common.notSet} / ${sceneId}` : uiText.common.none}
          />
          <MetricRow
            label={uiText.agentDiscussion.manifestOutputLanguage}
            value={projectLanguage ? formatArtifactLanguage(projectLanguage, false) : uiText.language.projectLanguageNeedsReview}
          />
          <MetricRow label={uiText.modelRouting.effective} value={modelExecutionLabel(modelExecution)} />
          <MetricRow label={uiText.agentDiscussion.manifestSavedDraft} value={savedDraftManifest} />
          <MetricRow label={uiText.agentDiscussion.manifestLocalDraftState} value={localDraftState} />
          <MetricRow
            label={uiText.agentDiscussion.manifestContextPack}
            value={
              form.includeContextPack
                ? uiText.agentDiscussion.manifestContextRebuilt
                : uiText.agentDiscussion.manifestExcluded
            }
          />
          <MetricRow
            label={uiText.agentDiscussion.manifestPolicy}
            value={
              crossLanguagePolicy === "explicit_reference"
                ? uiText.language.explicitReference
                : uiText.language.projectOnly
            }
          />
          <MetricRow label={uiText.agentDiscussion.manifestWebSearch} value={webState} />
          <ListBlock
            title={uiText.agentDiscussion.manifestSources}
            items={[
              ...selectedSources.map((source) => {
                const eligibility = sourceAgentEligibility(
                  source,
                  projectLanguage,
                  crossLanguagePolicy
                );
                return `${source.title} · ${formatSourceLanguage(source.language)} · ${source.id}${
                  eligibility === "eligible"
                    ? ""
                    : ` · ${uiText.agentDiscussion.manifestSourceBlocked}`
                }`;
              }),
              ...missingSourceIds.map(
                (sourceId) => `${uiText.agentDiscussion.sourceMissing} · ${formatSourceLanguage("und")} · ${sourceId} · ${uiText.agentDiscussion.manifestSourceBlocked}`
              )
            ]}
          />
        </details>
        <details className="agent-reference-options"><summary>{uiText.authorWorkspace.referenceOptions}</summary>
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
              disabled={form.mode === "create_scene" || !draft}
              onChange={(event) =>
                onFormChange((current) => ({
                  ...current,
                  includeLatestDraft: event.target.checked,
                  mode: event.target.checked ? current.mode : "discuss",
                  selectedText: event.target.checked ? current.selectedText : "",
                  selectedStart: event.target.checked ? current.selectedStart : undefined, selectedEnd: event.target.checked ? current.selectedEnd : undefined, selectedDraftId: event.target.checked ? current.selectedDraftId : undefined
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
        {form.includeLatestDraft && includedDraft.status !== "ready" && (
          <div className="agent-context-note warning agent-draft-recovery">
            <div>
              <AlertTriangle size={14} />
              <span>
                {includedDraft.status === "blocked_scope"
                  ? uiText.errors.agentDraftScopeMismatch
                  : uiText.errors.agentIncludedDraftMustBeSaved}
              </span>
            </div>
            <div>
              <button type="button" onClick={onOpenWriting} disabled={busy !== null}>
                <FileText size={13} /> {uiText.agentDiscussion.openWriting}
              </button>
              {canRestoreSavedDraft(draft, draftDirty) && (
                <button className="danger" type="button" onClick={onRestoreDraft} disabled={busy !== null}>
                  {uiText.agentDiscussion.restoreSavedDraft}
                </button>
              )}
            </div>
          </div>
        )}
        {blockedSourceIds.length > 0 && (
          <div className="agent-context-note warning">
            <AlertTriangle size={14} />
            <span>{uiText.errors.agentSourcesBlockedByPolicy}</span>
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
          {sources.length || missingSourceIds.length ? (
            <div className="agent-source-list" aria-label={uiText.agentDiscussion.sourcePickerAria}>
              {sources.map((source) => {
                const ready = source.extraction_status === "ready";
                const languageKnown = source.language !== "und";
                const languageAllowed =
                  projectLanguage !== null &&
                  (source.language === projectLanguage ||
                    crossLanguagePolicy === "explicit_reference");
                const selectable = ready && languageKnown && languageAllowed;
                const selected = selectedSourceIds.has(source.id);
                const languageTitle = !languageKnown
                  ? uiText.language.sourceUnknownDisabled
                  : !languageAllowed
                    ? uiText.language.sourceMismatchDisabled
                    : undefined;
                return (
                  <label className={!selectable && !selected ? "disabled" : ""} key={source.id} title={languageTitle}>
                    <input
                      checked={selected}
                      disabled={(!selectable && !selected) || busy !== null}
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
              {missingSourceIds.map((sourceId) => (
                <label className="warning" key={sourceId} title={uiText.agentDiscussion.sourceMissingHelp}>
                  <input
                    checked
                    disabled={busy !== null}
                    onChange={() => onToggleSource(sourceId)}
                    type="checkbox"
                  />
                  <span>
                    <strong>{uiText.agentDiscussion.sourceMissing}</strong>
                    <small>{sourceId}</small>
                  </span>
                </label>
              ))}
            </div>
          ) : (
            <p className="agent-source-empty">{uiText.agentDiscussion.sourcePickerEmpty}</p>
          )}
          <small className="agent-source-safety">{uiText.agentDiscussion.sourcePickerSafety}</small>
        </div>
        </details>
        {!hasScene && (
          <EmptyState
            icon={<MessageSquare />}
            title={uiText.agentDiscussion.noSceneTitle}
            text={uiText.agentDiscussion.noSceneText}
          />
        )}
        {result && (
          <div className="agent-result">
            <strong>{uiText.authorWorkspace.resultReady}</strong>
            <p>{uiText.authorWorkspace.resultBoundary}</p>
            <button type="button" className="primary" onClick={onOpenProposal}><SplitSquareVertical size={14} /> {uiText.authorWorkspace.reviewResult}</button>
            {(result.model_execution ?? result.proposal.provenance.model_execution) && <MetricRow label={uiText.modelRouting.actual} value={modelExecutionLabel(result.model_execution ?? result.proposal.provenance.model_execution)} />}
            <MetricRow label={uiText.agentDiscussion.proposalMetric} value={`${result.proposal.title} / v${result.proposal.version}`} />
            <MetricRow
              label={uiText.agentDiscussion.replacementMetric}
              value={result.proposal.artifact_type === "scene_draft" ? uiText.agentDiscussion.fullSceneDraft : uiText.agentDiscussion.discussionOnly}
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
  baseline,
  busy,
  canGenerate,
  canReview,
  currentDraftId,
  currentDraftReady,
  currentSceneId,
  currentProjectId,
  derivedDraftRef,
  dirty,
  filter,
  hasScene,
  onAccept,
  onApplyProjectStructure,
  onApplyOutlineLanguage,
  onApplyComposition,
  onCreateNew,
  onExtractCandidates,
  onFilterChange,
  onOpenCanonReview,
  onOpenPromotedDraft,
  onPromoteDraft,
  onReject,
  onReviewVersion,
  onSave,
  onSelect,
  onSourceDraftChange,
  onSubmitReview,
  onSwitchTarget,
  onTextChange,
  onTitleChange,
  onTypeChange,
  proposalSourceDraftId,
  proposalText,
  proposalTitle,
  proposalType,
  proposals,
  promotedDraft,
  reviewProposal,
  reviewVersion,
  selectedProposal,
  targetPolicy,
  targetScene,
  versions,
  versionsLoading
}: {
  baseline: ExactDraftLookup;
  busy: string | null;
  canGenerate: boolean;
  canReview: boolean;
  currentDraftId: string;
  currentDraftReady: boolean;
  currentSceneId: string;
  currentProjectId: string;
  derivedDraftRef: UniqueRefResolution;
  dirty: boolean;
  filter: ProposalStatus | "all";
  hasScene: boolean;
  onAccept: () => void;
  onApplyProjectStructure: () => void;
  onApplyOutlineLanguage: () => void;
  onApplyComposition: () => void;
  onCreateNew: () => void;
  onExtractCandidates: () => void;
  onFilterChange: (filter: ProposalStatus | "all") => void;
  onOpenCanonReview: () => void;
  onOpenPromotedDraft: () => void;
  onPromoteDraft: () => void;
  onReject: () => void;
  onReviewVersion: (version: number) => void;
  onSave: () => void;
  onSelect: (proposalId: string) => void;
  onSourceDraftChange: (draftId: string) => void;
  onSubmitReview: () => void;
  onSwitchTarget: () => void;
  onTextChange: (text: string) => void;
  onTitleChange: (title: string) => void;
  onTypeChange: (artifactType: ProposalArtifactType) => void;
  proposalSourceDraftId: string;
  proposalText: string;
  proposalTitle: string;
  proposalType: ProposalArtifactType;
  proposals: ProposalArtifact[];
  promotedDraft: ExactDraftLookup;
  reviewProposal: ProposalArtifact | null;
  reviewVersion: number | null;
  selectedProposal: ProposalArtifact | null;
  targetPolicy: PromotionTargetPolicy;
  targetScene: SceneOutline | null;
  versions: ProposalArtifact[];
  versionsLoading: boolean;
}) {
  const actionPolicy = selectedProposal
    ? proposalActionPolicy(selectedProposal.status, dirty, selectedProposal.artifact_type)
    : null;
  const locked = busy !== null || Boolean(selectedProposal && actionPolicy?.readonly);
  const canSave = canGenerate && busy === null && dirty && (
    !selectedProposal || Boolean(actionPolicy?.canSave)
  );
  const canSubmit = canGenerate && busy === null && Boolean(actionPolicy?.canSubmit);
  const canDecide = canReview && busy === null && Boolean(actionPolicy?.canDecide);
  const sourceBaseline = resolveUniqueProposalRef(selectedProposal?.source_refs ?? [], "draft");
  const staleDraftBaseline = sourceBaseline.status === "unique" && sourceBaseline.ref !== currentDraftId;
  const canPromoteDraft =
    currentDraftReady && !staleDraftBaseline &&
    canReview &&
    busy === null &&
    hasScene &&
    Boolean(actionPolicy?.canPromote) &&
    selectedProposal?.artifact_type === "scene_draft" &&
    targetPolicy.status === "ready" &&
    derivedDraftRef.status === "none";
  const effectiveSourceDraftId = proposalSourceDraftId || currentDraftId;
  const canPromoteCandidates =
    canReview &&
    busy === null &&
    Boolean(actionPolicy?.canPromote) &&
    selectedProposal?.artifact_type === "fact_draft" &&
    Boolean(effectiveSourceDraftId.trim());
  const canApplyProjectStructure =
    canReview &&
    busy === null &&
    Boolean(actionPolicy?.canPromote) &&
    selectedProposal?.artifact_type === "project_structure_draft";
  const sortedVersions = [...versions].sort((left, right) => right.version - left.version);
  const compositionBody = parseComposition(selectedProposal);
  const editedComposition = selectedProposal ? parseComposition({ ...selectedProposal, body: proposalText }) : null;
  const compositionApplied = compositionApplicationRecorded(selectedProposal);
  const canApplyComposition = canReview && compositionCanApply(selectedProposal, dirty, currentProjectId);
  const storedOutlinePatch = parseOutlineLanguagePatch(selectedProposal);
  const editedOutlinePatch = selectedProposal ? parseOutlineLanguagePatch({ ...selectedProposal, body: proposalText }) : null;
  const isOutlinePatch = Boolean(storedOutlinePatch || editedOutlinePatch);
  const outlineApplied = outlineLanguageApplicationRecorded(selectedProposal);
  const canApplyOutlineLanguage = canReview && canApplyOutlineLanguagePatch(selectedProposal, dirty, currentProjectId);
  const bodyEditor = <textarea
    className="proposal-textarea"
    value={proposalText}
    onChange={(event) => onTextChange(event.target.value)}
    spellCheck={false}
    aria-label={uiText.proposals.bodyAria}
    disabled={locked}
  />;

  return (
    <section className="proposal-panel" aria-label={uiText.proposals.ariaLabel}>
      <div className="proposal-header">
        <div>
          <span><SplitSquareVertical size={15} /> {uiText.proposals.title}</span>
          <small>
            {proposals.length} {uiText.proposals.countSuffix}
            {dirty && <mark className="unsaved-badge">{uiText.proposals.unsavedBadge}</mark>}
          </small>
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
          {compositionBody ? <>{editedComposition && <CompositionPreview body={editedComposition} />}<details><summary>{uiText.outlineLanguage.advanced}</summary>{bodyEditor}</details></> : isOutlinePatch ? <>
            {editedOutlinePatch ? <OutlineLanguagePreview patch={editedOutlinePatch} /> : <p className="proposal-inline-warning">{uiText.outlineLanguage.invalidPreview}</p>}
            <details><summary>{uiText.outlineLanguage.advanced}</summary>{bodyEditor}</details>
          </> : selectedProposal?.artifact_type === "scene_draft" ? <>
            {baseline.status === "ready" && reviewProposal?.version === selectedProposal.version ? <ManuscriptDiff before={baseline.draft.text} after={proposalText} labels={{ ...uiText.manuscript, title: uiText.manuscript.diffTitle }} /> : selectedProposal.source_refs.some((ref) => ref.kind === "draft") ? reviewProposal && reviewProposal.version !== selectedProposal.version ? <ManuscriptProse text={proposalText} /> : <p className="proposal-inline-warning">{baseline.status === "loading" || baseline.status === "idle" ? uiText.proposals.baselineLoading : uiText.proposals.baselineUnavailable}</p> : <ManuscriptDiff before="" after={proposalText} labels={{ ...uiText.manuscript, title: uiText.manuscript.diffTitle }} />}
            <details><summary>{uiText.manuscript.edit}</summary>{bodyEditor}</details>
          </> : bodyEditor}
          <div className="proposal-actions">
            <button type="button" disabled={!proposalText.trim()} onClick={() => exportAuthorText(proposalTitle || "StoryGraph", proposalText)}><Download size={14} /> {uiText.navigation.exportText}</button>
            {(!selectedProposal || actionPolicy?.editable) && (
              <button type="button" onClick={onSave} disabled={!canSave}>
                <Save size={14} /> {uiText.proposals.save}
              </button>
            )}
            {actionPolicy?.showSubmit && (
              <button type="button" onClick={onSubmitReview} disabled={!canSubmit}>
                <Clock3 size={14} /> {uiText.proposals.submitReview}
              </button>
            )}
            {actionPolicy?.showDecision && (
              <>
                <button type="button" onClick={onAccept} disabled={!canDecide}>
                  <Check size={14} /> {uiText.proposals.accept}
                </button>
                <button type="button" onClick={onReject} disabled={!canDecide}>
                  <X size={14} /> {uiText.proposals.reject}
                </button>
              </>
            )}
            {actionPolicy?.showPromotion && selectedProposal?.artifact_type === "project_structure_draft" && (
              <button type="button" onClick={onApplyProjectStructure} disabled={!canApplyProjectStructure}>
                <BookOpen size={14} /> {uiText.proposals.applyStructure}
              </button>
            )}
            {compositionBody && (selectedProposal?.status === "accepted" || compositionApplied) && <button type="button" disabled={busy !== null || !canApplyComposition} onClick={onApplyComposition}><BookOpen size={14} />{compositionApplied ? uiText.manuscript.compositionApplied : uiText.manuscript.applyComposition}</button>}
            {(canApplyOutlineLanguage || (canReview && outlineApplied && !dirty)) && <button type="button" disabled={busy !== null || outlineApplied} onClick={onApplyOutlineLanguage}>
              <BookOpen size={14} /> {outlineApplied ? uiText.outlineLanguage.alreadyApplied : uiText.outlineLanguage.apply}
            </button>}
          </div>
          {dirty && selectedProposal && (
            <p className="proposal-inline-warning">{uiText.proposals.dirtyActionHelp}</p>
          )}
          {actionPolicy?.showPromotion && selectedProposal?.artifact_type === "scene_draft" && (
            <div className="proposal-promotion-state">
              {staleDraftBaseline && <p className="proposal-inline-warning">{uiText.manuscript.staleProposal}</p>}
              {derivedDraftRef.status === "ambiguous" ? (
                <p className="proposal-inline-warning">{uiText.proposals.derivedDraftAmbiguous}</p>
              ) : derivedDraftRef.status === "unique" ? (
                <PromotedDraftSummary
                  canSwitchScene={Boolean(targetScene)}
                  currentSceneId={currentSceneId}
                  lookup={promotedDraft}
                  onOpen={onOpenPromotedDraft}
                  onSwitchScene={onSwitchTarget}
                />
              ) : (
                <>
                  {targetPolicy.status !== "ready" && (
                    <p className="proposal-inline-warning">
                      {targetPolicy.status === "ambiguous"
                        ? uiText.proposals.targetAmbiguous
                        : targetPolicy.status === "mismatch"
                          ? uiText.proposals.targetMismatch(targetScene?.title ?? targetPolicy.targetSceneId)
                          : uiText.proposals.targetMissing}
                    </p>
                  )}
                  {targetPolicy.status === "ready" && targetPolicy.targetSceneId === null && (
                    <p className="proposal-inline-note">{uiText.proposals.legacyCurrentTarget}</p>
                  )}
                  {(targetPolicy.status === "mismatch" || targetPolicy.status === "missing_scene") && targetScene && (
                    <button type="button" onClick={onSwitchTarget} disabled={busy !== null}>
                      <MapPin size={14} /> {uiText.proposals.switchTarget(targetScene.title)}
                    </button>
                  )}
                  <button type="button" onClick={onPromoteDraft} disabled={!canPromoteDraft}>
                    <FileText size={14} /> {uiText.proposals.promoteDraft}
                  </button>
                </>
              )}
            </div>
          )}
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
          {selectedProposal?.provenance.model_execution ? <MetricRow label={uiText.modelRouting.actual} value={modelExecutionLabel(selectedProposal.provenance.model_execution)} /> : selectedProposal?.provenance.model_ref ? <MetricRow label={uiText.modelRouting.historyModel} value={selectedProposal.provenance.model_ref} /> : null}
          <MetricRow label={uiText.proposals.metadataCreatedVia} value={proposalCreationMethod(selectedProposal, versions) ? formatProvenanceMethod(proposalCreationMethod(selectedProposal, versions)) : versionsLoading ? uiText.common.loading : uiText.common.notSet} />
          {proposalType === "fact_draft" && (
            <label>
              <span>{uiText.proposals.sourceDraft}</span>
              <input
                disabled={Boolean(selectedProposal && !actionPolicy?.editable && !actionPolicy?.showPromotion)}
                value={effectiveSourceDraftId}
                onChange={(event) => onSourceDraftChange(event.target.value)}
                placeholder={uiText.proposals.sourceDraftPlaceholder}
              />
            </label>
          )}
          {selectedProposal?.artifact_type === "fact_draft" && actionPolicy?.showPromotion && (
              <div className="proposal-side-actions">
                <button type="button" onClick={onExtractCandidates} disabled={!canPromoteCandidates}>
                  <ShieldCheck size={14} /> {uiText.proposals.extractCandidates}
                </button>
                <button type="button" onClick={onOpenCanonReview} disabled={busy !== null}>
                  <ShieldCheck size={14} /> {uiText.proposals.openCanonReview}
                </button>
              </div>
          )}
          <details open={isOutlinePatch || compositionBody ? undefined : true}>
          <summary>{uiText.outlineLanguage.auditDetails}</summary>
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
          </details>
        </div>
      </div>
      {selectedProposal && reviewProposal && (
        <section className="proposal-review" aria-label={uiText.proposals.reviewAria}>
          <div className="proposal-review-head">
            <div>
              <strong>{uiText.proposals.reviewTitle}</strong>
              <span>{isOutlinePatch ? uiText.outlineLanguage.historyHelp : uiText.proposals.reviewHelp}</span>
            </div>
            {versionsLoading && <RefreshCw className="spin" size={15} />}
          </div>
          <div className="proposal-history">
            <span>{uiText.proposals.historyTitle}</span>
            <div>
              {sortedVersions.map((version) => (
                <button
                  className={version.version === reviewVersion ? "selected" : ""}
                  key={version.version}
                  onClick={() => onReviewVersion(version.version)}
                  type="button"
                >
                  v{version.version} · {proposalStatusLabels[version.status]}
                </button>
              ))}
            </div>
          </div>
          <div className="proposal-review-metadata">
            <MetricRow label={uiText.proposals.metadataVersion} value={`v${reviewProposal.version}`} />
            <MetricRow label={uiText.proposals.metadataStatus} value={proposalStatusLabels[reviewProposal.status]} />
            <MetricRow
              label={uiText.language.artifactLanguageLabel}
              value={formatArtifactLanguage(reviewProposal.content_language, reviewProposal.language_inferred)}
            />
            <ListBlock title={uiText.proposals.refsTarget} items={formatProposalRefs(reviewProposal.target_refs)} />
            <ListBlock title={uiText.proposals.refsSource} items={formatProposalRefs(reviewProposal.source_refs)} />
          </div>
          <details className="proposal-version-content">
            <summary>{uiText.proposals.versionContent}</summary>
            <span>{uiText.proposals.historicalTitle}</span>
            <strong>{reviewProposal.title}</strong>
            <pre>{reviewProposal.body}</pre>
          </details>
          {!isOutlinePatch && !compositionBody && (selectedProposal.artifact_type !== "scene_draft" || reviewProposal.version !== selectedProposal.version) && <ProposalReviewDiff baseline={baseline} after={reviewProposal?.body ?? ""} />}
        </section>
      )}
    </section>
  );
}

function PromotedDraftSummary({
  canSwitchScene,
  currentSceneId,
  lookup,
  onOpen,
  onSwitchScene
}: {
  canSwitchScene: boolean;
  currentSceneId: string;
  lookup: ExactDraftLookup;
  onOpen: () => void;
  onSwitchScene: () => void;
}) {
  if (lookup.status === "loading") {
    return <p><RefreshCw className="spin" size={14} /> {uiText.proposals.promotedDraftLoading}</p>;
  }
  if (lookup.status !== "ready") {
    return <p className="proposal-inline-warning">{uiText.proposals.promotedDraftUnavailable}</p>;
  }
  const scopeMatches = exactDraftMatchesEditorScene(lookup.draft.scene_id, currentSceneId);
  return (
    <details className="promoted-draft-summary">
      <summary>{uiText.proposals.alreadyPromoted(lookup.draft.id, lookup.draft.version)}</summary>
      <MetricRow label={uiText.proposals.metadataStatus} value={lookup.draft.discarded ? uiText.proposals.draftDiscarded : uiText.proposals.draftAvailable} />
      <MetricRow label={uiText.language.artifactLanguageLabel} value={formatArtifactLanguage(lookup.draft.content_language, lookup.draft.language_inferred)} />
      <MetricRow label={uiText.proposals.targetScene} value={lookup.draft.scene_id} />
      {scopeMatches ? (
        <button type="button" onClick={onOpen}>
          <FileText size={14} /> {uiText.proposals.openPromotedDraft}
        </button>
      ) : (
        <div className="promoted-draft-scope-warning">
          <p className="proposal-inline-warning">{uiText.proposals.openDraftSwitchFirst}</p>
          <button type="button" onClick={onSwitchScene} disabled={!canSwitchScene}>
            <MapPin size={14} /> {uiText.proposals.switchToDraftScene}
          </button>
        </div>
      )}
      <pre>{lookup.draft.text}</pre>
    </details>
  );
}

function ProposalReviewDiff({ baseline, after }: { baseline: ExactDraftLookup; after: string }) {
  const statusText = baseline.status === "none"
    ? uiText.proposals.baselineNone
    : baseline.status === "ambiguous"
      ? uiText.proposals.baselineAmbiguous
      : baseline.status === "missing_target"
        ? uiText.proposals.baselineTargetMissing
        : baseline.status === "loading" || baseline.status === "idle"
          ? uiText.proposals.baselineLoading
          : baseline.status === "error"
            ? uiText.proposals.baselineUnavailable
            : null;
  return (
    <section className="proposal-diff" aria-label={uiText.proposals.diffAria}>
      <div className="proposal-review-head">
        <div>
          <strong>{uiText.proposals.diffTitle}</strong>
          <span>{uiText.proposals.diffHelp}</span>
        </div>
      </div>
      {statusText ? (
        <p className={baseline.status === "loading" || baseline.status === "idle" ? "" : "proposal-inline-warning"}>
          {statusText}
        </p>
      ) : baseline.status === "ready" ? (
        <>
          <div className="proposal-baseline-meta">
            <span>{uiText.proposals.baselineExact(baseline.draft.id, baseline.draft.version)}</span>
            <span>{formatArtifactLanguage(baseline.draft.content_language, baseline.draft.language_inferred)}</span>
            <span>{baseline.draft.discarded ? uiText.proposals.draftDiscarded : uiText.proposals.draftAvailable}</span>
          </div>
          <ManuscriptDiff before={baseline.draft.text} after={after} labels={{ ...uiText.manuscript, title: uiText.manuscript.diffTitle }} />
        </>
      ) : null}
    </section>
  );
}

function ProjectSidebar({
  busy,
  canReview,
  chapterForm,
  characterForm,
  currentChapterId,
  editingChapterId,
  readingChapterId,
  onEditChapter,
  chapterTitleEditor,
  onChapterTitleChange,
  onSaveChapterTitle,
  onCancelChapterTitle,
  chapterMetadataTarget,
  chapterMetadataSaveAllowed,
  onLoadChapterMetadata,
  onLoadSceneMetadata,
  sceneMetadataSaveAllowed,
  onSelectChapter,
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
  workspaceLoadError,
  worldRuleForm
}: {
  busy: string | null;
  canReview: boolean;
  chapterForm: ChapterForm;
  characterForm: CharacterForm;
  currentChapterId: string;
  editingChapterId: string | null;
  chapterTitleEditor: ChapterTitleEditor | null;
  onChapterTitleChange: (title: string) => void;
  onSaveChapterTitle: () => void;
  onCancelChapterTitle: () => void;
  chapterMetadataTarget: (ChapterEditorScope & { baseline: ChapterForm }) | null;
  chapterMetadataSaveAllowed: boolean;
  onLoadChapterMetadata: (chapter: ChapterOutline) => void;
  onLoadSceneMetadata: (scene: SceneOutline) => void;
  sceneMetadataSaveAllowed: boolean;
  readingChapterId: string | null;
  onEditChapter: (id: string) => void;
  onSelectChapter: (id: string) => void;
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
  workspaceLoadError: boolean;
  worldRuleForm: WorldRuleForm;
}) {
  const chapters = selectedProject?.chapters ?? [];
  const sceneChapterId = sceneForm.chapter_id || currentChapterId;
  const selectedBuiltinDemo = selectedProject?.id === "project_fantasy_demo";
  const outlineDetailsRef = useRef<HTMLDetailsElement | null>(null);
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
    onLoadSceneMetadata(selectedScene);
  };

  const loadSelectedChapter = () => {
    if (!selectedChapter) return;
    onLoadChapterMetadata(selectedChapter);
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
          <summary className="section-title">{uiText.authorWorkspace.treeTitle}</summary>
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

              {selectedProject && (
                <details className="project-card"><summary>{uiText.authorWorkspace.projectDetails}</summary>
                  <strong>{selectedProject.title}</strong>
                  <span>
                    {genreLabel(selectedProject.genre, uiText.genres, uiText.sidebar.uncategorized)} / {formatProjectLanguage(selectedProject)}
                  </span>
                  <span>
                    {chapters.length} {uiText.sidebar.chapterCount} / {projectSceneCount} {uiText.sidebar.sceneCount}
                  </span>
                  <span>{String(selectedProject.properties.narrative_pov ?? uiText.sidebar.povUnset)}</span>
                </details>
              )}
            </>
          ) : (
            <div className="project-empty">
              {workspaceLoadError ? uiText.navigation.connectionFailed : workspaceLoaded ? uiText.sidebar.projectEmpty : uiText.sidebar.projectLoading}
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
            <ProjectTree projectId={projectId} chapters={chapters} sceneId={readingChapterId ? "" : sceneId} selectedChapterId={readingChapterId} editingChapterId={editingChapterId} onEditChapter={onEditChapter}
              busy={busy !== null} onSelectScene={onSelectScene} onSelectChapter={onSelectChapter}
              chapterEditor={<div className="chapter-inline-editor">
                <label><span>{uiText.authorWorkspace.editingChapter}</span><input aria-label={uiText.authorWorkspace.chapterTitle} value={chapterTitleEditor?.title ?? ""} disabled={busy !== null} onChange={(event) => onChapterTitleChange(event.target.value)} /></label>
                <small>{uiText.authorWorkspace.chapterSavedExplicitly}</small>
                <button type="button" onClick={onSaveChapterTitle} disabled={!canReview || busy !== null || !chapterTitleEditor?.title.trim() || !chapterTitleIsDirty(chapterTitleEditor)}><Save size={13} /> {uiText.common.save}</button>
                <button type="button" disabled={busy !== null} onClick={onCancelChapterTitle}>{uiText.common.cancel}</button>
                <button type="button" disabled={busy !== null} onClick={() => { if (selectedChapter) onLoadChapterMetadata(selectedChapter); if (outlineDetailsRef.current) { outlineDetailsRef.current.open = true; outlineDetailsRef.current.scrollIntoView({ block: "nearest", behavior: "smooth" }); } }}>{uiText.authorWorkspace.chapterDetails}</button>
              </div>}
            />
          ) : (
            <EmptyState
              icon={<BookOpen />}
              title={workspaceLoadError ? uiText.navigation.connectionFailed : uiText.sidebar.noProjectTreeTitle}
              text={workspaceLoadError ? uiText.navigation.connectionFailedHelp : uiText.sidebar.noProjectTreeText}
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

        <details ref={outlineDetailsRef} className="sidebar-section seed-panel">
          <summary className="section-title">{uiText.sidebar.outlineTitle}</summary>
          <p className="metadata-target-label">{chapterMetadataTarget ? `${uiText.authorWorkspace.editingChapter}: ${chapterMetadataTarget.baseline.title} (${chapterMetadataTarget.chapterId})` : uiText.authorWorkspace.chapterTargetRequired}</p>
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
              disabled={!canReview || !chapterMetadataSaveAllowed || busy !== null}
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
              disabled={!canReview || !selectedScene || busy !== null || !sceneMetadataSaveAllowed}
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

function PaneResizeHandle({
  ariaLabel,
  help,
  max,
  min,
  onChange,
  onReset,
  orientation,
  value
}: {
  ariaLabel: string;
  help: string;
  max: number;
  min: number;
  onChange: (value: number, commit: boolean) => void;
  onReset: () => void;
  orientation: "horizontal" | "vertical";
  value: number;
}) {
  const dragRef = useRef<{
    pointerId: number;
    startPosition: number;
    startValue: number;
    lastValue: number;
  } | null>(null);
  const pointerPosition = (event: React.PointerEvent<HTMLDivElement>) =>
    orientation === "horizontal" ? event.clientY : event.clientX;
  const finishDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    dragRef.current = null;
    onChange(drag.lastValue, true);
  };

  return (
    <div
      aria-label={ariaLabel}
      aria-orientation={orientation}
      aria-valuemax={Math.round(max)}
      aria-valuemin={Math.round(min)}
      aria-valuenow={Math.round(value)}
      className={`pane-resize-handle ${orientation}`}
      onDoubleClick={onReset}
      onKeyDown={(event) => {
        const next = separatorKeyboardValue({
          key: event.key,
          value,
          min,
          max,
          orientation,
          largeStep: event.shiftKey
        });
        if (next === null) return;
        event.preventDefault();
        onChange(next, true);
      }}
      onPointerCancel={finishDrag}
      onPointerDown={(event) => {
        if (event.button !== 0) return;
        event.preventDefault();
        event.currentTarget.setPointerCapture(event.pointerId);
        dragRef.current = {
          pointerId: event.pointerId,
          startPosition: pointerPosition(event),
          startValue: value,
          lastValue: value
        };
      }}
      onPointerMove={(event) => {
        const drag = dragRef.current;
        if (!drag || drag.pointerId !== event.pointerId) return;
        const next = Math.min(
          max,
          Math.max(min, drag.startValue + pointerPosition(event) - drag.startPosition)
        );
        drag.lastValue = next;
        onChange(next, false);
      }}
      onPointerUp={finishDrag}
      role="separator"
      tabIndex={0}
      title={help}
    >
      <span aria-hidden="true" />
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
  canAdoptSources,
  structureReady,
  structureModelLabel,
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
  onSaveSelection,
  onSaveProposal,
  onSaveStyle,
  onUpdateLanguage,
  onUseWithAgent,
  projectLanguage,
  summary
}: {
  busy: string | null;
  canGenerate: boolean;
  canAdoptSources: boolean;
  structureReady: boolean;
  structureModelLabel: string;
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
  onSaveSelection: (document: SourceDocument, range: ManuscriptSelection) => void;
  onSaveProposal: (document: SourceDocument) => void;
  onSaveStyle: (document: SourceDocument) => void;
  onUpdateLanguage: (document: SourceDocumentSummary, language: "zh-CN" | "en-US") => void;
  onUseWithAgent: (document: SourceDocumentSummary) => void;
  projectLanguage: AppLocale | null;
  summary: SourceDocumentSummary | null;
}) {
  const [languageDraft, setLanguageDraft] = useState<SourceLanguage>("zh-CN");
  const [sourceSelection, setSourceSelection] = useState<ManuscriptSelection | null>(null);
  useEffect(() => { setSourceSelection(null); }, [doc?.id, doc?.updated_at]);
  useEffect(() => {
    if (summary?.language && summary.language !== "und") {
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
  const editableLanguage = languageDraft === "zh-CN" || languageDraft === "en-US";
  const sameLanguage = doc.language === projectLanguage;
  const canManageSource = canGenerate && hasProject && busy === null;
  const canSceneBridge = ready && sameLanguage && canGenerate && hasScene && busy === null;
  const canSourceAdopt = canSceneBridge && canAdoptSources;
  const canProjectBridge = ready && sameLanguage && canGenerate && hasProject && busy === null;
  const canAnalyzeStructure =
    ready && canManageSource && structureReady &&
    projectLanguage !== null &&
    doc.language !== "und" &&
    (doc.language === projectLanguage || crossLanguagePolicy === "explicit_reference");
  const canArchive = hasProject && canGenerate && busy === null;
  const agentEligibility = sourceAgentEligibility(doc, projectLanguage, crossLanguagePolicy);
  const canUseWithAgent =
    canGenerate && hasScene && projectLanguage !== null && busy === null && sourceCanHandoff(doc);
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
          <span>{formatStatus(doc.extraction_status)}</span>
        </div>
      </div>
      <details className="source-language-disclosure"><summary>{uiText.language.sourceLanguageLabel}: {formatSourceLanguage(doc.language)}</summary>
      <div className="source-language-editor">
        <label>
          <span>{uiText.language.sourceLanguageLabel}</span>
          <select
            value={languageDraft}
            onChange={(event) => setLanguageDraft(event.target.value)}
            disabled={!canManageSource}
          >
            {languageDraft !== "zh-CN" && languageDraft !== "en-US" && (
              <option value={languageDraft}>{formatSourceLanguage(languageDraft)}</option>
            )}
            <option value="zh-CN">{uiText.language.chinese}</option>
            <option value="en-US">{uiText.language.english}</option>
          </select>
        </label>
        <button
          type="button"
          disabled={!canManageSource || !editableLanguage || languageDraft === doc.language}
          onClick={() => {
            if (editableLanguage) onUpdateLanguage(summary, languageDraft);
          }}
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
      </details>
      <div className="reader-bridge">
        <span>{uiText.library.bridgeText}</span>
        <div>
          <button
            className="primary"
            disabled={!canUseWithAgent}
            onClick={() => onUseWithAgent(summary)}
            title={
              !hasScene
                ? uiText.errors.selectScene
                : agentEligibility === "language_mismatch"
                  ? uiText.library.useWithAgentMismatchTitle
                  : agentEligibility === "eligible"
                  ? uiText.library.useWithAgentTitle
                  : formatSourceAgentEligibility(agentEligibility)
            }
            type="button"
          >
            <MessageSquare size={14} /> {uiText.library.useWithAgent}
          </button>
          <details className="source-advanced-actions"><summary>{uiText.manuscript.sourceAdvanced}</summary><small>{doc.id} · {formatFileSize(doc.byte_size)}</small><small>{uiText.library.buildStructure}: {structureModelLabel}</small><div>
          <button
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
            disabled={!canSourceAdopt}
            onClick={() => onSaveDraft(doc)}
            title={!canAdoptSources ? uiText.sidebar.requireFullPermission : contentBridgeLanguageTitle ?? uiText.manuscript.saveWholeSource}
            type="button"
          >
            <FileText size={14} /> {uiText.manuscript.saveWholeSource}
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
          </div></details>
        </div>
      </div>
      {doc.extraction_status === "failed" ? (
        <div className="reader-error">
          <AlertTriangle size={17} />
          <strong>{uiText.library.readErrorTitle}</strong>
          <span>{sourceImportFailureMessage(doc)}</span>
          {doc.error && !importErrorCode(doc.error) && (
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
              <span>{doc.warnings.slice(0, 2).map(sourceImportWarningMessage).join(" ")}</span>
              <details>
                <summary>{uiText.errors.technicalDetails}</summary>
                <code>{doc.warnings.slice(0, 2).join("\n")}</code>
              </details>
            </div>
          )}
          <div className="source-manuscript-selection"><strong>{uiText.manuscript.sourceOriginal}</strong><p>{uiText.manuscript.sourceHelp}</p><button type="button" disabled={!sourceSelection || !canSourceAdopt} title={!canAdoptSources ? uiText.sidebar.requireFullPermission : contentBridgeLanguageTitle ?? undefined} onClick={() => { if (sourceSelection) onSaveSelection(doc, sourceSelection); }}><FileText size={14} />{uiText.manuscript.useSource}</button>{contentBridgeLanguageTitle && <p className="proposal-inline-warning">{contentBridgeLanguageTitle}</p>}</div>
          <pre onMouseUp={(event) => setSourceSelection(selectedManuscriptRange(event.currentTarget, window.getSelection()))} onKeyUp={(event) => setSourceSelection(selectedManuscriptRange(event.currentTarget, window.getSelection()))}>{doc.extracted_text}</pre>
        </div>
      )}
    </div>
  );
}

function AgentSettingsInspector({
  apiBase,
  onApiBaseChange,
  connectionLocked,
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
  onSettingsChange,
  updateStatus,
  backendVersion
}: {
  apiBase: string;
  onApiBaseChange: (value: string) => void;
  connectionLocked: boolean;
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
  onSettingsChange: (settings: AgentSettings) => void;
  updateStatus: UpdateStatus;
  backendVersion: BackendVersion;
}) {
  const [connectionInput, setConnectionInput] = useState(apiBase);
  useEffect(() => { setConnectionInput(apiBase); }, [apiBase]);
  const descriptions = defaultPermissionDescriptions;
  const updateTarget = updateStatus.installerUrl ?? updateStatus.releaseUrl;

  return (
    <div className="settings-panel">
      <details className="settings-block settings-disclosure"><summary>{uiText.modelRouting.presetCollapsed}</summary><AgentPresets apiBase={apiBase} settings={settings} busy={busy !== null} onChange={onSettingsChange} /></details>
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
            {SUPPORTED_UI_LOCALES.map((key) => <option key={key} value={key}>{localeRegistry[key].label}</option>)}
          </select>
        </label>
      </section>
      <details className="settings-block settings-disclosure">
        <summary><Database size={15} /> {uiText.navigation.connection}</summary>
        <label><span>{uiText.settings.apiAddress}</span><input value={connectionInput} onChange={(event) => setConnectionInput(event.target.value)} disabled={connectionLocked || busy !== null} aria-label={uiText.runtime.apiAddressAria} /></label>
        <button type="button" disabled={connectionLocked || busy !== null || !normalizeApiBase(connectionInput) || connectionInput.replace(/\/$/, "") === apiBase} onClick={() => onApiBaseChange(connectionInput.trim().replace(/\/$/, ""))}>{uiText.navigation.connect}</button>
      </details>
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

      <ModelRoutingSettings key={apiBase} apiBase={apiBase} settings={settings} form={form} onFormChange={onFormChange} apiKeyInput={apiKeyInput} onApiKeyChange={onApiKeyChange} clearApiKey={clearApiKey} onClearApiKeyChange={onClearApiKeyChange} busy={busy !== null || !settings} />

      <section className="settings-block">
        <div className="settings-title"><Lock size={15} /> {uiText.settings.permissionSection}</div>
        <div className="permission-stack">
          {permissionLevels.map((level) => (
            <label className={`permission-option ${form.permission_level === level ? "selected" : ""}`} key={level}>
              <input
                checked={form.permission_level === level}
                disabled={busy !== null || !settings}
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
        <MetricRow label={uiText.navigation.backendVersion} value={backendVersion.version ?? uiText.navigation.backendVersionUnknown} />
        {backendVersion.source === "openapi" && <small>{uiText.navigation.backendVersionLegacy}</small>}
        {backendVersionCompatibility(APP_VERSION, backendVersion) === "mismatch" && <p className="preset-error" role="alert">{uiText.navigation.backendVersionMismatch(APP_VERSION, backendVersion.version!)}</p>}
        {backendVersionCompatibility(APP_VERSION, backendVersion) === "unknown" && <small>{uiText.navigation.backendVersionUnknownHelp}</small>}
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
          {["available", "error"].includes(updateStatus.state) && updateStatus.canInstall && (
            <button
              className="inline-update-button"
              onClick={onInstallUpdate}
              type="button"
              disabled={busy !== null}
            >
              <Download size={14} /> {uiText.settings.installUpdate}
            </button>
          )}
          {((updateStatus.state === "available" && !updateStatus.canInstall) || updateStatus.state === "error") && updateTarget && (
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
        <button onClick={onUpdateCheck} type="button" disabled={busy !== null || ["downloading", "awaiting_edits", "installing"].includes(updateStatus.state)}>
          <RefreshCw size={15} /> {uiText.settings.checkUpdates}
        </button>
        <button className="primary" onClick={onSave} type="button" disabled={busy !== null || !settings}>
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
            <span>{fact.subject_id} {localizeGraphLabel(fact.relation)} {fact.object_id}</span>
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
              <b>{localizeGraphLabel(edge.type)}</b>
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
  return <button className={active ? "active" : ""} onClick={onClick} type="button" title={label} aria-label={label}>{icon}<span>{label}</span></button>;
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
    return taskConnectionReady(settings, "writing")
      ? modelExecutionLabel(resolvedTask(settings, "writing"))
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
  const result = await extractDocumentFile(file);
  const text = result.text === null ? null : normalizeImportedText(result.text);
  const language = languageOverride ?? detectSourceLanguage(text ?? "");
  return {
    title: file.name, relative_path: getImportPath(file), media_type: mediaType,
    language, byte_size: result.byteSize, checksum_sha256: result.checksumSha256,
    extraction_status: result.errorCode ? "failed" : "ready", extracted_text: text,
    warnings: result.warnings.map((code) => `import_warning:${code}`),
    error: result.errorCode ? `import_error:${result.errorCode}` : null,
    provenance: { imported_by: "author", imported_via: "local_file", source_last_modified_ms: file.lastModified, note: "workbench.source.import" }
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
  if (language === "und") return uiText.language.undetermined;
  return language;
}

function formatSourceAgentEligibility(eligibility: SourceAgentEligibility): string {
  if (eligibility === "not_ready") return uiText.library.useWithAgentNotReady;
  if (eligibility === "unknown_language") return uiText.language.sourceUnknownDisabled;
  if (eligibility === "project_language_unavailable") return uiText.errors.projectLanguageRequired;
  if (eligibility === "language_mismatch") return uiText.language.sourceMismatchDisabled;
  return uiText.library.useWithAgentTitle;
}

function formatArtifactLanguage(
  language: AppLocale | null | undefined,
  inferred: boolean | undefined
): string {
  if (!language) return uiText.language.historicalLanguageUnknown;
  const label = language === "zh-CN" ? uiText.language.chinese : uiText.language.english;
  return `${label}${inferred ? uiText.language.inferredLanguage : ""}`;
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
  if (mediaType === "application/rtf") return uiText.library.formats.rtf;
  return uiText.library.formats.docx;
}

function sourceFileAccept(mediaType: SourceMediaType): string {
  if (mediaType === "text/plain") return ".txt";
  if (mediaType === "text/markdown") return ".md,.markdown";
  if (mediaType === "application/rtf") return ".rtf";
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

function outlineLanguageFailureMessage(error: unknown): string | null {
  const key = outlineLanguageFailureKey(error);
  return key ? uiText.errors[key] : null;
}

function manuscriptFailureMessage(error: unknown): string | null {
  if (!(error instanceof ApiRequestError)) return null;
  const messages: Record<string, string> = { composition_backend_unsupported: uiText.manuscript.localBackendOnly, source_adoption_backend_unsupported: uiText.manuscript.localBackendOnly, composition_input_too_large: uiText.manuscript.compositionTooLarge, composition_invalid: uiText.manuscript.compositionInvalid, composition_stale: uiText.manuscript.compositionStale, source_language_mismatch: uiText.errors.sourceContentLanguageMismatch, source_stale: uiText.manuscript.sourceStale, draft_baseline_stale: uiText.manuscript.staleProposal };
  return messages[error.category ?? ""] ?? null;
}

function isLocalizedUserError(message: string): boolean {
  return [...Object.values(uiText.errors), ...Object.values(uiText.manuscript), ...Object.values(uiText.documentImport)].some(
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

function loadSourcePaneLayout(): SourcePaneLayout {
  if (typeof window === "undefined") return { ...DEFAULT_SOURCE_PANE_LAYOUT };
  try {
    return readSourcePaneLayout(window.localStorage);
  } catch {
    return { ...DEFAULT_SOURCE_PANE_LAYOUT };
  }
}

function persistSourcePaneLayout(layout: SourcePaneLayout): void {
  if (typeof window === "undefined") return;
  try {
    writeSourcePaneLayout(window.localStorage, layout);
  } catch {
    // Resizing remains available for this session if local storage is unavailable.
  }
}

const fallbackSteps: WorkflowStep[] = [
  { name: "build_context", status: "pending", artifact_refs: {} },
  { name: "write_draft", status: "pending", artifact_refs: {} },
  { name: "check_continuity", status: "pending", artifact_refs: {} },
  { name: "extract_state", status: "pending", artifact_refs: {} },
  { name: "human_review", status: "pending", artifact_refs: {} }
];
