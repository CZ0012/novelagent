import { describe, expect, it } from "vitest";
import { readWorkbenchView, writeWorkbenchView, WORKBENCH_VIEW_KEY, type WorkbenchView } from "./workbenchView";

function storage() { const values = new Map<string,string>(); return { getItem: (key:string) => values.get(key) ?? null, setItem: (key:string,value:string) => { values.set(key,value); } }; }
const view: WorkbenchView = { projectId:"p", sceneId:"s", chapterId:"c", area:"notebook", sessions:{p:"chat"} };
describe("backend-scoped author navigation preferences", () => {
 it("restores IDs and work area independently for each backend", () => {
  const data=storage(); writeWorkbenchView(data,"local-a",view); writeWorkbenchView(data,"local-b",{...view,projectId:"q",area:"write"});
  expect(readWorkbenchView(data,"local-a")).toEqual(view);
  expect(readWorkbenchView(data,"local-b")?.projectId).toBe("q");
  expect(readWorkbenchView(data,"other")).toBeNull();
 });
 it("drops malformed and incompatible preferences instead of navigating", () => {
  const data=storage(); data.setItem(WORKBENCH_VIEW_KEY,"{"); expect(readWorkbenchView(data,"local")).toBeNull();
  data.setItem(WORKBENCH_VIEW_KEY,JSON.stringify({version:1,backends:{local:{...view,area:"unknown"}}})); expect(readWorkbenchView(data,"local")).toBeNull();
  data.setItem(WORKBENCH_VIEW_KEY,JSON.stringify({version:2,backends:{local:view}})); expect(readWorkbenchView(data,"local")).toBeNull();
 });
 it("validates session IDs and tolerates unavailable browser storage", () => {
  const data=storage(); data.setItem(WORKBENCH_VIEW_KEY,JSON.stringify({version:1,backends:{local:{...view,sessions:{p:4,q:"ok"}}}}));
  expect(readWorkbenchView(data,"local")?.sessions).toEqual({q:"ok"});
  const denied={getItem:()=>{throw Error("denied")},setItem:()=>{throw Error("denied")}};
  expect(readWorkbenchView(denied,"local")).toBeNull(); expect(()=>writeWorkbenchView(denied,"local",view)).not.toThrow();
 });
});
import { MAIN_AGENT_LAYOUT_KEY, readMainAgentShare, writeMainAgentShare } from "./mainAgentLayout";
import { resolveWorkbenchProjectView } from "./workbenchView";

describe("per-project return navigation", () => {
 it("keeps A scene/chapter/area/session while visiting B and returning immediately", () => {
  const data=storage();
  const a:WorkbenchView={projectId:"A",sceneId:"a2",chapterId:"ac",area:"authoring",sessions:{A:"chat-a"}};
  const b:WorkbenchView={projectId:"B",sceneId:"b1",area:"notebook",sessions:{B:"chat-b"}};
  writeWorkbenchView(data,"local",a); writeWorkbenchView(data,"local",b);
  expect(readWorkbenchView(data,"local","A")).toEqual({...a,sessions:{A:"chat-a",B:"chat-b"}});
  expect(readWorkbenchView(data,"local","B")?.area).toBe("notebook");
  expect(readWorkbenchView(data,"local")?.projectId).toBe("B");
  writeWorkbenchView(data,"local",{...b,sessions:{B:""}});
  expect(readWorkbenchView(data,"local","B")?.sessions.B).toBe("");
  expect(resolveWorkbenchProjectView({id:"A",chapters:[{id:"ac",scenes:[{id:"a1"},{id:"a2"}]}]},readWorkbenchView(data,"local","A"))).toEqual({sceneId:"a2",chapterId:"ac",area:"authoring"});
 });
 it("migrates the previous backend-only view without losing A when B is saved",()=>{
  const data=storage();data.setItem(WORKBENCH_VIEW_KEY,JSON.stringify({version:1,backends:{local:view}}));
  writeWorkbenchView(data,"local",{projectId:"B",sceneId:"b",area:"write",sessions:{}});
  expect(readWorkbenchView(data,"local","p")).toEqual(view);
 });
 it("drops deleted scene/chapter IDs and never borrows another project's location",()=>{
  const project={id:"p",chapters:[{id:"new-chapter",scenes:[{id:"new-scene"}]}]};
  expect(resolveWorkbenchProjectView(project,view)).toEqual({sceneId:"new-scene",chapterId:null,area:"notebook"});
  expect(resolveWorkbenchProjectView({id:"empty",chapters:[]},view)).toEqual({sceneId:"",chapterId:null,area:"write"});
  expect(readWorkbenchView(storage(),"local","absent")).toBeNull();
 });
 it("keeps each project's split while inheriting the old global default",()=>{
  const data=storage();data.setItem(MAIN_AGENT_LAYOUT_KEY,JSON.stringify({version:1,share:42}));
  expect(readMainAgentShare(data,"A")).toBe(42);
  writeMainAgentShare(data,65,"A");writeMainAgentShare(data,31,"B");
  expect(readMainAgentShare(data,"A")).toBe(65);expect(readMainAgentShare(data,"B")).toBe(31);
  expect(readMainAgentShare(data)).toBe(42);expect(readMainAgentShare(data,"other")).toBe(42);
  data.setItem(`${MAIN_AGENT_LAYOUT_KEY}:project:broken`,"{");expect(readMainAgentShare(data,"broken")).toBe(42);
 });
});
