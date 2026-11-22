import { apiGet, apiPatch, apiPost, apiPut } from "./api";
import { authoringPath, type AuthoringSession } from "./authoring";

export type ConversationTarget = { sessionId: string; messageId?: string };
export type SessionNavigation = { nonce: number; sessionId?: string; messageId?: string };
export type TitleMetadata = { version: number; origin: string; state: string; title: string };
type SessionRow = Pick<AuthoringSession, "id" | "title" | "updated_at"> & {title_metadata?: TitleMetadata | null};
type Page = { more: boolean; next_offset: number | null; total_matches: number };
type FoundMessage = { session_id: string; message_id: string; role: string; content: string };
export type AuthorMemory = { id: string; text: string; kind: "tentative" | "preference" | "decision";
  status: "active" | "withdrawn" | "tentative"; version: number; source_session_id: string;
  source_message_id: string; evidence: string };
export type Instructions = { instructions: string; version: number };
const projectPath = (project: string) => "/projects/" + encodeURIComponent(project);
function queryString(query: string, offset: number) {
  return new URLSearchParams({query, offset: String(offset), limit:"25"});
}
export function conversations(api: string, project: string, query: string, offset: number) {
  return apiGet<Page & {sessions: SessionRow[]}>(api, authoringPath(project) + "?" + queryString(query, offset));
}
export function findConversationMessages(api: string, project: string, query: string, offset: number) {
  return apiGet<Page & {records: FoundMessage[]}>(api, projectPath(project) + "/authoring-search?" + queryString(query, offset));
}
export function exactMessage(api: string, project: string, session: string, message: string) {
  return apiGet<{message: AuthoringSession["messages"][number]}>(api, authoringPath(project, session) + "/messages/" + encodeURIComponent(message));
}
export function renameConversation(api: string, project: string, row: SessionRow, title: string) {
  return apiPost<{title_metadata: TitleMetadata}>(api, authoringPath(project,row.id)+"/title", {
    title, expected_version: row.title_metadata?.version ?? 0,
  });
}
export function instructions(api: string, project: string) {
  return apiGet<Instructions>(api,projectPath(project)+"/author-context");
}
export function saveInstructions(api: string, project: string, text: string, version: number) {
  return apiPut<Instructions>(api,projectPath(project)+"/author-context",{instructions:text,expected_version:version});
}
export function memories(api: string, project: string, query: string, withdrawn: boolean, offset: number) {
  const params=queryString(query, offset);
  params.set("include_withdrawn",String(withdrawn));
  return apiGet<Page & {records:AuthorMemory[]}>(api,projectPath(project)+"/author-memories?"+params);
}
export function editMemory(api: string, project: string, entry: AuthorMemory, text: string, status: AuthorMemory["status"]) {
  return apiPatch<{memory:AuthorMemory}>(api,projectPath(project)+"/author-memories/"+encodeURIComponent(entry.id),
    {text, status, expected_version:entry.version});
}
