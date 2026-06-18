import {
  Activity,
  AlertTriangle,
  BookOpen,
  Boxes,
  Check,
  ChevronRight,
  Clock3,
  Database,
  FileText,
  GitBranch,
  Network,
  Play,
  RefreshCw,
  Save,
  Settings,
  ShieldCheck,
  SplitSquareVertical,
  X
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CandidateFact,
  ContextPack,
  ContinuityReport,
  Draft,
  SceneRunResult,
  WorkflowRun,
  WorkflowStep,
  apiGet,
  apiPost
} from "./api";
import { demoProject } from "./sampleData";
import "./styles.css";

const defaultDraft = `Lin Jin climbed the old bell tower after the rain stopped.

The bell rings early. The sound was wrong: too clean, too deliberate, like a signal sent through stone.

Under the frame he found half black wax seal pressed into the dust. He closed his hand around it before Helian Ya could see how sharply his suspicion had changed.`;

type InspectorTab = "context" | "continuity" | "facts";

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
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const endpoint = useMemo(
    () => `/projects/${projectId}/scenes/${sceneId}`,
    [projectId, sceneId]
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

  const refreshFacts = useCallback(async () => {
    const payload = await apiGet<{ facts: CandidateFact[] }>(
      apiBase,
      `/projects/${projectId}/facts/pending`
    );
    setFacts(payload.facts);
  }, [apiBase, projectId]);

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

  const missingCritical = contextPack?.missing_context.some((gap) => gap.severity === "critical");

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
          <StatusDot label="JSON graph" tone="neutral" />
          <button className="icon-button" title="Settings" type="button">
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
              <button onClick={() => runAction("save", saveDraft)} type="button">
                <Save size={16} /> Save
              </button>
              <button onClick={() => runAction("draft", generateDraft)} type="button" disabled={missingCritical}>
                <FileText size={16} /> Draft
              </button>
              <button className="primary" onClick={() => runAction("run", runScene)} type="button">
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
          </div>
          {activeTab === "context" && <ContextInspector pack={contextPack} />}
          {activeTab === "continuity" && <ContinuityInspector run={run} report={continuityReport} />}
          {activeTab === "facts" && (
            <FactsInspector
              facts={facts}
              busy={busy}
              onReview={(factId, action) => runAction(action, () => reviewFact(factId, action))}
            />
          )}
          <GraphPreview />
        </aside>
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
  facts,
  busy,
  onReview
}: {
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
            <button onClick={() => onReview(fact.id, "accept")} disabled={busy !== null} type="button"><Check size={14} />Accept</button>
            <button onClick={() => onReview(fact.id, "defer")} disabled={busy !== null} type="button"><Clock3 size={14} />Defer</button>
            <button onClick={() => onReview(fact.id, "reject")} disabled={busy !== null} type="button"><X size={14} />Reject</button>
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

const fallbackSteps: WorkflowStep[] = [
  { name: "build_context", status: "pending", artifact_refs: {} },
  { name: "write_draft", status: "pending", artifact_refs: {} },
  { name: "check_continuity", status: "pending", artifact_refs: {} },
  { name: "extract_state", status: "pending", artifact_refs: {} },
  { name: "human_review", status: "pending", artifact_refs: {} }
];
