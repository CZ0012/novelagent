"""Trusted writing methods shipped with StoryGraph and read by the Main Agent."""
from importlib.resources import files
from types import MappingProxyType


SKILL_DESCRIPTIONS = MappingProxyType({
    "author-collaboration": "Turn a first idea into a conversation, alternatives or a pending design.",
    "project-navigation": "Find the author's current chapter or scene and open a relevant workspace.",
    "character-perspective": "Plan actions from each character's limited perspective and control revelation.",
    "review-and-revision": "Explain a finding, distinguish evidence from inference and trace a change.",
    "exact-draft-evidence": "Discuss an authorized passage and reconcile what the saved prose establishes.",
    "writer-and-canon": "Move from an approved scene design to a Writer draft and explicit human review.",
})

# Load only built-ins from this package. A manuscript, imported Source or working
# directory cannot register a new skill or override the program's permissions.
SKILLS = MappingProxyType({
    name: files(__package__).joinpath(name, "SKILL.md").read_text(encoding="utf-8").strip()
    for name in SKILL_DESCRIPTIONS
})
