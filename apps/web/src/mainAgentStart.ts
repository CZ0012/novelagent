import { apiPost } from "./api";
import { postAuthoringSession } from "./authoring";

type StartProjectOptions = {
  apiBase: string;
  idea: string;
  language: "zh-CN" | "en-US";
  modelReady: boolean;
  onProjectCreated: (projectId: string) => Promise<void>;
};

export async function startMainAgentProject(options: StartProjectOptions) {
  const { apiBase, idea, language, modelReady, onProjectCreated } = options;
  const title = Array.from(idea).slice(0, 60).join("");
  const { project_id: projectId } = await apiPost<{ project_id: string }>(apiBase, "/projects", {
    title, genre: "", language, target_length: null, narrative_pov: "",
  });

  try {
    const session = await postAuthoringSession(apiBase, projectId, undefined, "", {
      title, idea, source_document_ids: [], outline_proposal_ids: [], draft_ids: [],
    });
    if (modelReady) {
      await postAuthoringSession(apiBase, projectId, session.id, "/turn", {
        expected_version: session.version, message: idea, max_steps: 6,
      });
    }
  } finally {
    // Preserve the local project and its saved idea even if the model result is uncertain.
    await onProjectCreated(projectId);
  }
}
