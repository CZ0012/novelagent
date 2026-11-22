import { BookOpen, ChevronDown, FileText, FolderOpen, Library, Menu, MessageSquare, Network, NotebookPen, ShieldCheck, Sparkles, SplitSquareVertical } from "lucide-react";
import type { ReactNode } from "react";
import { uiText } from "./localization";

export type AuthorWorkArea = "write" | "authoring" | "checks" | "notebook" | "sources" | "proposals" | "planning" | "graph" | "workflow";

/** Presentation-only chrome. All navigation stays owned by App's protected state. */
export function WorkbenchHeader({ title, onToggleNavigation, navigationOpen, commands, actions, diagnostics, statusTone }: {
  title: string; onToggleNavigation: () => void; navigationOpen: boolean; commands: ReactNode; actions: ReactNode; diagnostics: ReactNode; statusTone: string;
}) {
  return <header className="author-header">
    <div className="author-header-identity"><button type="button" className="icon-button navigation-toggle" aria-label={uiText.shellDesk.navigation} aria-expanded={navigationOpen} onClick={onToggleNavigation}><Menu size={19} /></button>
      <div className="author-brand-mark"><BookOpen size={21} strokeWidth={1.5} /></div><div className="author-brand"><span>STORYGRAPH <span className="author-brand-agent">AGENT</span></span><strong title={title}>{title}</strong></div>
    </div>
    <div className="author-header-actions">{commands}{actions}<details className="author-system-status"><summary aria-label={uiText.shellDesk.systemStatus}><span className="connection-indicator" data-tone={statusTone} /><ChevronDown size={12} /></summary><div>{diagnostics}</div></details></div>
  </header>;
}

export function AuthorWorkspaceTabs({ active, onNavigate, tools }: { active: AuthorWorkArea; onNavigate: (area: AuthorWorkArea) => void; tools: ReactNode }) {
  const tabs = [
    { id: "write" as const, label: uiText.shellDesk.manuscript, icon: FileText },
    { id: "authoring" as const, label: uiText.shellDesk.design, icon: Sparkles },
    { id: "checks" as const, label: uiText.shellDesk.checks, icon: ShieldCheck }
  ];
  return <nav className="author-workspace-tabs" aria-label={uiText.workspace.mainWorkspaceAria}>{tabs.map(({ id, label, icon: Icon }) => <button key={id} type="button" className={active === id ? "active" : ""} aria-current={active === id ? "page" : undefined} onClick={() => onNavigate(id)}><Icon size={15} />{label}</button>)}<div className="author-workspace-tools">{tools}</div></nav>;
}

export function AuthorMaterialNavigation({ active, onNavigate }: { active: AuthorWorkArea; onNavigate: (area: AuthorWorkArea) => void }) {
  const items = [
    { id: "notebook" as const, label: uiText.shellDesk.notebook, icon: NotebookPen },
    { id: "sources" as const, label: uiText.tabs.sources, icon: Library },
    { id: "planning" as const, label: uiText.planning.title, icon: BookOpen },
    { id: "proposals" as const, label: uiText.tabs.proposals, icon: SplitSquareVertical },
    { id: "graph" as const, label: uiText.graph.title, icon: Network }
  ];
  return <nav className="author-material-navigation" aria-label={uiText.shellDesk.materials}><h2>{uiText.shellDesk.materialHeading}</h2>{items.map(({ id, label, icon: Icon }) => <button type="button" key={id} className={active === id ? "active" : ""} aria-current={active === id ? "page" : undefined} onClick={() => onNavigate(id)}><Icon size={15} /><span>{label}</span></button>)}</nav>;
}

export function AuthorSidebarTabs({ active, onChange }: { active: "chapters" | "sessions"; onChange: (value: "chapters" | "sessions") => void }) {
  return <div className="author-sidebar-tabs" role="group" aria-label={uiText.shellDesk.navigationView}><button type="button" aria-pressed={active === "chapters"} onClick={() => onChange("chapters")}><FolderOpen size={14} />{uiText.shellDesk.chapters}</button><button type="button" aria-pressed={active === "sessions"} onClick={() => onChange("sessions")}><MessageSquare size={14} />{uiText.shellDesk.sessions}</button></div>;
}
