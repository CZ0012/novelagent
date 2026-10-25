"""Bounded completion space for an explicitly planned scene, not a retry policy."""

from storygraph.models.context import ContextPack


def completion_budget(provider, base: int, *, thinking_allowance: int | None = None) -> int:
    """Expose explicit reasoning headroom in LLMRequest, before any paid-call guard.

    Provider defaults are deliberately unchanged. This is a visible output ceiling,
    not a hidden provider rewrite, retry, protocol switch or paid-call authorization.
    """
    if isinstance(base, bool) or not isinstance(base, int) or base < 1:
        raise ValueError("Completion baseline must be a positive integer")
    if thinking_allowance is not None and (type(thinking_allowance) is not int or not 1 <= thinking_allowance <= 65536):
        raise ValueError("Explicit thinking allowance must be an integer between 1 and 65536")
    mode = getattr(provider, "thinking_mode", "provider_default")
    effort = getattr(provider, "reasoning_effort", None)
    if effort not in {None, "low", "high", "max"} or mode not in {"provider_default", "enabled", "disabled"}:
        raise ValueError("Unsupported explicit completion mode")
    if mode == "disabled" and effort is not None:
        raise ValueError("Disabled thinking conflicts with explicit effort")
    if effort is None and mode != "enabled":
        return base
    # Provider low effort can still consume substantial reasoning on a large
    # structured prompt. Keep its mode low, with explicit visible headroom.
    allowance = {"low": 32768, "high": 32768, "max": 65536}.get(effort, 32768)
    if thinking_allowance is not None:
        allowance = thinking_allowance
    return min(65536, base + allowance)


def planned_completion_budget(context: ContextPack | None, *, baseline: int) -> int:
    plan = context.scene_plan if context is not None else None
    target = plan.target_length if plan is not None else None
    if target is None:
        return baseline
    # Chinese narration plus JSON summary/self-check overhead needs more than
    # the old 2,048-token default for a typical 2,500-character planned scene.
    # This is an output ceiling, never permission to pad prose or exceed scope.
    return min(16000, max(baseline, target * 2 + 1024))
