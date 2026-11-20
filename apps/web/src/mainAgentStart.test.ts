import { beforeEach, expect, it, vi } from "vitest";
import { apiPost } from "./api";
import { postAuthoringSession } from "./authoring";
import { startMainAgentProject } from "./mainAgentStart";
vi.mock("./api", () => ({ apiPost: vi.fn() }));
vi.mock("./authoring", () => ({ postAuthoringSession: vi.fn() }));
beforeEach(() => { vi.resetAllMocks(); vi.mocked(apiPost).mockResolvedValue({ project_id: "project_local" }); vi.mocked(postAuthoringSession).mockResolvedValue({ id: "session_local", version: 1 } as never); });
const input = () => ({ apiBase: "http://local", idea: "A locked door", language: "en-US" as const, modelReady: true, onProjectCreated: vi.fn(async () => {}) });
it("saves an explicitly empty-reference project session before exactly one configured turn", async () => {
  const args = input(); await startMainAgentProject(args);
  expect(apiPost).toHaveBeenCalledTimes(1);
  expect(postAuthoringSession).toHaveBeenNthCalledWith(1, args.apiBase, "project_local", undefined, "", expect.objectContaining({ idea: args.idea, source_document_ids: [], outline_proposal_ids: [], draft_ids: [] }));
  expect(postAuthoringSession).toHaveBeenNthCalledWith(2, args.apiBase, "project_local", "session_local", "/turn", { expected_version: 1, message: args.idea, max_steps: 6 });
  expect(args.onProjectCreated).toHaveBeenCalledWith("project_local");
});
it("persists the idea without making a turn when no model is configured", async () => {
  await startMainAgentProject({ ...input(), modelReady: false });
  expect(postAuthoringSession).toHaveBeenCalledTimes(1);
});
it("opens the existing project after a failed or unknown paid result and never retries", async () => {
  vi.mocked(postAuthoringSession).mockResolvedValueOnce({ id: "session_local", version: 1 } as never).mockRejectedValueOnce(new Error("unknown result"));
  const args = input(); await expect(startMainAgentProject(args)).rejects.toThrow("unknown result");
  expect(args.onProjectCreated).toHaveBeenCalledWith("project_local");
  expect(postAuthoringSession).toHaveBeenCalledTimes(2);
  expect(apiPost).toHaveBeenCalledTimes(1);
});
it("exposes the existing project when session creation fails so the original idea can be restored there", async () => {
  vi.mocked(postAuthoringSession).mockRejectedValueOnce(new Error("session save failed"));
  const args = input(); await expect(startMainAgentProject(args)).rejects.toThrow("session save failed");
  expect(args.onProjectCreated).toHaveBeenCalledWith("project_local");
  expect(postAuthoringSession).toHaveBeenCalledTimes(1);
});
