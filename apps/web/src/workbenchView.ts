import type { AuthorWorkArea } from "./AuthorWorkbenchChrome";

export const WORKBENCH_VIEW_KEY = "storygraph.author-workbench.v1";
export interface WorkbenchView { projectId: string; sceneId: string; chapterId?: string; area: AuthorWorkArea; sessions: Record<string, string>; }
const areas: AuthorWorkArea[] = ["write", "authoring", "checks", "notebook", "sources", "proposals", "planning", "graph", "workflow"];
export function readWorkbenchView(storage: Pick<Storage, "getItem">, backend: string, projectId?: string): WorkbenchView | null {
  try {
    const data = JSON.parse(storage.getItem(WORKBENCH_VIEW_KEY) ?? "null");
    const backendView = data?.version === 1 && data.backends?.[backend];
    const value = projectId ? (backendView?.projects?.[projectId] ?? (backendView?.projectId === projectId ? backendView : null)) : backendView;
    if (!value || typeof value.projectId !== "string" || typeof value.sceneId !== "string" || !areas.includes(value.area)) return null;
    const sessions: Record<string, string> = {};
    if (backendView.sessions && typeof backendView.sessions === "object") for (const [key, id] of Object.entries(backendView.sessions)) if (typeof id === "string" && id.length <= 256) sessions[key] = id;
    return { projectId: value.projectId, sceneId: value.sceneId, area: value.area, ...(typeof value.chapterId === "string" ? { chapterId: value.chapterId } : {}), sessions };
  } catch { return null; }
}
export function writeWorkbenchView(storage: Pick<Storage, "getItem" | "setItem">, backend: string, view: WorkbenchView): void {
  try {
    const previous = JSON.parse(storage.getItem(WORKBENCH_VIEW_KEY) ?? "null");
    const backends = previous?.version === 1 && previous.backends && typeof previous.backends === "object" ? previous.backends : {};
    const prior = backends[backend];
    const projects = { ...(prior?.projects ?? {}) };
    // Migrate the old backend-wide last view before recording another project.
    if (prior?.projectId && !projects[prior.projectId]) projects[prior.projectId] = { projectId: prior.projectId, sceneId: prior.sceneId, chapterId: prior.chapterId, area: prior.area };
    projects[view.projectId] = { projectId: view.projectId, sceneId: view.sceneId, ...(view.chapterId ? { chapterId: view.chapterId } : {}), area: view.area };
    storage.setItem(WORKBENCH_VIEW_KEY, JSON.stringify({ version: 1, backends: { ...backends, [backend]: { ...view, sessions: { ...prior?.sessions, ...view.sessions }, projects } } }));
  } catch { /* Local preference failures must never block author work. */ }
}

/** Resolve preferences against current project IDs; a deleted item is never reopened. */
export function resolveWorkbenchProjectView(project: { id: string; chapters: Array<{ id: string; scenes: Array<{ id: string }> }> }, saved: WorkbenchView | null) {
  const current = saved?.projectId === project.id ? saved : null;
  const scenes = project.chapters.flatMap(chapter => chapter.scenes);
  return {
    sceneId: scenes.find(scene => scene.id === current?.sceneId)?.id ?? scenes[0]?.id ?? "",
    chapterId: project.chapters.find(chapter => chapter.id === current?.chapterId)?.id ?? null,
    area: current?.area ?? "write" as AuthorWorkArea
  };
}
