"""Session-bound MCP JSON-RPC transport; no sockets, remote tools or credentials.

The provider-neutral command envelope is a client adapter. Every command crosses
serialized JSON-RPC before a validated dispatcher executes it.
"""
import json

from storygraph.core.errors import ContractError
from storygraph.models.authoring import AuthoringToolAction, authoring_tool_schema
from storygraph.services.authoring_collaboration import allowed_authoring_tools, validate_authoring_mode_tool
from storygraph.skills import SKILLS, SKILL_DESCRIPTIONS


_TOOL_HELP = {
    "discover_capabilities": "List tools allowed in this collaboration mode and available writing methods.",
    "read_skill": "Load one packaged writing method for the Main Agent.",
    "inspect_project": "Find chapters and scenes by title or ID in the current project outline.",
    "inspect_reviews": "Inspect existing proposal statuses and available evidence from scoped review reports.",
    "open_workflow": "Offer a clickable destination for the author to open in the workbench.",
    "inspect_sources": "List explicitly selected references and their exact versions.",
    "read_source": "Read one bounded page from an authorized source, outline or saved Draft.",
    "search_source": "Find a literal passage in a selected reference.",
    "search_draft_quotes": "Resolve exact quotations during a saved-Draft reconciliation.",
    "inspect_canon": "Query this project's established graph facts with provenance.",
    "inspect_workspace": "Look up adopted design items, scene cards and character plans in this session.",
    "search_history": "Retrieve earlier conversation and proposal records from this session.",
    "inspect_proposal": "Read the operations of an exact design proposal before reviewing or revising it.",
    "character_view": "Retrieve an individual character's authorized perspective.",
    "simulate_character": "Ask an isolated model request for that character's possible actions.",
    "impact_analysis": "Trace which scene designs and saved drafts depend on a proposed change.",
    "propose_workspace": "Submit a pending design proposal for author review.",
    "revise_proposal": "Revise a pending proposal while preserving its untouched design.",
    "propose_draft_evidence": "Propose reader or character knowledge backed by exact saved quotations.",
    "propose_design_changes": "Propose specific field edits to existing design items, cards or character plans.",
    "propose_card_review": "Present snapshots of existing scene cards for explicit author review.",
    "finish": "Reply to the author or ask a question and finish this turn.",
}

def _input_schema(arguments, definitions):
    needed = {}
    def collect(value):
        if isinstance(value, dict):
            ref = value.get("$ref", "")
            if ref.startswith("#/$defs/"):
                key = ref.removeprefix("#/$defs/")
                if key not in needed:
                    needed[key] = definitions[key]
                    collect(definitions[key])
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
    collect(arguments)
    return {**arguments, **({"$defs": needed} if needed else {})}


class AuthoringMCPServer:
    """One turn owns one server and dispatcher closure. Not an HTTP endpoint."""

    def __init__(self, *, dispatch, validate_context, mode="collaborate"):
        self.dispatch, self.validate_context, self.mode = dispatch, validate_context, mode
        self.initialized = False
        self.ready = False
        self.failures = {}

    def request(self, wire: str) -> str:
        try:
            request = json.loads(wire)
        except (ValueError, TypeError):
            return json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
        identity = request.get("id") if isinstance(request, dict) else None
        try:
            return self._request(request)
        except Exception as exc:
            # The local client preserves typed failures for existing budget/retry policy.
            # A wire consumer receives only stable diagnostics, never private values.
            if isinstance(identity, (str, int)) and not isinstance(identity, bool):
                self.failures[identity] = exc
            code = {"authoring_mcp_method_not_found": -32601, "authoring_mcp_invalid_request": -32600}.get(str(exc), -32602)
            if isinstance(request, dict) and "id" not in request:
                return ""
            return json.dumps({"jsonrpc": "2.0", "id": identity, "error": {"code": code, "message": "Request rejected"}})

    def _request(self, request):
        if (not isinstance(request, dict) or request.get("jsonrpc") != "2.0"
                or set(request) - {"jsonrpc", "id", "method", "params"}
                or not isinstance(request.get("method"), str)
                or ("id" in request and (not isinstance(request["id"], (str, int)) or isinstance(request["id"], bool)))):
            raise ContractError("authoring_mcp_invalid_request")
        method, params = request.get("method"), request.get("params", {})
        if not isinstance(params, dict):
            raise ContractError("authoring_mcp_invalid_params")
        self.validate_context()
        if method == "initialize":
            if params.get("protocolVersion") not in {"2024-11-05", "2025-03-26", "2025-06-18"}:
                raise ContractError("authoring_mcp_protocol_unsupported")
            self.initialized = True
            result = {"protocolVersion": params["protocolVersion"], "capabilities": {"tools": {}, "resources": {}},
                      "serverInfo": {"name": "storygraph-authoring", "version": "1"}}
        elif not self.initialized:
            raise ContractError("authoring_mcp_initialize_required")
        elif method == "notifications/initialized":
            if "id" in request or params:
                raise ContractError("authoring_mcp_invalid_request")
            self.ready = True
            return ""
        elif not self.ready:
            raise ContractError("authoring_mcp_initialized_notification_required")
        elif method == "tools/list":
            if params:
                raise ContractError("authoring_mcp_invalid_params")
            schema = authoring_tool_schema()
            result = {"tools": [{"name": v["properties"]["tool"]["const"],
                "description": _TOOL_HELP[v["properties"]["tool"]["const"]],
                "inputSchema": _input_schema(v["properties"]["args"], schema["$defs"])}
                for v in schema["oneOf"] if v["properties"]["tool"]["const"] in allowed_authoring_tools(self.mode)]}
        elif method == "resources/list":
            if params:
                raise ContractError("authoring_mcp_invalid_params")
            result = {"resources": [{"uri": "storygraph://skills/" + key, "name": key,
                                      "mimeType": "text/markdown", "description": SKILL_DESCRIPTIONS[key]} for key in SKILLS]}
        elif method == "resources/read":
            if set(params) != {"uri"} or not isinstance(params["uri"], str):
                raise ContractError("authoring_mcp_invalid_params")
            uri = params.get("uri", "")
            key = uri.removeprefix("storygraph://skills/")
            if uri != "storygraph://skills/" + key or key not in SKILLS:
                raise ContractError("authoring_skill_not_found")
            result = {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": SKILLS[key]}]}
        elif method == "tools/call":
            if set(params) != {"name", "arguments"}:
                raise ContractError("authoring_mcp_invalid_params")
            action = AuthoringToolAction.model_validate({"tool": params["name"], "args": params["arguments"]})
            validate_authoring_mode_tool(self.mode, action.tool)
            output = self.dispatch(action)
            result = {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}],
                      "structuredContent": output, "isError": False}
        else:
            raise ContractError("authoring_mcp_method_not_found")
        return json.dumps({"jsonrpc": "2.0", "id": request.get("id"), "result": result}, ensure_ascii=False)


class AuthoringMCPClient:
    def __init__(self, server):
        self.server, self.sequence = server, 0

    def call(self, method, params=None):
        self.sequence += 1
        response = self.server.request(json.dumps({"jsonrpc": "2.0", "id": self.sequence,
                                                 "method": method, "params": params or {}}))
        if not response:
            return None
        decoded = json.loads(response)
        if "error" in decoded:
            raise self.server.failures.pop(self.sequence, ContractError("authoring_mcp_request_failed"))
        return decoded["result"]

    def initialize(self):
        self.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                 "clientInfo": {"name": "storygraph-main-agent", "version": "1"}})
        self.server.request(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def execute(self, action):
        return self.call("tools/call", {"name": action.tool, "arguments": action.args})["structuredContent"]
