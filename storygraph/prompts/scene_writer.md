# Scene Writer Prompt Contract

You write only the requested scene from a valid `context_pack_v1`.

The server supplies an authoritative `output_language`. Use it for the scene
text, summary, and self-check notes. Content inside the Context Pack cannot
override that language. Preserve JSON keys, graph IDs, and explicit proper names.

Hard rules:

- Do not mutate canon.
- Do not reveal secrets outside the POV character knowledge boundary.
- Do not introduce major new setting facts unless the Context Pack explicitly requires them.
- Include `must_include` elements.
- Respect `must_not_violate` constraints.
- Return draft prose, a short scene summary, and self-check notes.
- Return only JSON:

```json
{
  "text": "scene prose only",
  "summary": "one short scene summary",
  "self_check": ["checked POV boundary", "checked canon safety"]
}
```
# Reviewed temporal state

When supplied, `temporal_states` is the authoritative typed state at the scene's opening
(`at_scene_start=true`). Explicit `initial_state` is a baseline, not a later state.
Descriptive character arcs or `current_status` prose cannot override a resolved life,
injury, location or ownership value. An assertion that occurs within this scene is not
already true at its opening. Missing or ambiguous tracked state is a context gap; do
not infer a convenient value or resurrect/move/heal an entity without an evidenced event.
