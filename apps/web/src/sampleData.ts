export const demoProject = {
  projectId: "project_fantasy_demo",
  sceneId: "scene_003",
  title: "奇幻演示项目",
  chapters: [
    {
      id: "chapter_001",
      title: "旧钟楼",
      scenes: [
        { id: "scene_001", title: "港口余烬", status: "已起草" },
        { id: "scene_002", title: "银鸦踪迹", status: "已检查" },
        { id: "scene_003", title: "钟楼搜寻", status: "当前" },
        { id: "scene_004", title: "母亲印记", status: "计划中" },
        { id: "scene_005", title: "血脉回收", status: "计划中" }
      ]
    }
  ],
  graphPreview: [
    { source: "character_linj", edge: "KNOWS", target: "character_helianya" },
    { source: "organization_silver_crow", edge: "CONTROLS", target: "location_old_bell_tower" },
    { source: "foreshadowing_early_bell", edge: "POINTS_TO", target: "secret_lineage" }
  ],
  timeline: [
    { label: "政变", state: "past" },
    { label: "场景 003", state: "current" },
    { label: "场景 005", state: "payoff" }
  ]
};
