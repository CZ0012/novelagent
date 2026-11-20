"""A single-turn grant for discussing only a selected span of saved prose."""
from pydantic import Field, model_validator

from storygraph.core.errors import ContractError
from storygraph.models.common import ContractModel
from storygraph.models.draft import Draft
from storygraph.services.canon_snapshot import content_hash


class AuthoringSelectedPassage(ContractModel):
    draft_id: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1, strict=True)
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    start: int = Field(ge=0, strict=True)
    end: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def bounded_span(self):
        if not 0 < self.end - self.start <= 8000:
            raise ValueError("Select 1 to 8000 UTF-16 units from the saved Draft.")
        return self


def resolve_selected_passage(pin: AuthoringSelectedPassage, project_id: str,
                             scene_id: str | None, draft: Draft | None) -> dict:
    if (draft is None or not scene_id or draft.project_id != project_id
            or draft.scene_id != scene_id or draft.id != pin.draft_id or draft.discarded):
        raise ContractError("authoring_selected_passage_scope_mismatch")
    if draft.version != pin.version or content_hash(draft.text) != pin.text_sha256:
        raise ContractError("authoring_selected_passage_stale")
    encoded = draft.text.encode("utf-16-le")
    if pin.end > len(encoded) // 2:
        raise ContractError("authoring_selected_passage_invalid_span")
    try:
        text = encoded[pin.start * 2 : pin.end * 2].decode("utf-16-le")
    except UnicodeDecodeError:
        raise ContractError("authoring_selected_passage_invalid_span") from None
    return {**pin.model_dump(), "scene_id": scene_id, "offset_unit": "utf16", "text": text}
