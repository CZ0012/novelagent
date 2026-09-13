/** Transient editor guards; no author text is persisted by these policies. */
export type DraftScope = {
  apiBase: string;
  projectId: string;
  sceneId: string;
};

export type DraftRequestSnapshot = {
  scope: DraftScope;
  sequence: number;
  editorRevision: number;
};

export type DraftResponseState = DraftRequestSnapshot;

export function draftScopesMatch(left: DraftScope, right: DraftScope): boolean {
  return left.apiBase === right.apiBase &&
    left.projectId === right.projectId &&
    left.sceneId === right.sceneId;
}

export function draftRequestIsCurrent(
  request: DraftRequestSnapshot,
  current: DraftResponseState
): boolean {
  return request.sequence === current.sequence && draftScopesMatch(request.scope, current.scope);
}

export function canHydrateDraftLoad(
  request: DraftRequestSnapshot,
  current: DraftResponseState,
  editorScope: DraftScope | null,
  dirty: boolean
): boolean {
  if (!draftRequestIsCurrent(request, current)) return false;
  if (request.editorRevision !== current.editorRevision) return false;
  // A confirmed scene switch can replace the previous scene's editor. A refresh
  // of the same scene must preserve edits made before the request as well.
  return !dirty || editorScope === null || !draftScopesMatch(editorScope, request.scope);
}

export function draftSaveCompletionPolicy(
  request: DraftRequestSnapshot,
  current: DraftResponseState
): {
  applySavedDraft: boolean;
  replaceEditor: boolean;
  continueNavigation: boolean;
} {
  const applySavedDraft = draftRequestIsCurrent(request, current);
  const unchanged = applySavedDraft && request.editorRevision === current.editorRevision;
  return {
    applySavedDraft,
    replaceEditor: unchanged,
    continueNavigation: unchanged
  };
}
