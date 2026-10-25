"""Whole-leaf creative edits with deterministic pinned-source before values."""

from copy import deepcopy

from storygraph.models.longform import CreativeRevisionOutput, TargetedRevisionChange, TargetedRevisionOutput


def parse_revision_output(raw, payload):
    """Do not salvage legacy mismatches or guess paths, types or substrings."""
    if isinstance(raw, dict) and set(raw) == {"replacements"}:
        creative = CreativeRevisionOutput.model_validate(raw)
        current = payload["current_values"]
        allowed = set(payload["allowed_paths"])
        changes = []
        for replacement in creative.replacements:
            if replacement.path not in allowed or replacement.path not in current:
                raise ValueError("Unknown creative replacement path.")
            changes.append(TargetedRevisionChange(path=replacement.path,
                before=deepcopy(current[replacement.path]), after=deepcopy(replacement.after)))
        return TargetedRevisionOutput(changes=changes)
    # Complete legacy changes still retain every original before value for the
    # existing exact/full-or-unique-span validator. No mixed-format fallback.
    return TargetedRevisionOutput.model_validate(raw)
