import { beforeEach, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { activateLocale } from "./localization";
import { ModelConnectionSetup } from "./ModelConnectionSetup";
import { mergeConnectionCommit } from "./connectionCommit";
import { settingsToForm } from "./modelRouting";
import type { AgentSettings } from "./api";
const old: AgentSettings = { selected_preset_id:"p",agent_presets:[],scene_writer:"llm",provider_label:"Existing API",llm_base_url:"https://old.test/v1",llm_model:"old",llm_json_mode:true,api_key_configured:true,permission_level:"read_generate",connection_profiles:[],task_assignments:{discussion:null} };
beforeEach(async () => { await activateLocale("zh-CN"); });
it("shows simple model onboarding before advanced settings without rendering an API secret field by default", () => {
  const html = renderToStaticMarkup(<ModelConnectionSetup apiBase="http://localhost" settings={null} backendReady={false} backendReadGeneration={0} active busy={false} onStatus={() => undefined} onCommitted={() => undefined} />);
  expect(html).toContain("保存并用于主 Agent"); expect(html).toContain("仅保存连接"); expect(html).not.toContain('type="password"'); expect(html).toContain("disabled");
});
it("rebases a targeted save while preserving edits made during its request and existing API defaults", () => {
 const saved: AgentSettings = { ...old,connection_profiles:[{id:"new",name:"Plan",protocol:"responses",base_url:"",model:"exact",json_mode:true,api_key_configured:false}],task_assignments:{discussion:"new"} };
 const dirty = { ...settingsToForm(old),provider_label:"unsaved",permission_level:"full" as const, task_assignments:{discussion:"other",writing:"writer"} };
 const next = mergeConnectionCommit(dirty,old,saved,"new");
 expect(next.provider_label).toBe("unsaved"); expect(next.permission_level).toBe("full"); expect(next.llm_base_url).toBe(old.llm_base_url); expect(next.task_assignments).toEqual(dirty.task_assignments); expect(next.connection_profiles).toHaveLength(1);
 expect(mergeConnectionCommit(next,old,saved,"new").connection_profiles).toHaveLength(1);
 expect(mergeConnectionCommit(settingsToForm(old),old,saved,"new").task_assignments?.discussion).toBe("new");
});
it("save-only preserves the current Main Agent assignment", () => { expect(mergeConnectionCommit(settingsToForm(old),old,old,"missing").task_assignments?.discussion).toBeNull(); });
