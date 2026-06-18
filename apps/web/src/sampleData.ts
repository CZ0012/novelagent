export const demoProject = {
  projectId: "project_fantasy_demo",
  sceneId: "scene_003",
  title: "Fantasy Demo",
  chapters: [
    {
      id: "chapter_001",
      title: "The Old Bell Tower",
      scenes: [
        { id: "scene_001", title: "Harbor Ashes", status: "drafted" },
        { id: "scene_002", title: "Silver Crow Trace", status: "checked" },
        { id: "scene_003", title: "The Tower Search", status: "active" },
        { id: "scene_004", title: "The Mother Mark", status: "planned" },
        { id: "scene_005", title: "Lineage Payoff", status: "planned" }
      ]
    }
  ],
  graphPreview: [
    { source: "character_linj", edge: "KNOWS", target: "character_helianya" },
    { source: "organization_silver_crow", edge: "CONTROLS", target: "location_old_bell_tower" },
    { source: "foreshadowing_early_bell", edge: "POINTS_TO", target: "secret_lineage" }
  ],
  timeline: [
    { label: "Coup", state: "past" },
    { label: "Scene 003", state: "current" },
    { label: "Scene 005", state: "payoff" }
  ]
};
