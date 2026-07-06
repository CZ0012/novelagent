"""LLM-backed author/Agent discussion for draft revision proposals."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any
from urllib import parse, request

from storygraph.core.errors import ContractError
from storygraph.models.context import ContextPack
from storygraph.models.draft import Draft
from storygraph.models.proposal import ProposalArtifactType, ProposalBodyFormat, ProposalRef
from storygraph.services.llm_provider import LLMMessage, LLMProvider, LLMRequest


DiscussionMode = str


@dataclass(frozen=True)
class DiscussionSource:
    kind: str
    ref: str
    title: str
    text: str
    note: str | None = None


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class AgentDiscussionDraft:
    reply: str
    proposal_title: str
    proposal_body: str
    artifact_type: ProposalArtifactType
    body_format: ProposalBodyFormat
    source_refs: list[ProposalRef] = field(default_factory=list)
    target_refs: list[ProposalRef] = field(default_factory=list)
    web_results: list[WebSearchResult] = field(default_factory=list)
    truncated_sources: list[str] = field(default_factory=list)
    replacement_applied: bool = False


class SimpleWebSearchClient:
    """Small no-key search helper used only when the author explicitly asks."""

    endpoint = "https://api.duckduckgo.com/"

    def search(self, query: str, *, max_results: int = 5) -> list[WebSearchResult]:
        if not query.strip():
            return []
        params = parse.urlencode(
            {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
            }
        )
        http_request = request.Request(
            f"{self.endpoint}?{params}",
            headers={"User-Agent": "StoryGraph-Agent/agent-discussion"},
        )
        with request.urlopen(http_request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return self._results_from_payload(payload, max_results=max_results)

    def _results_from_payload(
        self,
        payload: dict[str, Any],
        *,
        max_results: int,
    ) -> list[WebSearchResult]:
        results: list[WebSearchResult] = []
        heading = _text(payload.get("Heading"))
        abstract = _text(payload.get("AbstractText"))
        abstract_url = _text(payload.get("AbstractURL"))
        if heading and abstract:
            results.append(WebSearchResult(title=heading, url=abstract_url, snippet=abstract))

        for topic in _flatten_related_topics(payload.get("RelatedTopics")):
            if len(results) >= max_results:
                break
            title = _text(topic.get("FirstURL")) or _text(topic.get("Text"))[:80]
            snippet = _text(topic.get("Text"))
            url = _text(topic.get("FirstURL"))
            if snippet:
                results.append(WebSearchResult(title=title or "Search result", url=url, snippet=snippet))
        return results[:max_results]


class AgentDiscussionService:
    """Creates non-canon Proposal Store drafts from a focused author request."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        model: str,
        prompt_path: Path | None = None,
        web_search_client: SimpleWebSearchClient | None = None,
        max_source_chars: int = 12000,
        max_local_source_chars: int = 5000,
        temperature: float = 0.2,
    ) -> None:
        self.provider = provider
        self.model = model
        self.prompt_path = prompt_path or Path(__file__).parents[1] / "prompts" / "agent_discussion.md"
        self.web_search_client = web_search_client or SimpleWebSearchClient()
        self.max_source_chars = max_source_chars
        self.max_local_source_chars = max_local_source_chars
        self.temperature = temperature

    def discuss(
        self,
        *,
        project_id: str,
        scene_id: str,
        instruction: str,
        mode: DiscussionMode,
        selected_text: str | None = None,
        base_text: str | None = None,
        context_pack: ContextPack | None = None,
        latest_draft: Draft | None = None,
        local_sources: list[DiscussionSource] | None = None,
        allow_web_search: bool = False,
        web_search_query: str | None = None,
    ) -> AgentDiscussionDraft:
        instruction = instruction.strip()
        if not instruction:
            raise ContractError("Agent discussion requires an author instruction.")
        if mode not in {"discuss", "revise_selection", "revise_scene"}:
            raise ContractError("Unknown agent discussion mode.")

        selected_text = (selected_text or "").strip()
        base_text = base_text if base_text is not None else latest_draft.text if latest_draft else ""
        if mode == "revise_selection" and not selected_text:
            raise ContractError("revise_selection requires selected_text.")
        if mode in {"revise_selection", "revise_scene"} and not base_text.strip():
            raise ContractError("Revision modes require base_text or a latest scene draft.")

        web_results = (
            self.web_search_client.search(web_search_query or instruction)
            if allow_web_search
            else []
        )
        payload, truncated_sources = self._payload(
            project_id=project_id,
            scene_id=scene_id,
            instruction=instruction,
            mode=mode,
            selected_text=selected_text,
            base_text=base_text,
            context_pack=context_pack,
            latest_draft=latest_draft,
            local_sources=local_sources or [],
            web_results=web_results,
        )
        response = self.provider.generate(
            LLMRequest(
                model=self.model,
                temperature=self.temperature,
                max_tokens=4096,
                messages=[
                    LLMMessage(role="system", content=self.prompt_path.read_text(encoding="utf-8")),
                    LLMMessage(role="user", content=json.dumps(payload, ensure_ascii=False, indent=2)),
                ],
            )
        )
        parsed = _parse_discussion_response(response.content)
        draft = self._draft_from_response(
            mode=mode,
            instruction=instruction,
            scene_id=scene_id,
            base_text=base_text,
            selected_text=selected_text,
            parsed=parsed,
        )
        return AgentDiscussionDraft(
            **draft,
            source_refs=self._source_refs(
                latest_draft=latest_draft,
                context_pack=context_pack,
                local_sources=local_sources or [],
                web_results=web_results,
                instruction=instruction,
            ),
            target_refs=[ProposalRef(kind="scene", ref=scene_id)],
            web_results=web_results,
            truncated_sources=truncated_sources,
        )

    def _payload(
        self,
        *,
        project_id: str,
        scene_id: str,
        instruction: str,
        mode: DiscussionMode,
        selected_text: str,
        base_text: str,
        context_pack: ContextPack | None,
        latest_draft: Draft | None,
        local_sources: list[DiscussionSource],
        web_results: list[WebSearchResult],
    ) -> tuple[dict[str, Any], list[str]]:
        base_slice, base_truncated = _clip(base_text, self.max_source_chars)
        truncated_sources = ["base_text"] if base_truncated else []
        clipped_sources = []
        for source in local_sources:
            text, truncated = _clip(source.text, self.max_local_source_chars)
            if truncated:
                truncated_sources.append(source.ref)
            clipped_sources.append(
                {
                    "kind": source.kind,
                    "ref": source.ref,
                    "title": source.title,
                    "note": source.note,
                    "text": text,
                }
            )
        payload: dict[str, Any] = {
            "contract": "agent_discussion_request_v1",
            "project_id": project_id,
            "scene_id": scene_id,
            "mode": mode,
            "author_instruction": instruction,
            "selected_text": selected_text,
            "base_text": base_slice,
            "base_text_truncated": base_truncated,
            "latest_draft": (
                {
                    "id": latest_draft.id,
                    "version": latest_draft.version,
                    "summary": latest_draft.summary,
                }
                if latest_draft
                else None
            ),
            "context_pack": context_pack.model_dump() if context_pack else None,
            "local_sources": clipped_sources,
            "web_search_results": [
                {"title": result.title, "url": result.url, "snippet": result.snippet}
                for result in web_results
            ],
            "safety": {
                "proposal_only": True,
                "must_not_commit_canon": True,
                "must_not_create_candidate_facts": True,
                "promotion_requires_author_review": True,
            },
        }
        return payload, truncated_sources

    def _draft_from_response(
        self,
        *,
        mode: DiscussionMode,
        instruction: str,
        scene_id: str,
        base_text: str,
        selected_text: str,
        parsed: dict[str, Any],
    ) -> dict[str, Any]:
        reply = _required_str(parsed, "reply")
        proposal_title = _optional_str(parsed.get("proposal_title")) or f"Agent 讨论：{scene_id}"
        proposal_body = _optional_str(parsed.get("proposal_body"))
        replacement_text = _optional_str(parsed.get("replacement_text"))

        if mode == "discuss":
            body = proposal_body or _discussion_markdown(
                instruction=instruction,
                reply=reply,
                selected_text=selected_text,
                replacement_text=replacement_text,
            )
            return {
                "reply": reply,
                "proposal_title": proposal_title,
                "proposal_body": body,
                "artifact_type": "scene_rebuild",
                "body_format": "markdown",
                "replacement_applied": False,
            }

        if mode == "revise_scene":
            body = proposal_body or replacement_text
            if not body:
                raise ContractError("revise_scene response requires proposal_body.")
            return {
                "reply": reply,
                "proposal_title": proposal_title,
                "proposal_body": body,
                "artifact_type": "scene_draft",
                "body_format": "plain_text",
                "replacement_applied": True,
            }

        if not replacement_text:
            raise ContractError("revise_selection response requires replacement_text.")
        applied = _replace_unique(base_text, selected_text, replacement_text)
        if applied is None:
            body = _discussion_markdown(
                instruction=instruction,
                reply=reply,
                selected_text=selected_text,
                replacement_text=replacement_text,
                warning="未能在基础草稿中唯一定位选中段落，因此没有生成完整场景草稿。",
            )
            return {
                "reply": reply,
                "proposal_title": proposal_title,
                "proposal_body": body,
                "artifact_type": "scene_rebuild",
                "body_format": "markdown",
                "replacement_applied": False,
            }
        return {
            "reply": reply,
            "proposal_title": proposal_title,
            "proposal_body": applied,
            "artifact_type": "scene_draft",
            "body_format": "plain_text",
            "replacement_applied": True,
        }

    def _source_refs(
        self,
        *,
        latest_draft: Draft | None,
        context_pack: ContextPack | None,
        local_sources: list[DiscussionSource],
        web_results: list[WebSearchResult],
        instruction: str,
    ) -> list[ProposalRef]:
        refs = [
            ProposalRef(kind="author_instruction", ref="agent_discussion", note=instruction[:200])
        ]
        if latest_draft:
            refs.append(ProposalRef(kind="draft", ref=latest_draft.id, note="Latest scene draft."))
        if context_pack:
            refs.append(
                ProposalRef(
                    kind="context_pack",
                    ref=f"{context_pack.project_id}:{context_pack.scene_id}",
                    note="Context Pack used as revision constraints.",
                )
            )
        refs.extend(
            ProposalRef(kind=source.kind or "imported_document", ref=source.ref, note=source.title)
            for source in local_sources
        )
        refs.extend(
            ProposalRef(kind="web_search", ref=result.url or result.title, note=result.snippet[:200])
            for result in web_results
        )
        return refs


def _parse_discussion_response(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        cleaned = cleaned.removesuffix("```").strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ContractError("Agent discussion response must be JSON") from exc
    if not isinstance(payload, dict):
        raise ContractError("Agent discussion response must be a JSON object")
    return payload


def _discussion_markdown(
    *,
    instruction: str,
    reply: str,
    selected_text: str = "",
    replacement_text: str = "",
    warning: str = "",
) -> str:
    sections = [
        "# Agent 讨论记录",
        "",
        "## 作者问题",
        instruction,
        "",
        "## Agent 回复",
        reply,
    ]
    if selected_text:
        sections.extend(["", "## 标注片段", selected_text])
    if replacement_text:
        sections.extend(["", "## 建议替换", replacement_text])
    if warning:
        sections.extend(["", "## 注意", warning])
    return "\n".join(sections).strip()


def _replace_unique(base_text: str, selected_text: str, replacement_text: str) -> str | None:
    if not selected_text:
        return None
    first = base_text.find(selected_text)
    if first < 0:
        return None
    second = base_text.find(selected_text, first + len(selected_text))
    if second >= 0:
        return None
    return base_text[:first] + replacement_text + base_text[first + len(selected_text) :]


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = _optional_str(payload.get(key))
    if not value:
        raise ContractError(f"Agent discussion response requires {key}.")
    return value


def _optional_str(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        return str(value).strip()
    return value.strip()


def _clip(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _flatten_related_topics(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    topics: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        nested = item.get("Topics")
        if isinstance(nested, list):
            topics.extend(_flatten_related_topics(nested))
        else:
            topics.append(item)
    return topics
