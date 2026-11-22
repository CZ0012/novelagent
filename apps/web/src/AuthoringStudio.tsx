import { createPortal } from "react-dom";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { ApiRequestError, apiGet, apiPost, type WriterChoice, type Draft, type ProposalArtifact, type SceneOutline, type SourceDocumentSummary } from "./api";
import { ChatGPTUsage, CHATGPT_USAGE_URL } from "./ChatGPTPlanSettings";
import { modelProviderFailureKey, storedPlanFailureKey } from "./modelProviderErrors";
import { uiText } from "./localization";
import { AuthoringProposalPreview, AuthoringDesign, AuthoringEvidenceList, AuthoringProposalActions, AuthoringProposalOrigin } from "./AuthoringDesign";
import { authoringCanAdopt, updateAuthoringSources, applyAuthoringStructure, previewAuthoringStructure, authoringReconciliationCard, authoringReconciliationCards, reconcileAuthoringDraft, authoringPath, getAuthoringSession, listAuthoringSessions, postAuthoringSession, authoringSha256, authoringValidPassage, type AuthoringPassageSelection, authoringToolNavigation, authoringCanPinDraft, type AuthoringNavigation, type AuthoringPreview, type AuthoringSession, type AuthoringStructurePreview } from "./authoring";
import { VisibilityActualPreview } from "./WriterVisibilityPanel";
import { AuthoringStructure } from "./AuthoringStructure";
import { AuthoringHistory, AuthoringHistoricalProposal } from "./AuthoringHistory";
import { AuthoringSources } from "./AuthoringSources";
import { exactMessage, type SessionNavigation } from "./projectContext";
import "./AuthoringStudio.css";

// Ephemeral per-window composers survive project navigation without writing unpublished
// messages to localStorage or adding them to the model's conversation.
const conversationDrafts = new Map<string, Map<string,string>>();
function draftsFor(base:string, project:string) {
  const key=JSON.stringify([base,project]);
  const drafts=conversationDrafts.get(key) ?? new Map<string,string>();
  conversationDrafts.set(key,drafts);
  return drafts;
}

export type { AuthoringNavigation } from "./authoring";

export function AuthoringStudio({ layout = "full", panelHost, activePanel, currentSceneId, currentChapterId, bootstrapSessionId, sessionNavigation, onActiveSessionChange, initialIdea, draftSelection, onOpenSettings, onNavigate, apiBase, projectId, projectLanguage, active, canGenerate, modelReady, modelLabel, usingChatGPTPlan = false, sources, proposals, scenes, names = {}, draft, draftDirty, onHandoff, onWriterContext, canReview = false, onStructureApplied }: {
  sessionNavigation?: SessionNavigation | null; onActiveSessionChange?: (id: string | null, version: number) => void;
  panelHost?: HTMLElement | null; activePanel?: "conversation" | "design" | "checks"; draftSelection?: AuthoringPassageSelection | null; layout?: "full" | "dock"; currentSceneId?: string; currentChapterId?: string; bootstrapSessionId?: string; initialIdea?: string; onOpenSettings?: () => void; onNavigate?: (target: AuthoringNavigation) => void;
  apiBase: string; projectId: string; projectLanguage: string; active: boolean; canGenerate: boolean; modelReady: boolean; modelLabel: string; usingChatGPTPlan?: boolean;
  sources: SourceDocumentSummary[]; proposals: ProposalArtifact[]; scenes: SceneOutline[]; names?: Record<string, string>;
  draft: Draft | null; draftDirty: boolean; onWriterContext?: (session: { sessionId: string; choice: WriterChoice | null } | null) => void; onHandoff: (sceneId: string, savedDraft: Draft | null, choice?: WriterChoice | null) => void; canReview?: boolean; onStructureApplied?: (sceneId: string) => Promise<void>;
}) {
  const t = uiText.authoring;
  const [panel, setPanel] = useState<"design" | "checks" | "history">("design");
  useEffect(() => { if (activePanel === "design" || activePanel === "checks") setPanel(value => activePanel === "design" && value === "history" ? value : activePanel); }, [activePanel]);
  const actionLock = useRef(false);
  const composerRef = useRef<HTMLTextAreaElement | null>(null);
  const messageScrollRef = useRef<HTMLDivElement | null>(null);
  const [passage, setPassage] = useState<{ sessionId: string; draftId: string; draftVersion: number; selection: AuthoringPassageSelection } | null>(null);
  const [collaborationMode, setCollaborationMode] = useState<"collaborate" | "discuss" | "review">("collaborate");
  const [sessions, setSessions] = useState<Array<Pick<AuthoringSession, "id" | "project_id" | "title" | "version" | "updated_at">>>([]);
  const [session, setSession] = useState<AuthoringSession | null>(null), [creating, setCreating] = useState(false);
  useEffect(() => { const element = messageScrollRef.current; if (element) element.scrollTop = element.scrollHeight; }, [session?.id, session?.messages.length]);
  const [idea, setIdea] = useState(""), [message, setMessage] = useState("");
  const [quotedMessage, setQuotedMessage] = useState<AuthoringSession["messages"][number] | null>(null);
  const switchSequence = useRef(0);
  const unsent = useRef(draftsFor(apiBase,projectId));
  const activeSessionHandler = useRef(onActiveSessionChange);
  activeSessionHandler.current = onActiveSessionChange;


  const [sourceIds, setSourceIds] = useState<string[]>([]), [outlineIds, setOutlineIds] = useState<string[]>([]);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (loaded) activeSessionHandler.current?.(creating ? null : session?.id ?? null, session?.version ?? 0);
  }, [loaded, creating, session?.id, session?.version]);
  const [cardId, setCardId] = useState(""), [targetSceneId, setTargetSceneId] = useState(""), [preview, setPreview] = useState<AuthoringPreview | null>(null), [policyVersion, setPolicyVersion] = useState(0);
  const [structure, setStructure] = useState<AuthoringStructurePreview | null>(null), [writerDraft, setWriterDraft] = useState<Draft | null>(null);
  const [reconcileSelection, setReconcileSelection] = useState<{ sessionId: string; draftId: string; cardId: string } | null>(null);
  const generation = useRef(0), sessionRef = useRef<AuthoringSession | null>(null), locked = busy || session?.turn_status === "running" || !canGenerate, paidLocked = locked || !modelReady;
  const writerContextHandler = useRef(onWriterContext); writerContextHandler.current = onWriterContext;
  useEffect(() => { writerContextHandler.current?.(!creating && session ? { sessionId: session.id, choice: session.writer_choice ?? null } : null); }, [apiBase, projectId, creating, session?.id, session?.writer_choice?.fingerprint]);
  useEffect(() => () => { writerContextHandler.current?.(null); }, [apiBase, projectId]);
  const planFailure = storedPlanFailureKey(session?.turn_error_category);
  const planActionError = Boolean(error && (["modelPlanUsageLimit", "modelPlanPermission", "modelPlanEligibility", "modelPlanUnavailable"] as const).some(key => uiText.errors[key] === error));
  const outlines = proposals.filter(item => item.artifact_type === "outline_draft" && item.project_id === projectId);
  async function action(work: () => Promise<void>) { if (actionLock.current) return; actionLock.current = true; const current = generation.current; setBusy(true); setError(""); try { await work(); } catch (exc) { if (generation.current === current) { setError(modelProviderFailureKey(exc) ? uiText.errors[modelProviderFailureKey(exc)!] : exc instanceof ApiRequestError && exc.category === "authoring_scene_plan_review_required" ? t.planReviewRequired : exc instanceof ApiRequestError && exc.category === "authoring_draft_pin_in_use" ? t.dockCitedDraft : t.actionFailed); const saved = sessionRef.current; if (saved) try { const latest = await getAuthoringSession(apiBase, projectId, saved.id); if (generation.current === current) accept(latest); } catch { /* Preserve the visible saved session when refresh fails. */ } } } finally { actionLock.current = false; if (generation.current === current) setBusy(false); } }
  async function load(id?: string, messageId?: string) {
    const current = generation.current, sequence = ++switchSequence.current;
    const values = await listAuthoringSessions(apiBase, projectId);
    let remembered: string | null = null;
    try { remembered = localStorage.getItem(`storygraph.authoring-session.v1:${apiBase}:${projectId}`); } catch { /* Optional preference. */ }
    const fallback = values[0]?.id;
    const selected = id ?? sessionRef.current?.id ?? bootstrapSessionId ?? remembered ?? fallback;
    let value: AuthoringSession | null = null;
    if (selected) {
      try { value = await getAuthoringSession(apiBase, projectId, selected); }
      catch (err) {
        if (id || !(err instanceof ApiRequestError) || (err.status !== 404 && err.status !== 409)) throw err;
        value = fallback && fallback !== selected ? await getAuthoringSession(apiBase, projectId, fallback) : null;
      }
    }
    const source = value && messageId ? await exactMessage(apiBase, projectId, value.id, messageId) : null;
    if (current !== generation.current || sequence !== switchSequence.current) return;
    if (sessionRef.current?.id !== value?.id) {
      setMessage(value ? unsent.current.get(value.id) ?? "" : "");
      setCardId(""); setTargetSceneId(""); setWriterDraft(null); setReconcileSelection(null);
    }
    if (!loaded && !value && initialIdea && !unsent.current.has("")) setIdea(initialIdea);
    setSessions(values); setPassage(null); setSession(value); sessionRef.current = value;
    if (value) remember(value.id);
    setLoaded(true); setCreating(!value); setPreview(null); setStructure(null);
    setQuotedMessage(source?.message ?? null);
  }
  useEffect(() => { generation.current += 1; sessionRef.current = null; setSession(null); setPassage(null); setSessions([]); setLoaded(false); setError(""); setBusy(false); setCreating(false); setQuotedMessage(null); unsent.current=draftsFor(apiBase,projectId); setIdea(unsent.current.get("") ?? ""); setMessage(""); setSourceIds([]); setOutlineIds([]); setPreview(null); setStructure(null); return () => { generation.current += 1; }; }, [apiBase, projectId]);
  useEffect(() => { if (!active || !projectId || loaded) return; setBusy(true); const current = generation.current; load().catch(() => { if (current === generation.current) setError(t.loadFailed); }).finally(() => { if (current === generation.current) setBusy(false); }); }, [active, apiBase, projectId, loaded]);
  const handledNavigation = useRef<number | null>(null);
  useEffect(() => {
    if (!loaded || !sessionNavigation || handledNavigation.current === sessionNavigation.nonce || busy || actionLock.current) return;
    handledNavigation.current = sessionNavigation.nonce;
    if (sessionRef.current) unsent.current.set(sessionRef.current.id, message);
    if (sessionNavigation.sessionId) {
      void action(() => load(sessionNavigation.sessionId, sessionNavigation.messageId));
    } else {
      setCreating(true); setPassage(null); setQuotedMessage(null); setError("");
      setCardId(""); setTargetSceneId(""); setWriterDraft(null); setStructure(null); setPreview(null);
    }
  }, [sessionNavigation, loaded, busy]);
  useEffect(() => {
    const renamed = (e: Event) => {
      const info = (e as CustomEvent).detail;
      if (info?.apiBase !== apiBase || info.projectId !== projectId) return;
      setSessions(rows=>rows.map(row=>row.id === info.sessionId ? {...row,title:info.title} : row));
      setSession(row=>row?.id === info.sessionId && row ? {...row,title:info.title} : row);
    };
    window.addEventListener("storygraph-conversation-title", renamed);
    return ()=>window.removeEventListener("storygraph-conversation-title",renamed);
  }, [apiBase,projectId]);
  function navigationLabel(target: AuthoringNavigation["target"]) { return ({ conversation: t.conversation, design: t.design, checks: t.dockChecks, manuscript: t.dockManuscript, sources: t.sources, graph: t.dockGraph, settings: t.dockSettings, planning: t.dockPlanning, proposals: t.dockProposals, writer: t.dockWriter, continuity: uiText.tabs.continuity })[target]; }
  function navigate(target: AuthoringNavigation) { if (target.target === "writer") target = { ...target, writer_choice: session?.writer_choice }; if (target.target === "design") { setPanel("design"); onNavigate?.(target); } else if (target.target === "checks") { setPanel("checks"); onNavigate?.(target); } else if (target.target === "settings" && onOpenSettings) onOpenSettings(); else if (target.target === "conversation") composerRef.current?.focus(); else onNavigate?.(target); }


  function remember(id: string) { try { localStorage.setItem(`storygraph.authoring-session.v1:${apiBase}:${projectId}`, id); } catch { /* Optional local preference. */ } }
  function accept(value: AuthoringSession) { window.dispatchEvent(new CustomEvent("storygraph-notebook-changed",{detail:{apiBase,projectId}})); if (sessionRef.current?.id !== value.id) setPassage(null); remember(value.id); sessionRef.current = value; setSession(value); setPreview(null); setStructure(null); setSessions(items => [{ id: value.id, project_id: value.project_id, title: value.title, version: value.version, updated_at: value.updated_at }, ...items.filter(item => item.id !== value.id)]); }
  async function create() { const openingIdea = idea.trim(); const current = generation.current; const value = await postAuthoringSession(apiBase, projectId, undefined, "", { title: Array.from(openingIdea).slice(0, 60).join(""), idea: openingIdea, auto_title: true, source_document_ids: sourceIds, outline_proposal_ids: outlineIds, draft_ids: [] }); if (current === generation.current) { accept(value); setCreating(false); unsent.current.delete(""); setIdea(""); setMessage(""); const developed = await postAuthoringSession(apiBase, projectId, value.id, "/turn", { expected_version: value.version, message: openingIdea, max_steps: 6, collaboration_mode: collaborationMode }); if (current === generation.current) accept(developed); } }
  const validPassage = !!passage && passage.sessionId === session?.id && passage.draftVersion === draft?.version && authoringValidPassage(projectId, currentSceneId, draft, draftDirty, passage.selection);
  async function turn() {
    if (!session || (passage && !validPassage)) return;
    const current = generation.current;
    const selected_passage = validPassage && passage && draft ? {
      draft_id: draft.id, version: draft.version, text_sha256: await authoringSha256(draft.text),
      start: passage.selection.start, end: passage.selection.end,
    } : undefined;
    if (current !== generation.current) return;
    // A selected passage authorizes this dispatch only, including uncertain outcomes.
    if (selected_passage) setPassage(null);
    const value = await postAuthoringSession(apiBase, projectId, session.id, "/turn", {
      expected_version: session.version, message: message.trim(), max_steps: 6,
      collaboration_mode: collaborationMode, selected_passage,
      navigation_context: { scene_id: currentSceneId || null, chapter_id: currentChapterId || null },
    });
    if (current === generation.current) { accept(value); unsent.current.delete(value.id); setMessage(""); }
  }
  async function decide(proposalId: string, decision: "adopt" | "reject") { if (!session || (decision === "adopt" && !session.proposals.some(proposal => proposal.id === proposalId && authoringCanAdopt(proposal)))) return; const current = generation.current, value = await postAuthoringSession(apiBase, projectId, session.id, `/proposals/${encodeURIComponent(proposalId)}/decision`, { expected_version: session.version, decision }); if (current === generation.current) accept(value); }
  const card = session?.workspace.scene_cards.find(item => item.id === cardId), targetScene = scenes.find(item => item.id === (targetSceneId || card?.scene_id));
  async function showPreview() { if (!session || !card || !targetScene) return; const current = generation.current;
    const value = await apiPost<AuthoringPreview>(apiBase, authoringPath(projectId, session.id) + `/cards/${encodeURIComponent(card.id)}/preview`, { expected_version: session.version, target_scene_id: targetScene.id });
    const target = await apiGet<{ draft: Draft | null }>(apiBase, `/projects/${encodeURIComponent(projectId)}/scenes/${encodeURIComponent(targetScene.id)}/draft`);
    if (current === generation.current) { setPreview(value); setPolicyVersion(value.expected_policy_version); setWriterDraft(target.draft); }
  }
  async function compile() { if (!session || !card || !targetScene || !preview) return; const current = generation.current;
    const value = await postAuthoringSession(apiBase, projectId, session.id, `/cards/${encodeURIComponent(card.id)}/compile`, { expected_version: session.version, target_scene_id: targetScene.id, expected_policy_version: policyVersion, expected_source_context_sha256: preview.source_context_sha256 });
    if (current === generation.current) { accept(value); window.dispatchEvent(new Event("storygraph-writer-visibility-changed")); onHandoff(targetScene.id, writerDraft, value.writer_choice); }
  }
  async function showStructure() { if (!session || !card) return; const current = generation.current; const value = await previewAuthoringStructure(apiBase, projectId, session, card.id); if (current === generation.current) { setStructure(value); setPreview(null); } }
  async function createStructure() { if (!session || !card || !structure || structure.gaps.length || !canReview || draftDirty) return; const current = generation.current; const value = await applyAuthoringStructure(apiBase, projectId, session, card.id, structure, structure.operation === "update" ? t.structureUpdateRationale : t.structureRationale); if (current !== generation.current) return; accept(value.session); setTargetSceneId(value.scene_id); await onStructureApplied?.(value.scene_id); }
  const reconcileCards = session ? authoringReconciliationCards(session, draft) : [];
  const selectedReconcileId = reconcileSelection?.sessionId === session?.id && reconcileSelection?.draftId === draft?.id ? reconcileSelection?.cardId : undefined;
  const reconcileCard = session ? authoringReconciliationCard(session, draft, selectedReconcileId) : null;
  async function reconcile() { if (!session || !draft || draftDirty || !reconcileCard) return; const current = generation.current;
    const value = await reconcileAuthoringDraft(apiBase, session, draft, reconcileCard.id);
    if (current === generation.current) accept(value);
  }
  function toggle(values: string[], id: string) { return values.includes(id) ? values.filter(value => value !== id) : [...values, id]; }
  const pendingCount = session?.proposals.filter(item => item.status === "pending").length ?? 0;
  return <section className={`authoring-studio ${layout === "dock" ? "authoring-docked" : ""}`} data-panel={panel} aria-label={t.title}><header><h2>{layout === "dock" ? uiText.mainAgentDock.title : t.title}</h2><p>{t.help}</p>{layout !== "dock" && <small>{uiText.modelRouting.effective}: {modelLabel}</small>}<ChatGPTUsage active={usingChatGPTPlan} />{layout === "dock" && pendingCount > 0 && <button type="button" onClick={()=>navigate({target:"checks"})}>{t.proposal} · {pendingCount}</button>}</header><p className="authoring-boundary">{t.boundary}</p>{session?.writer_choice && <p role="status">Writer · {session.writer_choice.profile_name} · {session.writer_choice.model} · {session.writer_choice.auth_mode === "chatgpt_plan" ? uiText.chatgpt.using : "API Key"}<br />{session.writer_choice.reason}<small>{uiText.chatgpt.writerOverrideHelp}</small></p>}
    {!projectId ? <p role="status">{t.needsProject}</p> : <>
    {!canGenerate && <p role="status">{t.readonly}</p>}{!modelReady && <p role="status">{t.needsModel}{onOpenSettings && <button type="button" onClick={onOpenSettings}>{t.dockSettings}</button>}</p>}{planFailure || planActionError ? <p role="alert">{planFailure ? uiText.errors[planFailure] : error} <a className="primary" href={CHATGPT_USAGE_URL} target="_blank" rel="noreferrer">{uiText.chatgpt.usage}</a>{onOpenSettings && <button type="button" onClick={onOpenSettings}>{t.dockSettings}</button>}</p> : error && <p role="alert">{error}{!loaded && <button type="button" disabled={busy} onClick={()=>{void action(()=>load());}}>{uiText.authorDesk.retry}</button>}</p>}
    {!onActiveSessionChange && <details className="authoring-session-controls" open={layout === "full"}><summary>{t.session} · {session?.title || t.newSession}</summary><div className="authoring-toolbar"><label>{t.session}<select value={creating ? "" : session?.id ?? ""} disabled={busy} onChange={event => { const id = event.target.value; if (id) { setCreating(false); void action(() => load(id)); } }}><option value="">{t.newSession}</option>{sessions.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><button type="button" disabled={busy} onClick={() => { setCreating(true); setPreview(null); }}>{t.newSession}</button><button type="button" disabled={busy} onClick={() => { void action(() => load()); }}>{t.refresh}</button></div></details>}
    {quotedMessage && <aside className="source-message-focus" aria-live="polite"><strong>{uiText.authorDesk.sourceMessage}</strong><p>{quotedMessage.content}</p><button type="button" onClick={()=>setQuotedMessage(null)}>{uiText.authorDesk.close}</button></aside>}
    {creating ? <section className="authoring-conversation first-composer"><div className="first-composer-bar"><label><span className="visually-hidden">{t.idea}</span><textarea rows={3} maxLength={12000} value={idea} disabled={locked} placeholder={uiText.authorDesk.firstMessage} onChange={event => { unsent.current.set("",event.target.value); setIdea(event.target.value); }} /></label><button type="button" className="primary" disabled={paidLocked || !idea.trim()} onClick={() => { void action(create); }}>{t.send}</button></div><details><summary>{t.dockContext}</summary><p>{t.sourceHelp}</p><div className="authoring-sources">{!sources.length && !outlines.length && <p>{t.noSources}</p>}{sources.map(source => { const available = source.extraction_status === "ready" && source.language === projectLanguage; return <label key={source.id}><input type="checkbox" disabled={locked || !available} checked={sourceIds.includes(source.id)} onChange={() => setSourceIds(values => toggle(values, source.id))} /><span>{source.title} · {source.language}{!available && ` · ${uiText.authoring.sourceUnavailable}`}</span></label>; })}{outlines.map(outline => <label key={outline.id}><input type="checkbox" disabled={locked || outline.content_language !== projectLanguage} checked={outlineIds.includes(outline.id)} onChange={() => setOutlineIds(values => toggle(values, outline.id))} /><span>{t.outline}: {outline.title} · v{outline.version}</span></label>)}</div></details><small className="title-usage">{uiText.authorDesk.titleUse}</small></section> : session && <>
    {layout !== "dock" && <nav className="authoring-view-tabs" aria-label={t.design}>{(["design", "checks", "history"] as const).map(value => <button key={value} type="button" aria-pressed={panel === value} onClick={() => { setPanel(value); onNavigate?.({ target: value === "checks" ? "checks" : "design" }); }}>{value === "design" ? t.design : value === "history" ? t.history : t.dockChecks}</button>)}</nav>}
    <AuthoringPanelPortal host={layout === "dock" ? panelHost : null}><div className={`authoring-upper ${layout === "dock" ? "authoring-upper-docked" : ""}`} data-panel={panel}>
    <AuthoringSources key={`sources:${session.id}`} session={session} sources={sources} proposals={proposals} busy={busy} canEdit={canGenerate && session.turn_status !== "running"} onSave={async (version, sourceIds, outlineIds) => { let saved = false; await action(async () => { const current = generation.current; const value = await updateAuthoringSources(apiBase, projectId, session.id, version, sourceIds, outlineIds); if (current === generation.current) { accept(value); saved = true; } }); return saved; }} />
    <AuthoringHistory key={`history:${session.id}`} apiBase={apiBase} projectId={projectId} session={session} names={names} />
    {session.turn_status !== "idle" && <p role="status">{session.turn_status === "running" ? t.running : session.turn_status === "unknown" ? t.unknown : t.failed}</p>}
    {session.turn_status === "running" && !busy && <details><summary>{t.recover}</summary><p>{t.recoverHelp}</p><button type="button" disabled={!canGenerate || busy} onClick={() => { void action(async () => { const current = generation.current; const value = await postAuthoringSession(apiBase, projectId, session.id, "/recover", { expected_version: session.version }); if (current === generation.current) accept(value); }); }}>{t.recover}</button></details>}
    <div className="authoring-columns">
    <section className="authoring-current-design"><h3>{t.design}</h3><div className="authoring-design-scroll" role="region" aria-label={t.design} tabIndex={0}><AuthoringDesign workspace={session.workspace} names={names} /></div></section></div>
    {session.proposals.filter(item => item.status === "pending").map(proposal => <section className="authoring-proposal" key={proposal.id}><h3>{t.proposal}</h3><p>{proposal.summary}</p><AuthoringProposalOrigin proposal={proposal} />{proposal.stale !== false && <p role="status">{proposal.stale ? t.staleProposal : t.unverifiedProposal}</p>}<p>{t.changeHelp}</p><p>{t.affected}: {proposal.affected_scene_ids.map(id => names[id] ?? scenes.find(scene => scene.id === id)?.title ?? id).join("、") || "—"}</p><AuthoringEvidenceList evidence={proposal.evidence} />{authoringCanAdopt(proposal) ? <><AuthoringProposalPreview before={session.workspace} patch={proposal.patch} names={names} /><details><summary>{t.before}</summary><AuthoringDesign workspace={session.workspace} names={names} /></details></> : <AuthoringHistoricalProposal proposal={proposal} names={names} />}<AuthoringProposalActions proposal={proposal} locked={locked} onDecide={decision => { void action(() => decide(proposal.id, decision)); }} /></section>)}
    {session.workspace.scene_cards.length > 0 && <section className="authoring-card"><h3>{t.handoff}</h3><p>{t.writerInstructionHelp}</p><div className="authoring-toolbar"><label>{t.sceneCards}<select value={cardId} disabled={busy} onChange={event => { setCardId(event.target.value); setTargetSceneId(""); setPreview(null); setStructure(null); }}><option value="">{uiText.common.none}</option>{session.workspace.scene_cards.map(item => <option key={item.id} value={item.id}>{item.title} · {t[item.status]}</option>)}</select></label><label>{t.targetScene}<select value={targetScene?.id ?? ""} disabled={busy} onChange={event => { setTargetSceneId(event.target.value); setPreview(null); setStructure(null); }}><option value="">{uiText.common.none}</option>{scenes.map(scene => <option key={scene.id} value={scene.id}>{scene.title}</option>)}</select></label></div>{card && !targetScene && <p>{t.noScene}</p>}{card?.status === "approved" && <div className="authoring-actions"><button type="button" disabled={busy} onClick={() => { void action(showStructure); }}>{card.scene_id ? t.structureUpdatePreview : t.structurePreview}</button></div>}{structure && <><p>{uiText.writerVisibility.cast}: {card?.writer_policy.characters.map(actor => actor.public_name).join("、")}</p><AuthoringStructure preview={structure} names={names} />{!canReview && <p role="status">{t.structurePermission}</p>}<button type="button" className="primary" disabled={locked || !canReview || structure.gaps.length > 0 || draftDirty || (structure.operation === "update" && !structure.changes?.length)} onClick={() => { void action(createStructure); }}>{structure.operation === "update" ? t.structureUpdateApply : t.structureApply}</button></>}<div className="authoring-actions"><button type="button" disabled={busy || !card || card.status !== "approved" || !targetScene} onClick={() => { void action(showPreview); }}>{t.writerPreview}</button>{preview && <button type="button" className="primary" disabled={locked || draftDirty} onClick={() => { void action(compile); }}>{writerDraft?.text.trim() ? t.handoffRevision : t.handoff}</button>}</div>{preview && writerDraft?.text.trim() && <p>{t.existingDraft} · {writerDraft.id} v{writerDraft.version}</p>}{preview && <VisibilityActualPreview preview={{ ...preview, mode: preview.mode }} />}</section>}
    <section className="authoring-card"><h3>{t.reconcile}</h3><p>{t.reconcileHelp}</p>{draft && draft.project_id === projectId ? <p>{scenes.find(scene => scene.id === draft.scene_id)?.title ?? draft.scene_id} · v{draft.version}{draftDirty ? ` · ${uiText.writerVisibility.unsaved}` : ""}</p> : <p>{t.noDraft}</p>}<label>{t.reconcileCard}<select value={reconcileCard?.id ?? ""} disabled={busy || !draft || !reconcileCards.length} onChange={event => setReconcileSelection({ sessionId: session.id, draftId: draft?.id ?? "", cardId: event.target.value })}><option value="">{t.reconcileSelect}</option>{reconcileCards.map(item => <option key={item.id} value={item.id}>{item.title} · v{item.version}</option>)}</select></label>{draft && !reconcileCards.length && <p role="status">{t.reconcileUnbound}</p>}<button type="button" disabled={paidLocked || !draft || !reconcileCard || draft.project_id !== projectId || draftDirty || !draft.text.trim()} onClick={() => { void action(reconcile); }}>{t.reconcile}</button></section>
    {session.proposals.some(item => item.status !== "pending") && <details><summary>{t.history}</summary>{session.proposals.filter(item => item.status !== "pending").map(item => <p key={item.id}>{item.summary} · {item.status === "adopted" ? t.decided : t.reject}</p>)}</details>}
    </div></AuthoringPanelPortal>
    <section className="authoring-conversation"><h3>{t.conversation}</h3><small>{t.sourcesLockedNew} · {session.source_pins.length}</small><p>{t.historyWindow}: {session.messages.length} / {session.history_counts?.messages ?? session.messages.length}</p><div ref={messageScrollRef} className="authoring-message-scroll" role="region" aria-label={t.historyMessages} tabIndex={0}>{session.messages.filter(item => item.role !== "tool").map(item => <article className={`authoring-message ${item.role}`} key={item.id}><strong>{item.role === "author" ? t.author : t.assistant}</strong><p>{item.content}</p></article>)}{session.messages.some(item => item.role === "tool") && <details><summary>{t.tools}</summary>{session.messages.filter(item => item.role === "tool").map(item => <article key={item.id}><strong>{t.toolsLabels[item.tool_name as keyof typeof t.toolsLabels] ?? t.tools}</strong><pre>{item.content}</pre></article>)}</details>}{session.messages.filter(item => item.role === "tool" && item.tool_name === "open_workflow").map(item => { const target = authoringToolNavigation(item.content); return target ? <button key={item.id} type="button" onClick={() => navigate(target)}>{t.dockOpen}{navigationLabel(target.target)}{target.scene_id ? ` · ${names[target.scene_id] ?? target.scene_id}` : ""}</button> : null; })}</div><details className="authoring-input-context"><summary>{t.dockContext}</summary><small>{uiText.modelRouting.effective} · {modelLabel}</small><button type="button" onClick={()=>{setPanel("history");onNavigate?.({target:"design"});}}>{t.journal}</button><p className="authoring-boundary">{t.turnBudget}</p><p className="authoring-location">{t.dockFocus}{names[currentSceneId ?? ""] ?? currentSceneId ?? names[currentChapterId ?? ""] ?? currentChapterId ?? uiText.mainAgentDock.projectTools} · {t.dockFocusHelp}</p><label>{t.dockMode}<select value={collaborationMode} disabled={locked} onChange={event => setCollaborationMode(event.target.value as typeof collaborationMode)}><option value="collaborate">{t.dockCollaborate}</option><option value="discuss">{t.dockDiscuss}</option><option value="review">{t.dockReview}</option></select></label><div className="authoring-draft-input"><button type="button" disabled={locked || !authoringValidPassage(projectId, currentSceneId, draft, draftDirty, draftSelection)} onClick={() => { if (session && draft && draftSelection && authoringValidPassage(projectId, currentSceneId, draft, draftDirty, draftSelection)) setPassage({ sessionId: session.id, draftId: draft.id, draftVersion: draft.version, selection: { ...draftSelection } }); }}>{t.dockIncludePassage}</button>{passage && <><p role="status">{validPassage ? t.dockPassageReady : t.dockPassageStale} · {passage.selection.start}–{passage.selection.end}</p><button type="button" disabled={locked} onClick={() => setPassage(null)}>{t.dockClearPassage}</button></>}<p>{validPassage ? t.dockPassageOnly : t.dockInputs}{validPassage ? "" : (session.draft_pins.map(pin => `${names[pin.scene_id] ?? pin.scene_id} · ${pin.draft_id} v${pin.version}`).join("、") || uiText.common.none)}</p><button type="button" disabled={locked || !authoringCanPinDraft(projectId, currentSceneId, draft, draftDirty)} onClick={() => { if (!draft || !authoringCanPinDraft(projectId, currentSceneId, draft, draftDirty)) return; const exact = draft; void action(async () => { const current = generation.current; const value = await postAuthoringSession(apiBase, projectId, session.id, "/draft-pins", { expected_version: session.version, draft_ids: [...new Set([...session.draft_pins.map(pin => pin.draft_id), exact.id])] }); if (current === generation.current) { accept(value); setPassage(null); } }); }}>{t.dockIncludeDraft}</button>{session.draft_pins.length > 0 && <button type="button" disabled={locked} onClick={() => { void action(async () => { const current = generation.current; const value = await postAuthoringSession(apiBase, projectId, session.id, "/draft-pins", { expected_version: session.version, draft_ids: [] }); if (current === generation.current) accept(value); }); }}>{t.dockClearDrafts}</button>}{draftDirty && <p role="status">{t.dockUnsaved}</p>}</div></details>{(draftDirty || (passage && !validPassage)) && <p className="authoring-input-blocker" role="status">{draftDirty ? t.dockUnsaved : t.dockPassageStale}</p>}<div className="authoring-compose"><label>{t.idea}<textarea ref={composerRef} rows={4} maxLength={12000} value={message} disabled={locked} placeholder={t.placeholder} onChange={event => { unsent.current.set(session.id,event.target.value); setMessage(event.target.value); }} /></label><button type="button" className="primary" disabled={paidLocked || (!!passage && !validPassage) || !message.trim()} onClick={() => { void action(turn); }}>{t.send}</button></div></section>
    </>}
    </>}
  </section>;
}

function AuthoringPanelPortal({ host, children }: { host?: HTMLElement | null; children: ReactNode }) { return host ? createPortal(children, host) : children; }
