import { useEffect, useState } from "react";
import { apiGet } from "./api";
import { uiText } from "./localization";
import type { LongformStyle } from "./longformPlanning";
export function ProjectStyleSummary({ apiBase, projectId, revision }: { apiBase: string; projectId: string; revision: string }) {
  const [profile, setProfile] = useState<(LongformStyle & { id: string; sha256: string }) | null>(null);
  useEffect(() => {
    let active = true; setProfile(null);
    if (projectId) apiGet<{ style_profile?: LongformStyle & { id: string; sha256: string } }>(apiBase, `/projects/${encodeURIComponent(projectId)}/style-profile`).then((result) => { if (active) { const style = result.style_profile; setProfile(style && typeof style.id === "string" && typeof style.sha256 === "string" && typeof style.name === "string" && Array.isArray(style.rubric) && Array.isArray(style.banned_patterns) ? style : null); } }).catch(() => { /* No profile is never fabricated. */ });
    return () => { active = false; };
  }, [apiBase, projectId, revision]);
  if (!profile) return null;
  const t = uiText.planning;
  return <details className="project-style-summary"><summary>{uiText.contextEvidence.approvedStyle}: {profile.name}</summary><dl>{([['pov', 'pov'], ['tense', 'tense'], ['tone', 'tone'], ['diction', 'diction'], ['sentence_rhythm', 'rhythm'], ['dialogue_style', 'dialogue']] as const).map(([field, label]) => <div key={field}><dt>{t[label]}</dt><dd>{profile[field]}</dd></div>)}<dt>{t.rubric}</dt><dd>{profile.rubric.join(" · ")}</dd><dt>{t.banned}</dt><dd>{profile.banned_patterns.join(' · ')}</dd></dl><small>{profile.id} · {profile.sha256.slice(0, 12)}</small></details>;
}
