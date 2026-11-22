import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { APP_LOCALE, uiText } from "./localization";
import { clampMainAgentShare, DEFAULT_MAIN_AGENT_SHARE, mainAgentKeyboardShare, readMainAgentShare, writeMainAgentShare } from "./mainAgentLayout";

export function MainAgentDock({ manuscript, children, scopeKey }: { manuscript: ReactNode; children: ReactNode; scopeKey?: string }) {
  const root = useRef<HTMLDivElement>(null);
  const readShare = () => { try { return readMainAgentShare(window.localStorage, scopeKey); } catch { return DEFAULT_MAIN_AGENT_SHARE; } };
  const [layout, setLayout] = useState(() => ({ scopeKey, share: readShare() }));
  const share = layout.scopeKey === scopeKey ? layout.share : readShare();
  useEffect(() => { setLayout({ scopeKey, share: readShare() }); }, [scopeKey]);
  const t = uiText.mainAgentDock;
  function update(value: number) { const next = clampMainAgentShare(value); setLayout({ scopeKey, share: next }); try { writeMainAgentShare(window.localStorage, next, scopeKey); } catch { /* Storage may be unavailable. */ } }
  return <div ref={root} className="main-agent-workbench" style={{ "--main-agent-share": `${share}fr`, "--manuscript-share": `${100 - share}fr` } as CSSProperties}>
    <div className="main-agent-manuscript">{manuscript}</div>
    <div className="main-agent-resize" role="separator" aria-label={t.resize} aria-orientation="horizontal" aria-valuemin={28} aria-valuemax={72} aria-valuenow={share} aria-valuetext={`${t.resizeValue} ${share}%`} tabIndex={0}
      title={t.resizeHelp}
      onDoubleClick={() => update(DEFAULT_MAIN_AGENT_SHARE)}
      onKeyDown={event => { const next = mainAgentKeyboardShare(event.key, share, event.shiftKey); if (next !== null) { event.preventDefault(); update(next); } }}
      onPointerDown={event => { if (event.button !== 0) return; event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault(); }}
      onPointerMove={event => { if (!event.currentTarget.hasPointerCapture(event.pointerId)) return; const bounds = root.current?.getBoundingClientRect(); if (bounds?.height) update(100 * (bounds.bottom - event.clientY) / bounds.height); }}
      onPointerUp={event => { if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); }}
    ><span /></div>
    <section className="main-agent-dock" aria-label={t.title}>{children}</section>
  </div>;
}

export function MainAgentWelcome({ busy, canCreate, modelReady, onCreate, onOpenSettings }: { busy: boolean; canCreate: boolean; modelReady: boolean; onCreate: (idea: string, language: "zh-CN" | "en-US") => Promise<void>; onOpenSettings: () => void }) {
  const zh = APP_LOCALE === "zh-CN";
  const t = uiText.mainAgentDock;
  const [idea, setIdea] = useState("");
  const [language, setLanguage] = useState<"zh-CN" | "en-US">(zh ? "zh-CN" : "en-US");
  return <section className="main-agent-welcome"><h2>{t.welcomeTitle}</h2>
    <p>{t.welcomeHelp}</p>
    <label>{t.idea}<textarea placeholder={t.ideaExample} rows={3} maxLength={12000} value={idea} onChange={event => setIdea(event.target.value)} disabled={busy} /></label>
    <div className="main-agent-welcome-actions"><label>{t.language}<select value={language} onChange={event => setLanguage(event.target.value as "zh-CN" | "en-US")} disabled={busy}><option value="zh-CN">中文</option><option value="en-US">English</option></select></label>
    <button type="button" className="primary" disabled={busy || !canCreate || !idea.trim()} onClick={() => { void onCreate(idea.trim(), language); }}>{modelReady ? t.createAndChat : t.createLocal}</button></div>
    {modelReady && <small className="title-usage">{uiText.authorDesk.titleUse}</small>}
    {!modelReady && <p>{t.setupHelp}<button type="button" onClick={onOpenSettings}>{t.settings}</button></p>}
  </section>;
}
