export type ContextGap = {
  kind: string;
  ref: string;
  severity: "low" | "medium" | "high" | "critical";
  message: string;
  source?: string | null;
};

export type ContextPack = {
  contract_version: "context_pack_v1";
  project_id: string;
  scene_id: string;
  chapter_id: string;
  pov_character_id: string;
  location_id: string;
  timeline_position: string;
  scene_goal: string;
  conflict: string;
  required_characters: string[];
  active_relationships: string[];
  knowledge_boundaries: Array<{
    character_id: string;
    knows: string[];
    does_not_know: string[];
    falsely_believes: string[];
    suspects: string[];
    hides: string[];
    source_refs: string[];
  }>;
  must_include: string[];
  must_not_violate: string[];
  unresolved_foreshadowing: string[];
  relevant_world_rules: string[];
  previous_scene_summary?: string | null;
  style_constraints: Record<string, unknown>;
  retrieved_style_samples: string[];
  missing_context: ContextGap[];
  provenance: {
    graph_query_ids: string[];
    draft_refs: string[];
    style_sample_refs: string[];
    author_instruction_refs: string[];
    built_at: string;
  };
  budget: {
    target_tokens: number;
    estimated_tokens: number;
    priority_order: string[];
    dropped_items: string[];
  };
};

export type Draft = {
  id: string;
  project_id: string;
  scene_id: string;
  version: number;
  text: string;
  summary?: string | null;
  discarded: boolean;
  created_at: string;
  updated_at: string;
};

export type ProposalArtifactType =
  | "scene_draft"
  | "fact_draft"
  | "scene_rebuild"
  | "canon_patch"
  | "outline_draft"
  | "project_structure_draft";

export type ProposalStatus =
  | "drafting"
  | "agent_revised"
  | "author_revised"
  | "ready_for_review"
  | "accepted"
  | "rejected";

export type ProposalRef = {
  kind: string;
  ref: string;
  note?: string | null;
  quote?: string | null;
  source_span?: Record<string, unknown> | null;
};

export type ProposalReviewDecision = {
  status: "none" | "accepted" | "rejected";
  reviewer?: string | null;
  reviewed_at?: string | null;
  note?: string | null;
};

export type ProposalArtifact = {
  contract_version: "proposal_artifact_v1";
  id: string;
  project_id: string;
  artifact_type: ProposalArtifactType;
  status: ProposalStatus;
  title: string;
  body: string;
  body_format: "plain_text" | "markdown" | "structured_json";
  target_refs: ProposalRef[];
  source_refs: ProposalRef[];
  provenance: {
    created_by: string;
    created_via: "manual" | "llm" | "import" | "workflow" | "api";
    workflow_run_id?: string | null;
    model_ref?: string | null;
    note?: string | null;
  };
  version: number;
  derived_refs: ProposalRef[];
  review_decision: ProposalReviewDecision;
  created_at: string;
  updated_at: string;
};

export type ProposalDraftPromotionResult = {
  proposal: ProposalArtifact;
  draft: Draft;
};

export type DocumentFactExtractionResult = {
  proposal: ProposalArtifact;
  source_draft: Draft;
  candidate_previews: CandidateFact[];
  truncated: boolean;
};

export type ProjectStructureDraftResult = {
  proposal: ProposalArtifact;
  outline: {
    schema: "project_structure_draft_v1";
    project_id: string;
    source_title: string;
    summary: string;
    chapters: Array<{
      title: string;
      chapter_index: number;
      summary: string;
      purpose: string;
      scenes: Array<{
        title: string;
        scene_index: number;
        summary: string;
        goal: string;
        conflict: string;
        timeline_position?: string | null;
        pov_label?: string | null;
        location_label?: string | null;
      }>;
    }>;
    truncated?: boolean;
  };
  truncated: boolean;
};

export type ProjectStructureApplyResult = {
  proposal: ProposalArtifact;
  chapters: GraphNodePayload[];
  scenes: GraphNodePayload[];
  already_applied: boolean;
};

export type AgentDiscussionMode = "discuss" | "revise_selection" | "revise_scene";

export type AgentDiscussionSource = {
  kind: string;
  ref: string;
  title: string;
  text: string;
  note?: string | null;
};

export type AgentDiscussionRequest = {
  mode: AgentDiscussionMode;
  instruction: string;
  selected_text?: string | null;
  base_text?: string | null;
  include_context_pack: boolean;
  include_latest_draft: boolean;
  local_sources: AgentDiscussionSource[];
  allow_web_search: boolean;
  web_search_query?: string | null;
};

export type AgentDiscussionResult = {
  proposal: ProposalArtifact;
  reply: string;
  web_results: Array<{
    title: string;
    url: string;
    snippet: string;
  }>;
  truncated_sources: string[];
  replacement_applied: boolean;
};

export type ProposalCandidatePromotionResult = {
  proposal: ProposalArtifact;
  source_draft: Draft;
  candidates: CandidateFact[];
};

export type GraphNodePayload = {
  id: string;
  type: string;
  status: string;
  properties: Record<string, unknown>;
};

export type SceneOutline = {
  id: string;
  title: string;
  scene_index?: number | null;
  status?: string | null;
  pov_character_id?: string | null;
  location_id?: string | null;
  timeline_position?: string | null;
  goal?: string | null;
  conflict?: string | null;
  outcome?: string | null;
  emotional_turn?: string | null;
  previous_scene_id?: string | null;
  style_constraints?: Record<string, unknown> | null;
  properties: Record<string, unknown>;
};

export type ChapterOutline = {
  id: string;
  title: string;
  volume_index?: number | null;
  chapter_index?: number | null;
  status?: string | null;
  summary?: string | null;
  purpose?: string | null;
  properties: Record<string, unknown>;
  scenes: SceneOutline[];
};

export type ProjectOutline = {
  id: string;
  title: string;
  genre?: string | null;
  language?: string | null;
  status: string;
  properties: Record<string, unknown>;
  chapters: ChapterOutline[];
};

export type ProjectGraphPreview = {
  project_id: string;
  nodes: Array<{
    id: string;
    type: string;
    label: string;
  }>;
  relationships: Array<{
    id: string;
    source_id: string;
    source_label: string;
    type: string;
    target_id: string;
    target_label: string;
  }>;
  timeline: Array<{
    id: string;
    label: string;
    state: string;
    chapter_id: string;
    scene_index?: number | null;
  }>;
  truncated: boolean;
};

export type WorkflowRun = {
  id: string;
  contract_version: "workflow_run_v1";
  workflow_name: string;
  project_id: string;
  scene_id?: string | null;
  status: string;
  current_step?: string | null;
  steps: WorkflowStep[];
  review_payload: {
    status: "none" | "pending";
    candidate_ids: string[];
    source_draft_id?: string | null;
    note?: string | null;
  };
  created_at: string;
  updated_at: string;
};

export type WorkflowStep = {
  name: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  artifact_refs: Record<string, unknown>;
  message?: string | null;
};

export type ContinuityReport = {
  contract_version: "continuity_report_v1";
  status: string;
  summary: string;
  issues: Array<{
    id: string;
    issue_type: string;
    severity: string;
    description: string;
    suggestion: string;
    blocking: boolean;
  }>;
  checked_dimensions: string[];
};

export type CandidateFact = {
  id: string;
  project_id: string;
  fact_type: string;
  subject_id: string;
  relation: string;
  object_id?: string | null;
  value?: string | null;
  source_scene_id: string;
  source_draft_id: string;
  source_span: {
    start_offset: number;
    end_offset: number;
    quote: string;
  };
  confidence: number;
  status: string;
  rationale: string;
  evidence: Array<{
    kind: string;
    ref: string;
    note?: string | null;
    quote?: string | null;
  }>;
  proposed_graph_patch: {
    operation: string;
    target: string;
    properties: Record<string, unknown>;
    source_ref: string;
  };
  review: {
    status: string;
    reviewer?: string | null;
    reviewed_at?: string | null;
    note?: string | null;
  };
  created_at: string;
};

export type SceneRunResult = {
  context_pack: ContextPack;
  draft: Draft | null;
  proposal?: ProposalArtifact | null;
  continuity_report: ContinuityReport | null;
  candidates: CandidateFact[];
  workflow_run: WorkflowRun;
};

export type AgentPermissionLevel = "read_only" | "read_generate" | "full";

export type AgentSettings = {
  scene_writer: "rule_based" | "llm";
  provider_label: string;
  llm_base_url: string;
  llm_model: string;
  api_key_configured: boolean;
  api_key_preview?: string | null;
  llm_json_mode: boolean;
  permission_level: AgentPermissionLevel;
  permission_descriptions?: Record<AgentPermissionLevel, string>;
};

export type AgentSettingsUpdate = {
  scene_writer: "rule_based" | "llm";
  provider_label: string;
  llm_base_url: string;
  llm_model: string;
  llm_api_key?: string | null;
  clear_api_key?: boolean;
  llm_json_mode: boolean;
  permission_level: AgentPermissionLevel;
};

export type DemoSeedResult = {
  project_id: string;
  scene_id: string;
  nodes_created: number;
  nodes_updated?: number;
  relationships_created: number;
  relationships_updated?: number;
  nodes_skipped: string[];
  relationships_skipped: string[];
};

export type DemoArchiveResult = {
  project_id: string;
  nodes_archived: number;
  relationships_archived: number;
};

export async function apiGet<T>(baseUrl: string, path: string): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`);
  return parseResponse<T>(response);
}

export async function apiPost<T>(
  baseUrl: string,
  path: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  return parseResponse<T>(response);
}

export async function apiPut<T>(
  baseUrl: string,
  path: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "PUT",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  return parseResponse<T>(response);
}

export async function apiPatch<T>(
  baseUrl: string,
  path: string,
  body?: unknown
): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: "PATCH",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body)
  });
  return parseResponse<T>(response);
}

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let payload: any = {};
  try {
    payload = text ? JSON.parse(text) : {};
  } catch {
    if (!response.ok) {
      throw new Error(text || response.statusText);
    }
    throw new Error("后端返回了无法解析的 JSON。");
  }
  if (!response.ok) {
    const detail = payload?.detail?.message ?? payload?.detail ?? response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return payload as T;
}
