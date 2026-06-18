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
import "./styles.css";

const defaultDraft = `Lin Jin climbed the old bell tower after the rain stopped.

The bell rings early. The sound was wrong: too clean, too deliberate, like a signal sent through stone.

Under the frame he found half black wax seal pressed into the dust. He closed his hand around it before Helian Ya could see how sharply his suspicion had changed.`;

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

export default function App() {
  const [apiBase, setApiBase] = useState("http://127.0.0.1:8000");
  const [projectId, setProjectId] = useState(demoProject.projectId);
  const [sceneId, setSceneId] = useState(demoProject.sceneId);
  const [activeTab, setActiveTab] = useState<InspectorTab>("context");
  const [contextPack, setContextPack] = useState<ContextPack | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [draftText, setDraftText] = useState(defaultDraft);
  const [draftSummary, setDraftSummary] = useState("Lin Jin finds a tower clue without learning the lineage secret.");
  const [run, setRun] = useState<WorkflowRun | null>(null);
  const [runEvents, setRunEvents] = useState<WorkflowStep[]>([]);
  const [continuityReport, setContinuityReport] = useState<ContinuityReport | null>(null);
  const [facts, setFacts] = useState<CandidateFact[]>([]);
  const [agentSettings, setAgentSettings] = useState<AgentSettings | null>(null);
  const [agentForm, setAgentForm] = useState<AgentSettingsUpdate>(defaultAgentForm);
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
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
          ? `No supported documents found. Skipped ${summary.skipped} file${summary.skipped === 1 ? "" : "s"}.`
          : "No documents selected."
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
      `Imported ${importedCount} document${importedCount === 1 ? "" : "s"}.`
    ];
    if (summary.failed) parts.push(`${summary.failed} need attention.`);
    if (summary.skipped) parts.push(`Skipped ${summary.skipped} unsupported file${summary.skipped === 1 ? "" : "s"}.`);
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
    setNotice("Local library cleared. Canon unchanged.");
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
    setNotice("Agent settings saved.");
  }, [agentForm, apiBase, apiKeyInput, clearApiKey]);

  const seedDemo = useCallback(async () => {
    const result = await apiPost<DemoSeedResult>(apiBase, "/demo/seed", {
      reviewer: "author",
      rationale: "Author explicitly initialized the bundled fantasy demo from the workbench.",
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
      `Demo ready: ${result.nodes_created} nodes and ${result.relationships_created} relationships seeded.`
    );
  }, [apiBase, refreshFacts]);

  const buildContext = useCallback(async () => {
    const pack = await apiPost<ContextPack>(apiBase, `${endpoint}/context-pack`);
    setContextPack(pack);
    setActiveTab("context");
    setNotice("Context Pack refreshed.");
  }, [apiBase, endpoint]);

  const saveDraft = useCallback(async () => {
    const saved = await apiPost<Draft>(apiBase, `${endpoint}/draft`, {
      text: draftText,
      summary: draftSummary
    });
    setDraft(saved);
    setNotice(`Draft v${saved.version} saved.`);
  }, [apiBase, draftSummary, draftText, endpoint]);

  const generateDraft = useCallback(async () => {
    const saved = await apiPost<Draft>(apiBase, `${endpoint}/draft`);
    setDraft(saved);
    setDraftText(saved.text);
    setDraftSummary(saved.summary ?? "");
    setNotice(`Draft v${saved.version} generated.`);
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
    setNotice(`Workflow ${result.workflow_run.status}.`);
  }, [apiBase, endpoint, refreshFacts]);

  const reviewFact = useCallback(
    async (factId: string, action: "accept" | "reject" | "defer") => {
      await apiPost<CandidateFact>(
        apiBase,
        `/projects/${projectId}/facts/${factId}/${action}`,
        { reviewer: "author", note: `${action} from workbench` }
      );
      await refreshFacts();
      setNotice(`Fact ${action}ed.`);
    },
    [apiBase, projectId, refreshFacts]
  );

  useEffect(() => {
    refreshFacts().catch(() => undefined);
  }, [refreshFacts]);

  useEffect(() => {
    refreshAgentSettings().catch(() => undefined);
  }, [refreshAgentSettings]);

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
            <span>Canon-safe fiction workbench</span>
          </div>
        </div>
        <label className="api-control">
          <Database size={15} />
          <input
            value={apiBase}
            onChange={(event) => setApiBase(event.target.value)}
            aria-label="API base URL"
          />
        </label>
        <div className="top-actions">
          <StatusDot label="FastAPI" tone="good" />
          <StatusDot label={agentSettings?.permission_level ?? "permission"} tone={permissionTone(agentSettings?.permission_level)} />
          <button className="icon-button" title="Settings" type="button" onClick={() => setActiveTab("settings")}>
            <Settings size={17} />
          </button>
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <div className="sidebar-section">
            <div className="section-title">Project</div>
            <div className="project-title">{demoProject.title}</div>
            <div className="project-id">{projectId}</div>
            <button
              className="sidebar-action"
              disabled={!canReview || busy !== null}
              onClick={() => runAction("seed-demo", seedDemo)}
              title={canReview ? "Seed bundled demo" : "Full permission required"}
              type="button"
            >
              <Database size={15} /> Seed Demo
            </button>
          </div>
          <nav className="scene-tree" aria-label="Scene tree">
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
            Drafts cannot mutate canon.
          </div>
        </aside>

        <main className="editor">
          <section className="scene-toolbar">
            <div>
              <h1>The Tower Search</h1>
              <p>{sceneId} / POV {contextPack?.pov_character_id ?? "character_linj"}</p>
            </div>
            <div className="toolbar-actions">
              <button onClick={() => runAction("context", buildContext)} type="button">
                <RefreshCw size={16} /> Context
              </button>
              <button onClick={() => runAction("save", saveDraft)} type="button" disabled={!canGenerate}>
                <Save size={16} /> Save
              </button>
              <button
                onClick={() => runAction("draft", generateDraft)}
                type="button"
                disabled={missingCritical || !canGenerate}
              >
                <FileText size={16} /> Draft
              </button>
              <button
                className="primary"
                onClick={() => runAction("run", runScene)}
                type="button"
                disabled={!canGenerate}
              >
                <Play size={16} /> Run
              </button>
            </div>
          </section>

          {(error || notice) && (
            <div className={`message ${error ? "error" : "notice"}`}>
              {error ? <AlertTriangle size={16} /> : <Check size={16} />}
              <span>{error ?? notice}</span>
            </div>
          )}

          <section className="meta-grid" aria-label="Scene metadata">
            <Meta label="Goal" value={contextPack?.scene_goal ?? "search for the missing sealed letter"} />
            <Meta label="Conflict" value={contextPack?.conflict ?? "the tower is controlled by a hostile faction"} />
            <Meta label="Timeline" value={contextPack?.timeline_position ?? "three days after the capital coup"} />
            <Meta label="Location" value={contextPack?.location_id ?? "location_old_bell_tower"} />
          </section>

          <section className="library-panel" aria-label="Local document library">
            <div className="library-header">
              <div>
                <span><Library size={15} /> Library / Import</span>
                <small>{libraryDocuments.length} local document{libraryDocuments.length === 1 ? "" : "s"} / not canon</small>
              </div>
              <div className="library-actions">
                <label className="import-button">
                  <FileUp size={15} />
                  Files
                  <input
                    accept=".txt,.md,.markdown,.docx"
                    multiple
                    onChange={handleLibraryInputChange}
                    type="file"
                  />
                </label>
                <label className="import-button">
                  <FolderOpen size={15} />
                  Folder
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
                  <X size={15} /> Clear
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
                    title="No Imported Documents"
                    text="Use Files or Folder to load txt, md, or docx into the local reader."
                  />
                )}
              </div>
              <DocumentReader document={selectedLibraryDocument} />
            </div>
          </section>

          <section className="draft-surface">
            <div className="draft-header">
              <span>Scene Draft</span>
              <small>{draft ? `v${draft.version} / ${draft.id}` : "local unsaved draft"}</small>
            </div>
            <textarea
              value={draftText}
              onChange={(event) => setDraftText(event.target.value)}
              spellCheck={false}
              aria-label="Scene draft text"
            />
            <input
              className="summary-input"
              value={draftSummary}
              onChange={(event) => setDraftSummary(event.target.value)}
              aria-label="Draft summary"
            />
          </section>

          <section className="run-panel">
            <div className="run-head">
              <div>
                <span>Agent Run</span>
                <small>{run?.id ?? "No run yet"}</small>
              </div>
              <StatusDot label={run?.status ?? "idle"} tone={statusTone(run?.status)} />
            </div>
            <div className="step-track">
              {(runEvents.length ? runEvents : fallbackSteps).map((step) => (
                <div key={step.name} className={`step ${step.status}`}>
                  <span>{step.name}</span>
                  <small>{step.status}</small>
                </div>
              ))}
            </div>
          </section>
        </main>

        <aside className="inspector">
          <div className="tabs" role="tablist">
            <TabButton active={activeTab === "context"} onClick={() => setActiveTab("context")} icon={<Boxes size={15} />} label="Context" />
            <TabButton active={activeTab === "continuity"} onClick={() => setActiveTab("continuity")} icon={<Activity size={15} />} label="QA" />
            <TabButton active={activeTab === "facts"} onClick={() => setActiveTab("facts")} icon={<ShieldCheck size={15} />} label="Facts" />
            <TabButton active={activeTab === "settings"} onClick={() => setActiveTab("settings")} icon={<Settings size={15} />} label="Settings" />
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
              settings={agentSettings}
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
          title="Select a Document"
          text="Imported content is held in browser memory only."
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
          <strong>Could not read this document.</strong>
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
  settings
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
  settings: AgentSettings | null;
}) {
  const descriptions = settings?.permission_descriptions ?? defaultPermissionDescriptions;
  const apiKeyStatus = settings?.api_key_configured
    ? `Configured (${settings.api_key_preview ?? "hidden"})`
    : "Not configured";

  return (
    <div className="settings-panel">
      <section className="settings-block">
        <div className="settings-title"><Wand2 size={15} /> Core model</div>
        <label>
          <span>Writer mode</span>
          <select
            value={form.scene_writer}
            onChange={(event) =>
              onFormChange((current) => ({
                ...current,
                scene_writer: event.target.value as AgentSettingsUpdate["scene_writer"]
              }))
            }
          >
            <option value="rule_based">Rule based local</option>
            <option value="llm">OpenAI-compatible LLM</option>
          </select>
        </label>
        <label>
          <span>Provider label</span>
          <input
            value={form.provider_label}
            onChange={(event) =>
              onFormChange((current) => ({ ...current, provider_label: event.target.value }))
            }
          />
        </label>
        <label>
          <span>Base URL</span>
          <input
            placeholder="https://provider.example/v1"
            value={form.llm_base_url}
            onChange={(event) =>
              onFormChange((current) => ({ ...current, llm_base_url: event.target.value }))
            }
          />
        </label>
        <label>
          <span>Model</span>
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
          <span>Request JSON mode</span>
        </label>
      </section>

      <section className="settings-block">
        <div className="settings-title"><KeyRound size={15} /> API key</div>
        <MetricRow label="Current key" value={apiKeyStatus} />
        <label>
          <span>Replace key</span>
          <input
            autoComplete="off"
            placeholder="Leave blank to keep existing key"
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
          <span>Clear saved key</span>
        </label>
      </section>

      <section className="settings-block">
        <div className="settings-title"><Lock size={15} /> Permission level</div>
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
            <span>Raising permissions is blocked by the API. Edit local config intentionally to re-elevate.</span>
          </div>
        )}
      </section>

      <div className="settings-actions">
        <button onClick={onRefresh} type="button" disabled={busy === "settings"}>
          <RefreshCw size={15} /> Refresh
        </button>
        <button className="primary" onClick={onSave} type="button" disabled={busy === "settings"}>
          <Save size={15} /> Save settings
        </button>
      </div>
    </div>
  );
}

function ContextInspector({ pack }: { pack: ContextPack | null }) {
  if (!pack) {
    return <EmptyState icon={<SplitSquareVertical />} title="No Context Pack" text="Build context to inspect canon, budget, and missing gaps." />;
  }
  return (
    <div className="inspector-body">
      <MetricRow label="Budget" value={`${pack.budget.estimated_tokens}/${pack.budget.target_tokens}`} />
      <MetricRow label="Graph queries" value={String(pack.provenance.graph_query_ids.length)} />
      <ListBlock title="Must include" items={pack.must_include} />
      <ListBlock title="Must not violate" items={pack.must_not_violate} tone="danger" />
      <ListBlock title="Relationships" items={pack.active_relationships} />
      <ListBlock title="Foreshadowing" items={pack.unresolved_foreshadowing} />
      <ListBlock title="Missing context" items={pack.missing_context.map((gap) => `${gap.severity}: ${gap.ref} - ${gap.message}`)} tone="warning" />
      <ListBlock title="Dropped items" items={pack.budget.dropped_items} />
    </div>
  );
}

function ContinuityInspector({ run, report }: { run: WorkflowRun | null; report: ContinuityReport | null }) {
  const blockingCount = report?.issues.filter((issue) => issue.blocking).length ?? 0;
  return (
    <div className="inspector-body">
      <MetricRow label="Current step" value={run?.current_step ?? "none"} />
      <MetricRow label="Review payload" value={run?.review_payload.status ?? "none"} />
      <MetricRow label="Continuity" value={report?.status ?? "not checked"} />
      <MetricRow label="Blocking issues" value={String(blockingCount)} />
      {report ? (
        <>
          <ListBlock title="Summary" items={[report.summary]} />
          <ListBlock title="Checked dimensions" items={report.checked_dimensions} />
          <ListBlock
            title="Issues"
            items={report.issues.map((issue) => `${issue.severity}: ${issue.issue_type} - ${issue.description} Suggestion: ${issue.suggestion}`)}
            tone={blockingCount > 0 ? "danger" : "warning"}
          />
        </>
      ) : (
        <EmptyState icon={<Activity />} title="No QA Report" text="Run the scene workflow to inspect continuity findings." />
      )}
      <ListBlock
        title="Run steps"
        items={(run?.steps ?? fallbackSteps).map((step) => `${step.name}: ${step.status}${step.message ? ` - ${step.message}` : ""}`)}
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
    return <EmptyState icon={<ShieldCheck />} title="No Pending Facts" text="Extracted state changes will pause here for human review." />;
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
            <button onClick={() => onReview(fact.id, "accept")} disabled={busy !== null || !canReview} type="button"><Check size={14} />Accept</button>
            <button onClick={() => onReview(fact.id, "defer")} disabled={busy !== null || !canReview} type="button"><Clock3 size={14} />Defer</button>
            <button onClick={() => onReview(fact.id, "reject")} disabled={busy !== null || !canReview} type="button"><X size={14} />Reject</button>
          </div>
        </div>
      ))}
    </div>
  );
}

function GraphPreview() {
  return (
    <div className="graph-preview">
      <div className="preview-title"><Network size={15} /> Graph / Timeline</div>
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
  return <div className="meta"><span>{label}</span><strong>{value || "missing"}</strong></div>;
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return <div className="metric-row"><span>{label}</span><strong>{value}</strong></div>;
}

function ListBlock({ title, items, tone }: { title: string; items: string[]; tone?: "danger" | "warning" }) {
  return (
    <section className={`list-block ${tone ?? ""}`}>
      <div className="list-title">{title}</div>
      {items.length ? items.map((item) => <p key={item}>{item}</p>) : <p className="muted">None</p>}
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
  read_only: "Read only",
  read_generate: "Read + generate",
  full: "Full permission"
};

const defaultPermissionDescriptions: Record<AgentPermissionLevel, string> = {
  read_only: "Read canon, drafts, context packs, runs, and pending facts only.",
  read_generate: "Read plus generate drafts, checks, extracted candidates, and style samples.",
  full: "All local author operations, including human seed and CandidateFact review decisions."
};

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
          ? `DOCX text extraction is unavailable or failed: ${toErrorMessage(exc)}`
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
    name: "Library",
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
  return normalized || "No readable text found in this document.";
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

const fallbackSteps: WorkflowStep[] = [
  { name: "build_context", status: "pending", artifact_refs: {} },
  { name: "write_draft", status: "pending", artifact_refs: {} },
  { name: "check_continuity", status: "pending", artifact_refs: {} },
  { name: "extract_state", status: "pending", artifact_refs: {} },
  { name: "human_review", status: "pending", artifact_refs: {} }
];
