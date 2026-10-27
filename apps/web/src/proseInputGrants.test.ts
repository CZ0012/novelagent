import { webcrypto } from "node:crypto";
import { expect, it } from "vitest";
import { proseInputGrants } from "./proseInputGrants";
import type { AgentDiscussionRequest, Draft } from "./api";
Object.defineProperty(globalThis, "crypto", { value: webcrypto, configurable: true });
const draft = { id:"d", project_id:"p", scene_id:"s", version:2, text:"私有前文😀选区后文" } as Draft;
const base = { mode:"create_scene", instruction:"  只写本场动作。  ", include_context_pack:true, include_latest_draft:false, included_draft_id:null, local_sources:[], source_document_ids:[], allow_web_search:false, cross_language_policy:"project_only" } as AgentDiscussionRequest;
it("binds only the explicit instruction for new prose and no grant for discussion", async () => {
  expect(await proseInputGrants({ ...base, mode:"discuss" }, null)).toBeUndefined();
  const result=await proseInputGrants(base,null);
  expect(result).toMatchObject({instruction:true,target:"none"});
  const hash=await webcrypto.subtle.digest("SHA-256",new TextEncoder().encode(base.instruction.trim()));
  expect(result?.instruction_sha256).toBe(Array.from(new Uint8Array(hash),n=>n.toString(16).padStart(2,"0")).join(""));
});
it("pins continuation/full revision and exact UTF16 selection without granting surrounding text", async () => {
  const request={...base,include_latest_draft:true,included_draft_id:draft.id};
  expect(await proseInputGrants({...request,mode:"continue_scene"},draft)).toMatchObject({target:"draft",draft_id:"d",version:2});
  const result=await proseInputGrants({...request,mode:"revise_selection",selected_start:6,selected_end:8,selected_text:"选区"},draft);
  expect(result).toMatchObject({target:"selection",start:6,end:8,expected_text:"选区",offset_unit:"utf16"});
  expect(JSON.stringify(result)).not.toContain("私有前文");
  await expect(proseInputGrants({...request,mode:"revise_selection",selected_start:5,selected_end:8,selected_text:"选区"},draft)).rejects.toThrow("Exact saved selection");
  await expect(proseInputGrants({...request,mode:"revise_scene",included_draft_id:"foreign"},draft)).rejects.toThrow("Pinned saved Draft");
});
