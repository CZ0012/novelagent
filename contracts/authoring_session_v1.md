# Authoring Session Contract v1

`authoring_session_v1` adds a persistent, project-scoped author/Main Agent
conversation and versioned **noncanon design workspace**. It is usable with only
an existing Project and an idea; a full-book plan, complete cast, decided true
cause and canonical Scene are not prerequisites. Existing graph, plan, review,
Draft, language and writer-visibility contracts remain unchanged.

## Authority and storage

The domain schema is `storygraph/models/authoring.py`. Sessions persist locally
in the Proposal workspace database, isolated by project. `id`, `project_id`,
positive monotonic `version`, frozen `content_language`, `title`, exact input
pins, messages, workspace, proposals and timestamps are stored. Each successful
mutation compares `expected_version`; stale writes return conflict without
partial mutation. A turn is CAS-claimed before provider calls using turn_status running and a
unique turn_id; concurrent turns cannot both spend against the same snapshot.
Only that turn can finalize. `turn_calls_started` (0–8) and `turn_max_steps`
(1–8, default 6) persist the actual shared dispatch budget. Increment/persist
before each Main or child socket dispatch, including failed/unknown outcomes;
no successful-tool-trace count can substitute for calls started. Failed/unknown state and sanitized turn_error_category
preserve the failure without silently retrying an uncertain paid call.
Provider calls cannot hold a transaction: persist their result
only if the session version and input pins still match. Conflicting results
must never overwrite a newer conversation or adopted design. Runtime prose and
source text do not belong in coordination Markdown, logs, Git or checkpoints.

These records do not become Graph canon, Drafts, CandidateFacts, PLAN approval,
character knowledge or reader knowledge. `author_decided` means an author design
decision, not a canon status. All existing explicit human-review gates still
apply. No new Graph labels, review statuses or old contract fields are added.

## Explicit inputs

`source_pins` select only existing ready Source Documents or exact outline
Proposal versions. A pin contains `kind: source_document|outline`, stable `id`,
SHA-256 and, for an outline, required exact positive `version`. Source Document
hashes cover the selected extracted text; outline hashes cover exact body text.
Sources are resolved server-side within the session project, never by arbitrary
path or URL. Source Document archiving, deletion, selected text changes or
language ineligibility block use rather than substituting newer text. An exact
immutable outline version remains valid when a newer version is created; only
an explicit rebind changes the selected outline reference.

`draft_pins` contain `scene_id`, `draft_id`, exact `version`, whole-text
`text_sha256`. Resolve the exact saved historical Draft, including an explicitly
selected discarded version; never substitute latest. Every pin is project/scene
scoped. Existing `language_policy_v1` selection and cross-language rules apply;
unknown-language sources cannot enter a model. Creating a session or selecting
inputs makes no provider call. `content_language` is server-derived from Project
language, never a model override; future calls reject a stale language binding.

## Workspace

`items` distinguish `world_fact`, `true_cause`, `character_belief`,
`character_claim` and `open_question`. Each has stable ID, `status:
open|alternative|author_decided`, text, optional alternative group, rationale,
dependencies and optional evidence. Beliefs and claims require an owning
`character_id`; `about_character_id` can describe that character's belief about
another's knowledge. Neither claims nor beliefs prove objective truth. An open
question cannot carry author-decided status. An unknown true cause can remain
open with competing alternatives indefinitely; the agent must not invent a
resolution merely to complete a form.
An author_decided fact remains decided when withheld from readers/POV. Do not
relabel it as unresolved in the full author_summary; author truth status and
Writer disclosure are separate axes.

`character_plans` record each character's goal, subjective belief item refs,
knowledge assumptions and intended actions. `knowledge_assumptions` remain
subjective possibilities, including beliefs about who knows what. Actions name
the actor and dependencies. Intentions are not realized events.

`scene_cards` have stable ID/version, title, optional existing `scene_id`,
`proposed|approved` status, optional POV, entry knowledge, intended actions,
intended acquisitions, outcome, dependencies, an explicit existing
`WriterVisibilityPolicy`, and author-only `withheld` information. Acquisition is
not entry knowledge; intended outcome is not a realized fact. Character-local
IDs may be used before graph structure exists; they must not masquerade as
canonical Character IDs at compilation. The positive Writer policy carries
approved public names/claims, disclosure phase, style and intended reader
inference. Private truth, withheld material, alternatives and conversation are
never automatically appended to Writer input.
All design references resolve within the final workspace produced by the patch:
`belief_item_ids` and knowledge `item_id` require item IDs; every `depends_on`
requires an item or card ID. Removing a referenced object or inventing a reference
that exists only in another pending proposal fails closed. Pending proposals do
not populate the adopted workspace.
Canonical Scene IDs are not design dependency IDs: bind canonical Scenes only
through scene_id, and use final workspace item/card IDs in depends_on.
Style bans, rubrics and negative instructions are Writer input too: they must
not reveal a withheld name, hiding place or true cause by naming it in a ban.
Use the positive allowed surface and generic limits instead.

`reader_records` use existing `ReaderPresented` exact saved-Draft bindings.
They record text actually presented, not an objective conclusion or automatic
Writer editing permission. Reader inference stays explicitly intended/uncertain.
IDs are unique within item/card collections and character plans have unique
owners. Bounds are explicit: 200 items, 200 cards, 80 character plans, 2000
reader records, 40 combined Source/outline pins and 2000 Draft pins. Session
responses show 40 recent messages plus all pending and 20 recent closed
proposals with typed total/more metadata; omitted history remains retrievable
from the normalized durable journal. Domain hydration bounds are 20000 messages
and 5000 proposals; they do not cap the total durable journal as turns append
through bounded views. Overflow fails visibly without silently dropping records.

## Bounded Main Agent loop

The Main Agent is an LLM making creative judgments using project framework
tools. It is not a hardcoded plot simulator or a form auto-fill sequence. Each
explicit author turn runs a bounded, visible provider-neutral tool loop. Actions
use strict `AuthoringToolAction` with `tool` and `args`:

- `inspect_sources`: query/offset/limit pages of selected input metadata.
- `inspect_workspace` and `search_history`: bounded query/offset/limit over stored design
  and persistent conversation, allowing earlier decisions to be retrieved without
  dropping or automatically retransmitting the complete conversation.
- `inspect_proposal`: exact scoped proposal ID plus offset/limit pages of its
  operations, including historical proposals outside the session response window.
- `read_source`: resolve only an exact selected source/Draft pin. Optional
  UTF-16 start/end must appear together and span 1–20000 units; offset_unit is
  utf16. Verify the full pinned source hash before returning that exact range,
  with offsets/full length. Omission returns the first page of at most 12000
  UTF-16 units with explicit start/end/total/more/next_start/complete metadata;
  it must not claim that this first page is the whole large source. Invalid
  boundaries, including surrogate splits, fail before exposing text.
- `search_source`: literal query within an exact pin with offset/limit hit
  pages, full-match UTF-16 coordinates, bounded context and explicit totals/more.
- `search_draft_quotes`: only during active exact-Draft/card reconciliation and
  after the target Draft has been read, resolve 1–12 literal quotation strings
  locally (each at most 1000 characters, at most 4000 combined). Return each
  quote_index with exact matched text/UTF-16 positions and this-turn quote_refs,
  total_matches/returned_count/more/ambiguous. Return at most 4 matches per quote,
  24 matches total and 6000 matched characters; extra matches remain explicitly
  marked more. Repeated occurrences are alternatives, not automatic selections.
  Single-source search remains available for later matches.
- `inspect_canon`: bounded same-project read, not mutation.
- `character_view`: construct a character-specific view from their entry
  knowledge, owned subjective beliefs/claims, goal and actions. Do not include
  omniscient truth or other characters' private beliefs by default.
- `simulate_character`: make a genuinely separate new model call with only the
  selected character's restricted view, own goal/beliefs, and bounded question.
  Strict arguments are character_id, optional card_id, and question_kind:
  next_action|conflict_response|disclosure_choice. The server supplies the preset
  question; arbitrary Main-authored question text cannot enter the child. Its result is `AuthoringCharacterSimulation`: 1–6 action/
  rationale options and at most 20 uncertainties, all noncanon suggestions.
- `impact_analysis`: compute dependencies of proposed changes.
- `propose_workspace`: emit a typed bounded design patch for review. For an
  existing ID, recursively merge only actually provided fields with the current
  workspace object; explicit arrays replace and explicit empty/null values are
  edits subject to final type validation. New IDs use complete model validation
  and defaults; removals stay explicit. Required tool schema fields still apply.
  Omitted fields cannot clear existing author plans, metadata or Draft evidence.
- `propose_design_changes`: preferred for small edits to existing adopted
  records. Args are summary and 1–20 distinct changes, each with target_type
  (item|character_plan|scene_card), exact current-workspace target_id and a
  nonempty fields dictionary. No creation/removal or pending-only target lookup.
  Check top-level names against the selected domain model; reject unknown fields
  and identities. Character plan character_id is protected; Scene card id,
  status, version and scene_id binding are protected. Recursively merge fields
  into the complete existing object (explicit arrays replace), validate that
  entire object through the existing domain schema, then generate a full typed
  AuthoringPatch and call ordinary proposal validation. Card status is set to
  server-proposed and versions remain server-managed. Model output need not
  repeat title, policy core or unrelated fields to edit one field. Nested extra
  keys, invalid types and broken dependencies still fail final validation. This
  tool is forbidden in reconcile mode, which retains its evidence-only chain.
  Persist only a compact proposal reference trace, not another copy of fields.
- `propose_card_review`: request human reapproval without editing content. Args
  are summary and 1–20 unique existing current-workspace card_ids. The framework
  copies each complete current card, sets server-proposed status and normalizes
  its version through existing proposal rules, then stores a full pending patch.
  No creative field is changed or retyped by the model. Only explicit author
  adoption approves the selected cards; no new HTTP form or direct status write
  is introduced. Unknown/foreign/duplicate targets and reconcile-mode use fail.
- `revise_proposal`: require an exact scoped pending proposal_id, summary and
  incremental patch. Recheck its base workspace, input pins, canon and language;
  apply the original patch to a virtual current workspace, apply the increment,
  then calculate a new full bounded patch relative to the real current workspace.
  For an upsert ID already in that virtual workspace, merge only fields actually
  present in the incremental model command: omitted values survive, dictionaries
  merge recursively, and explicit lists replace. Explicit empty/null values are
  edits and must satisfy full final-model validation. Tool argument normalization
  preserves nested field presence; defaults must not erase omitted author plans,
  POV, knowledge, actions, style or disclosure. Required argument schema fields
  remain required. A new ID uses complete object validation/defaults, and
  propose_workspace uses the same actual-field merge for existing IDs.
  Preserve all unchanged original proposal content and record server-filled
  optional supersedes_proposal_id on the new pending proposal. Neither the old
  proposal nor the adopted workspace changes. Reconciliation restrictions apply
  to the final composed patch and cannot be bypassed through this tool.
- `propose_draft_evidence`: the preferred narrow reconciliation proposal tool.
  Args are summary; acquisitions containing character_id, text, nonempty
  quote_refs and optional item_id; and reader_records containing quote_ref and
  presentation. Omitted/empty lists append nothing and preserve all existing
  records; an operation with no new evidence is rejected. It requires the active
  exact Draft/card binding and a verified current read of that Draft. The framework
  fills exact AuthoringEvidence/Draft pins and ReaderPresented from quote_refs,
  copies the complete selected card and changes only acquisitions plus server
  proposed status/version. Acquisition owners must belong to that card. The
  generated pending patch passes existing only-evidence and proposal validation;
  it does not change workspace, Draft, canon or Writer input without adoption.
- `finish`: deliver the conversational creative response.

The service validates each tool's exact arguments and output bounds. Strict typed
argument models reject unknown fields: read uses kind/id with optional exact
range, journal/workspace/source-index queries use query/offset/limit,
character view uses character_id/card_id, impact uses item_ids/card_ids, proposal
uses patch/summary, and finish uses message. An empty-argument tool accepts no
extra fields. A turn may ask a question and finish with no proposal. Tool/model
output cannot accept its own proposal, approve cards, write canon or invoke
prose generation. `character_view` remains a zero-provider-call read. `simulate_character` must
use an independent request: no Main Agent chat/history/tool transcript, author
truth, unresolved true-cause alternatives, source dossier or other characters'
private state may enter it. The strict preset question prevents Main-authored question text from becoming
a side channel for omniscient facts. Role-view projection must also omit author
rationales, evidence, dependency labels, and truth classifications that could
leak withheld knowledge. The Main Agent must not label its own omniscient
reasoning or a returned view as an isolated character simulation. Both the Main
Agent request and every simulation request consume the same explicit turn
max_steps/actual-call budget and normal financial guards. Reserve/check remaining
capacity before the child call; insufficient capacity returns a visible budget
result with no hidden extra call. No simulation output directly changes the
workspace, approval, knowledge, visibility or canon. Writer calls use only the existing positive approved policy and explicit
prose grants. Raw conversation belongs only to the Main Agent context.

Quote-reference registries exist only as local variables of one running turn,
not service attributes or shared caches. In a reconcile turn, exact-target Draft
search matches receive short quote_refs bound to project/session/turn, full
Draft pin and actual matched text/start/end. No caller-supplied, previous-turn,
foreign-Draft or stale reference can supply evidence. Revalidate full Draft
hash/span, selected card version and ordinary CAS/canon/source gates before
proposal persistence. Before the first reconcile provider call, the framework
validates the exact selected Draft/card and current CAS/source/canon/language,
reads the current default UTF-16 page, revalidates and saves a real read_source
trace with initiated_by=framework and model_execution=null. This local read
costs no provider call. Initial Main context reconciliation_read includes that
exact pin/hash/text/range and explicit more/next_start/complete metadata; a large
Draft is not silently presented as fully read. Only that target satisfies the
turn's read gate; other pins, historic text and fabricated read claims do not.
Further pages remain available through read_source. Quote search/evidence
assembly also makes no provider call; framework read → batch quotation search →
evidence proposal → finish normally needs three Main calls within the unchanged
original allowance. Main selects literal text
and returned references, never computes offsets or retypes an entire card.
Existing propose/revise reconciliation restrictions remain unchanged.

Use existing saved provider/role settings, financial guards and measured call
accounting. One narrow authoring-turn format correction is allowed: after an
already completed local JSON/schema error, or ProviderError invalid_response,
incomplete_response or unsupported_output with outcome_known=true, retain safe
diagnostics and allow Main one further format-correction request within the
original max_steps allowance. This is shared once across Main and character
calls. The only additional output-contract categories eligible for this same
single correction are authoring_patch_dangling_reference and authoring_empty_patch, emitted before
applying a bad design patch. Its diagnostic is a fixed code/hint explaining
workspace dependency IDs versus canonical scene_id, never the offending values.
The empty-patch hint directs discussion to finish and unchanged-card reapproval
to propose_card_review; a summary is not an approval target or a state change.
The framework does not replace or guess a reference. Other ContractError types,
including project scope, source/canon changes, permission and CAS conflicts,
remain immediate hard stops. This does not add a second correction allowance.
A failed child returns control to Main; its raw output
is never repaired or copied into Main history. Every dispatch still increments
the same persistent call count and rechecks session/source/canon/language and
permissions. Preserve successful proposals and role results without replaying
their tools. If no calls remain or the correction also fails, keep failed state.
Unknown outcomes, network/connection, authentication, rate limits and scope/CAS
failures stop immediately without correction. No model/protocol substitution,
credential change, budget increase or retry authority for other workflows is
implied. Malformed results are never fabricated successful decisions. Persist concise tool evidence,
not hidden reasoning, credentials, transport errors or private prompt dumps.

## Proposed diff and explicit adoption

Every model-proposed design revision is pending. `AuthoringProposal` carries
its stable ID, exact `base_workspace_sha256`, typed bounded `patch`,
summary, affected card/scene IDs, evidence, status and review audit fields. The
service computes the actual before/after diff and transitive dependency impact;
model impact claims cannot omit affected dependents. Changes to upstream design
invalidate dependent approved cards until the author explicitly reviews them.
Author feedback creates a new proposal, never a silent application.

`AuthoringPatch` contains bounded upsert_items/upsert_character_plans/
upsert_scene_cards, explicit remove_item_ids/remove_character_ids/remove_card_ids
and exact add_reader_records/remove_reader_records. Duplicate identities and
upsert/remove conflicts fail validation; the same exact reader record cannot be
added and removed in one patch. Sequential revision operations compose through
their virtual workspaces, so an original addition removed by the increment or
an original removal restored by it cancels in the final relative patch.
New proposal generation rejects an entirely empty resulting AuthoringPatch
before persistence, including complete cancellation of a pending revision.
Use finish for discussion or propose_card_review for explicit unchanged targets.
Existing empty historical records remain readable/rejectable and retain their
original stored content; no migration or retroactive reinterpretation occurs.
A complete workspace is a read snapshot,
not a required model-output replacement. Server verifies resulting bounds,
references, stable versions and all dependency changes, and expands each newly
generated pending patch to complete final objects before
persistence. Previously stored patches retain their exact full-patch meaning;
review applies them without reinterpreting omissions or migrating old records.
For an existing approved card edited without an explicit status, the server
sets the new proposed card to proposed. Explicit model-supplied approved status
is rejected, and card versions remain server-managed. The model-facing tool
schema advertises only proposed status; domain/session records still represent
both proposed and human-approved cards.

Explicit adoption validates session CAS, exact base workspace hash and source
freshness, then atomically applies the patch, preserves untouched objects/IDs, records reviewer/time and
marks that proposal `adopted`. Only this human action can approve its reviewed
cards/design decisions. Reject marks `rejected` without applying design. Pending
proposals with older baselines cannot be rebased or applied automatically.

## Scene handoff and writing

An approved card bound to an existing reviewed same-project Scene can compile
its **positive** `writer_policy` into the existing visibility store only through
an explicit author action with session/card version, current author Context Pack
source hash and visibility expected-version CAS. Validate current Scene/cast,
all reader sources, policy/style binding and existing `must_include` constraints.
Preview is the existing actual Writer-message preview and makes no model call.
A changed source/card/dependency blocks handoff; no fallback to unisolated input.

An unbound card offers explicit minimal structure review (defined below) or the
existing reviewed project-structure proposal route. It cannot silently create
graph nodes, claim structure approval or require a 100-chapter plan. Writing remains a separate explicit existing workflow using
the exact saved Drafts, approved current visibility and prose input grants.
Compiling a card does not start writing, mutate a Scene or approve a Draft.

## Exact Draft reconciliation

After prose is saved, an explicit reconciliation pins the actual exact Draft
and card. Proposed realized changes and reader updates must cite
`AuthoringEvidence`: whole-text Draft pin plus nonempty UTF-16 `[start,end)` and
exact expected text. Server verifies project/scene ownership, version, hash and
span before storing a pending proposal. Quotes are evidence of text, not proof
that a character's statement is true. Intended but absent actions, ambiguous
causes and unsupported reader inference remain unresolved. Reconciliation
neither edits prose nor promotes canon; adoption changes only design/reader
records. Canon extraction still uses real Draft -> pending CandidateFact ->
ReviewService, with unchanged provenance and human approval requirements.

## API ownership

The API surface consists of project-scoped session list/create/detail, bounded
turn, explicit proposal decision, approved-card compilation, and exact-Draft
reconciliation. All reads require existing read permission; model calls and
noncanon writes require generation permission. Requests include session
`expected_version` on mutation. The API owns input resolution, financial guards,
authority, CAS and exact dependency checks; the client owns only temporary
unsaved edits/diff presentation. No client-supplied hash or approval bypasses
server verification. Missing/foreign IDs fail closed without content leakage.

## Explicit minimal structure review

An approved unbound card can be previewed and explicitly reviewed into a single
Chapter and planned Scene. This does not require a complete world, a full-book
outline, or resolution of unknown true causes. `preview_structure` is read-only
and returns `source_sha256`, `card_version`, `scene_id`, `chapter_id`, `nodes`,
`relationships`, `character_mapping`, and `gaps`. Node specs contain id/type/
properties; relation specs also contain source_id/target_id. The hash binds the
exact card and complete scoped graph snapshot. Missing chapter title, location,
timeline position, goal, conflict, emotional turn, intended outcome, POV or POV
public identity appear as gaps and block application rather than being invented.

Only explicit `apply_structure` with exact session/card versions, source hash,
reviewer and rationale can create the displayed minimal Characters (public names
only), Location, Chapter, planned Scene, HAS_CHAPTER and HAS_SCENE. Scene fields
include approved plan/style/target length.
The displayed Scene properties also include `require_semantic_review: true`;
confirming structure explicitly approves this writing protection for this new
Scene. It does not change Project settings, other Scenes or story truths.
No design truth, hypothetical cause,
character knowledge, realized action, NEXT_SCENE chronology or full-world facts
are promoted by this operation. Preview, conversation and proposal adoption do
not apply graph structure. The existing project-structure proposal route remains
available as an alternative for larger plans.

Existing Characters are reused only by their exact same-project canonical ID;
local identities map to deterministic project/session graph IDs across cards.
Ambiguous duplicate public names fail closed. Reviewed identity mappings and
application receipts live in a separate authoring SQLite table, not arbitrary
Graph ID metadata. The original local workspace IDs remain intact. Policy
compilation resolves only exact canonical IDs or reviewed mappings.

Local graph application stages, durably persists and then publishes the graph
before saving the bound card with a version increment. This is not a distributed
atomic transaction. A prewritten intent and exact provenance creation events
allow a failed session save to recover without repeating graph writes. Incomplete
or mismatched evidence fails closed. Completed retries return the same IDs and
preserve subsequent author edits. Canon writes retain source_ref, reviewer,
rationale and event evidence. Writing/visibility approval remains a separate
explicit author action after structure review.

### In-flight project and canon freshness

Project language is re-resolved even when the session has no selected Sources or
Drafts. A changed language blocks provider-result persistence and proposal
adoption. Each new turn captures the current project-scoped canon fingerprint;
the exact fingerprint is checked before and after every main/character provider
call and before result persistence, alongside the session version and source
pins. A later turn may capture a newly reviewed canon state; the session does not
permanently lock the graph to its creation state.

Generated proposals carry server-filled optional `canon_sha256`. Adoption must
match its frozen fingerprint to current canon and must not silently refresh that
fingerprint. Legacy absent values cannot certify a proposal against an available
canon resolver. These checks are freshness guards, not canon write authority.

Saved-Draft reconciliation binds the exact saved Draft and, for character
acquisition proposals, one explicit `card_id` plus `card_version` whose bound
Scene matches the Draft. Only this card may receive evidence-backed acquisitions;
another card in the same Scene is not interchangeable. Without a card binding,
the service may propose reader records only. The API requires the card binding.

Generated assistant/tool messages and proposals may carry the server-filled
`model_execution` snapshot from `agent_runtime_v1` (profile ID/name, protocol,
model, task, thinking mode/effort only). The snapshot is copied at service
construction and on artifact creation; later settings changes cannot relabel
saved output. It contains no credential or provider address. Author messages do
not receive an inferred model snapshot. Execution metadata stays outside message
content and is excluded from searchable history tool payloads, role simulation,
and Writer input. Fake/legacy records may omit it.

### Durable collaboration journal and bounded retrieval

SQLite stores messages, versioned proposals and workspace snapshots as immutable
content-addressed blobs; session versions retain their references. Identical
workspace snapshots and unchanged historical records are reused across tool
checkpoints. Legacy inline session records remain readable and normalize on the
next save. Saving a bounded view merges by stable record ID and cannot delete
the omitted journal. Historical message content is immutable; proposal review
creates a new version while older session references retain the prior version.

Session detail returns the latest 40 messages in chronological order, all pending
proposals, and the latest 20 closed proposals. Typed `history_counts` and
`history_has_more` each expose exactly `messages` and `proposals`. These windows
are presentation limits, not deletion or automatic summarization. Scoped history
pages expose `records`, `total_matches`, `returned_count`, `offset`, `more`,
`next_offset`, and explicit `order=newest_first`. Exact old proposal detail is
project-and-session scoped. Draft pins and reader records support up to 2000
each; patches retain their smaller operation bounds.

Main initial context includes only ten recent Source/Draft pins with explicit
totals/more flags. `inspect_sources` pages the selected pin metadata;
`inspect_workspace` pages items, character plans, scene cards and reader records.
Both enforce query/offset/limit and return explicit total/returned/more metadata.
`search_history` searches the complete journal rather than the visible window.
`inspect_proposal` retrieves a scoped historical or pending proposal by ID and
pages its patch operations. Execution metadata is excluded from model-facing
history/proposal inspection. Role simulation and Writer input do not gain access
to the journal, pins or reader records from these retrieval additions.

The propose-tool checkpoint stores the full typed proposal once and returns its
ID, summary, affected IDs and impact counts; it does not duplicate the large
patch/diff in the persisted tool trace. Detailed operations remain retrievable.

Each new proposal also freezes server-filled `inputs_sha256` over the exact
ordered Source/Draft pin snapshots. Adoption must match this hash in addition to
workspace, canon, language and live-source freshness checks. Explicitly rebinding
selected inputs does not recertify old proposals or erase earlier conversation;
old source quotations remain historical records, not current source authority.

Source selection is limited to 40 distinct references in total across Source
documents and outline proposals (duplicates collapse within each kind). Create
and source-rebind request validation rejects a larger combined selection before
source lookup, session mutation or any provider call. Draft pins retain their
separate journal capacity. An explicitly selected immutable outline version
remains readable after a newer outline revision exists; rebind is an explicit
author choice and must not silently replace that historical reference.

Adopting an explicit unchanged-card upsert is still a review decision and may
restore that card's approval after source rebinding. Only the submitted cards
can be approved this way; other affected or untouched proposed cards do not gain
approval. Journal save responses bind the exact version committed by that
operation, even when another request commits a later version immediately after.

Invalid model output may add a local `format_diagnostic` tool message containing
safe JSON line/column coordinates, known-schema validation paths and static
whitelisted codes/hints for the existing subjective-owner/open-question status
validators and the known dangling-reference/empty-patch output guards. Owner
codes are `subjective_item_requires_character_id` and
`open_question_cannot_be_author_decided`; arbitrary error messages are never
echoed. The advertised item/tool schema expresses both rules conditionally:
belief/claim items require a nonnull owning character_id, and an open question
cannot be author_decided. Runtime acceptance remains unchanged. Unknown
field names are masked; raw malformed output, values and arbitrary keys are not
retained. The invalid command is not executed, no proposal is adopted, and turn
status/call count reflect the actual bounded turn outcome. This diagnostic uses
the same session/pin/canon CAS freshness checks as other result persistence. A
safe format_correction trace marks the single within-turn correction opportunity
and its remaining original call allowance. Diagnostics may enter Main for that
correction or a later explicit author turn, never isolated role/Writer input.
They do not authorize any retry of an uncertain or non-format provider failure.

### Explicit bound Scene plan revisions

The same structure preview/apply route supports an approved card already bound
to a same-project Scene. Preview now includes `operation` (`create` or `update`),
`current_scene` (the full current node, null for creation), and `changes` entries
with `field`, `before`, and `after`. For updates `nodes` contains only that Scene
and its displayed partial plan properties; `relationships` is empty.

Explicit update review applies only nonempty card title, timeline, goal, conflict,
intended outcome and emotional turn, plus target length,
POV/cast/location mappings and the Scene semantic-review requirement. It leaves
Scene summary unchanged unless the card supplies a nonempty explicit
`author_summary`: a filtered surface disclosure plan is not the complete author
summary. Creation prefers nonempty `author_summary`, retaining its legacy literal
surface fallback when absent. Updates never use that fallback. This complete
author plan is not copied into the positive writer policy or its surface plan.
Chapter membership, other Scenes, world truths, realized events,
knowledge and chronology remain untouched. A chapter-title edit is not applied
through this Scene-only update route.

Actors must use exact same-project canonical IDs or the deterministic local IDs
from the session's original reviewed Character creation. Location must be its
exact canonical ID or the unchanged current Location public name. Missing/new
identity mappings produce explicit gaps; names never implicitly identify a
newly selected existing actor/location. Additional identities require a separate
explicitly reviewed structure proposal before this plan update can proceed.

Creation also accepts an explicit same-project canonical Location ID for reuse;
an existing same-name Location requires explicit ID selection. Preview `reuse`
entries expose reused id/type/name and Character public_name when applicable.
Exact canonical Character identity or the session's reviewed local mapping can
carry a policy public-name alias without renaming its canonical node.

Scene-plan updates preserve all existing canonical style constraints. Visibility
style capsules are disclosure/voice permissions, not authority to replace canon
style. A new Scene using profile_projection inherits the complete project style
without an override from the projected subset. A new author_literal Scene only
sets explicitly nonempty style fields. Changing canonical style requires a
separate formal review mechanism outside this bridge.

An update validates session/card CAS and exact scoped graph/card source hash,
stages and persists the graph with reviewed update provenance, and records a
separate version/hash-bound update receipt. Original creation receipts are
retained. Since this operation changes only canon plan properties, it does not
rewrite or increment the already-approved design session/card. Exact update
event evidence repairs a failed receipt write without repeating the graph
update; completed retries preserve later author graph edits. It is not an atomic
transaction across graph persistence and SQLite. Preview and conversation still
perform no canon writes, and the updated plan requires separate visibility
compilation before prose generation.

## Main Agent workbench and internal MCP

The persistent lower conversation is scoped to an API connection and Project.
Opening a chapter or scene changes turn focus. The workbench may create a local
Project and Session from the author's first idea, then start one explicit turn
using the configured discussion provider. Its failure state and saved idea
remain available through the existing journal.

Ordinary turn requests accept optional `navigation_context` with Project-scoped
`chapter_id` and/or `scene_id`, and `collaboration_mode` with default
`collaborate`. In `discuss` and `review` the tool registry and dispatcher permit
read-only creative operations, simulation and workflow links. A proposal tool
issued in either mode must be rejected before it can store a pending proposal.
The dialogue and tool journal still record the turn.

An author can grant one turn a saved passage with `selected_passage` containing
`draft_id`, positive `version`, `text_sha256`, and half-open UTF-16 `start` and
`end` offsets (1–8000 code units). The scene must match the validated navigation
context, and the version, content hash, language and span must match the saved
Draft. Only that span is attached to Main's request. This creates no persistent
whole-Draft pin and grants no input to a character or Writer. Explicit full
Draft binding and exact-Draft evidence reconciliation remain separate operations.

The Main runtime owns a turn-local MCP server and client. Initialization, tool
discovery/calls and resource listing/reads run inside the backend process.
The existing strict provider command envelope remains the adapter. Tools are
bound to the server-side session, Project, permission, active mode, source pins
and version checks. The client discovers the built-in skills and loads the
author-collaboration method by default. Additional methods are read from
approved package resources under `storygraph://skills/`. A manuscript cannot
register a tool, import a skill or replace a model connection.

The additional operations are `discover_capabilities`, `read_skill`,
`inspect_project`, `inspect_reviews` and `open_workflow`. Navigation results
carry typed workspace targets; following a link is an explicit UI action.
Opening a workflow never records a completed review, model run, Draft change
or canon decision. Existing tools continue to use the same reviewed services.

Replacing complete Draft references uses the session version and exact project
and language checks. Removing a reference used by adopted design evidence or
reader records requires revising those citations first. A fresh conversation
can start with a different set of references. Removing other Draft references
returns scene cards to explicit review. Repeating the same selection is a no-op.
