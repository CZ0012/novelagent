import { ApiRequestError, type OutputLanguage, type ProposalArtifact } from "./api";

export type OutlineLanguageChange = {
  node_id: string;
  node_type: "Chapter" | "Scene";
  field: string;
  before: string;
  after: string;
};
export type OutlineLanguagePatch = {
  schema: "outline_language_patch_v1";
  project_id: string;
  output_language: OutputLanguage;
  changes: OutlineLanguageChange[];
};

const fields = {
  Chapter: ["title", "summary", "purpose"],
  Scene: ["title", "summary", "goal", "conflict", "timeline_position", "outcome", "emotional_turn"]
};

/** Recognize this narrow proposal schema, never arbitrary canon patches. */
export function parseOutlineLanguagePatch(proposal: ProposalArtifact | null): OutlineLanguagePatch | null {
  if (!proposal || proposal.artifact_type !== "canon_patch" || proposal.body_format !== "structured_json") return null;
  try {
    const body = JSON.parse(proposal.body);
    if (!body || body.schema !== "outline_language_patch_v1" || body.project_id !== proposal.project_id ||
      !["zh-CN", "en-US"].includes(body.output_language) || body.output_language !== proposal.content_language ||
      !Array.isArray(body.changes) || !body.changes.length || body.changes.length > 512) return null;
    if (Object.keys(body).some((key) => !["schema", "project_id", "output_language", "changes"].includes(key))) return null;
    const targets = new Set<string>();
    for (const change of body.changes) {
      if (!change || !Object.prototype.hasOwnProperty.call(fields, change.node_type) ||
        !(fields[change.node_type as keyof typeof fields].includes(change.field)) ||
        typeof change.node_id !== "string" || !change.node_id.trim() || [...change.node_id].length > 256 ||
        typeof change.before !== "string" || !change.before || [...change.before].length > 2000 ||
        typeof change.after !== "string" || [...change.after].length > 2000 ||
        !change.after.trim() || change.before === change.after) return null;
      if (Object.keys(change).some((key) => !["node_id", "node_type", "field", "before", "after"].includes(key))) return null;
      const target = `${change.node_id}\u0000${change.field}`;
      if (targets.has(target)) return null;
      targets.add(target);
    }
    return body as OutlineLanguagePatch;
  } catch { return null; }
}

export function canApplyOutlineLanguagePatch(proposal: ProposalArtifact | null, dirty: boolean, projectId: string): boolean {
  return Boolean(proposal && !dirty && proposal.status === "accepted" && proposal.project_id === projectId && parseOutlineLanguagePatch(proposal) && !outlineLanguageApplicationRecorded(proposal));
}

/** Only a complete, unique set of server-recorded canon events marks success.
 * A partial/missing receipt still permits the backend's idempotent recovery. */
export function outlineLanguageApplicationRecorded(proposal: ProposalArtifact | null): boolean {
  const patch = parseOutlineLanguagePatch(proposal);
  if (!patch || proposal?.status !== "accepted") return false;
  const expectedCount = new Set(patch.changes.map((change) => change.node_id)).size;
  const refs = proposal.derived_refs ?? [];
  return refs.length === expectedCount && refs.every((ref) => ref.kind === "canon_event" && /^evt_ol_[0-9a-f]{32}$/.test(ref.ref)) &&
    new Set(refs.map((ref) => ref.ref)).size === expectedCount;
}

const failureKeys = {
  outline_language_no_changes: "outlineLanguageNoChanges",
  outline_language_stale: "outlineLanguageStale",
  outline_language_invalid: "outlineLanguageInvalid",
  outline_language_backend_unsupported: "outlineLanguageUnsupported",
  outline_language_provider_endpoint_not_found: "outlineLanguageProviderEndpoint",
  outline_language_provider_invalid_credentials: "outlineLanguageProviderCredentials",
  outline_language_provider_rate_limit: "outlineLanguageProviderRateLimit",
  outline_language_provider_invalid_request: "outlineLanguageProviderInvalidRequest",
  outline_language_provider_provider_unavailable: "outlineLanguageProviderUnavailable",
  outline_language_provider_connection_error: "outlineLanguageProviderConnection",
  outline_language_provider_invalid_response: "outlineLanguageProviderResponse",
  outline_language_provider_request_failed: "outlineLanguageProviderFailed",
  outline_language_provider_failed: "outlineLanguageProviderFailed"
} as const;

export function outlineLanguageFailureKey(error: unknown): typeof failureKeys[keyof typeof failureKeys] | null {
  return error instanceof ApiRequestError && error.category && Object.prototype.hasOwnProperty.call(failureKeys, error.category)
    ? failureKeys[error.category as keyof typeof failureKeys] : null;
}

export function outlineLanguageScopeMatches(
  target: { apiBase: string; projectId: string }, apiBase: string, projectId: string
): boolean {
  return target.apiBase === apiBase && target.projectId === projectId;
}
