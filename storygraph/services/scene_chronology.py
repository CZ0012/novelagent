"""Sound world chronology from reviewed scene times, never narrative slots.

Persisted automatic links stay sparse. The internal order additionally joins
every proven accepted interval without exposing dense virtual Graph relations.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date

from storygraph.core.ids import slug_id

PROOF_KEY = "auto_chronology_v1"
_DAY = re.compile(r"(?:第([零〇一二两三四五六七八九十百千万\d]+)[日天]|\bDay\s+(\d+)\b)", re.I)
_CLOCK = re.compile(r"(?<![\d:])(\d{1,2}):(\d{2})(?::(\d{2}))?(?![\d:])")
_ISO = re.compile(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?(Z)?)?")
_DAY_TEXT = r"(?:第[零〇一二两三四五六七八九十百千万\d]+[日天]|Day\s+\d+)"
_TIME_TEXT = r"\d{1,2}:\d{2}(?::\d{2})?"
_RELATIVE_RANGE = re.compile(_DAY_TEXT + r"\s*[,，]?\s*" + _TIME_TEXT + r"\s*(?:—|–|-|至|到|~|～|\bto\b)\s*(?:" + _DAY_TEXT + r"\s*[,，]?\s*)?" + _TIME_TEXT, re.I)
_ISO_TEXT = r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2})?Z?"
_ISO_RANGE = re.compile(_ISO_TEXT + r"\s*(?:—|–|至|到|~|～|\bto\b|\s-\s)\s*" + _ISO_TEXT, re.I)
_AUTO_SOURCE = re.compile(r"proposal:([^:]+):(longform|longform-book|composition):[a-f0-9]{64}\Z")
_UNSUPPORTED_CLOCK_QUALIFIER = re.compile(
    r"(?<![A-Za-z])(?:a\.?m\.?|p\.?m\.?|noon|midnight)(?![A-Za-z])"
    r"|上午|下午|午前|午后|中午|正午|凌晨|清晨|早晨|早上|早间|午间|傍晚|晚上|晚间|夜间|半夜|午夜|黎明|黄昏", re.I)
_UNSUPPORTED_RELATIVE_ZONE = re.compile(
    r"\b(?:UTC|GMT|CST|JST|EST|EDT|PST|PDT|CET|CEST|EET|EEST|BST|IST|KST|HKT|SGT|AEST|AEDT|NZST|NZDT)\b"
    r"|北京时间|中国标准时间|东京时间|夏令时|时区", re.I)


def timeline_hash(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _number(value):
    if value.isascii() and value.isdigit():
        return int(value)
    digits = dict(zip("零〇一二两三四五六七八九", (0, 0, 1, 2, 2, 3, 4, 5, 6, 7, 8, 9)))
    total, current, previous_unit, zero, current_has_zero = 0, None, 10000, False, False
    for index, char in enumerate(value):
        if char in digits:
            digit = digits[char]
            if digit == 0:
                if current is not None or zero or total == 0:
                    return None
                zero = True
            else:
                if current is not None:
                    return None
                current_has_zero = zero
                current, zero = digit, False
        elif char in "十百千":
            unit = {"十": 10, "百": 100, "千": 1000}[char]
            if zero or unit >= previous_unit or (current is None and not (index == 0 and unit == 10)):
                return None
            total += (current or 1) * unit
            current, previous_unit = None, unit
        else:
            return None
    # A missing unit/zero in 二百三 or 一千二百三 is colloquially ambiguous:
    # never silently choose 203/1203 rather than 230/1230.
    if zero or (total and current is not None and previous_unit >= 100 and not current_has_zero):
        return None
    return total + (current or 0)


def parse_scene_interval(text):
    """Return a conservative (calendar-domain, start, end), or unknown.

    Every explicit range contributes to the envelope. Lone clocks and partially
    parsed multi-segment fields remain unknown. ISO/relative days never mix.
    """
    if not isinstance(text, str) or not text.strip() or re.search(r"以后|之后|以前|之前|次日|翌日|次晨|翌晨|次月|次年|after|before|later", text, re.I):
        return None
    if _UNSUPPORTED_CLOCK_QUALIFIER.search(text):
        return None
    if _UNSUPPORTED_RELATIVE_ZONE.search(text):
        return None
    iso = list(_ISO.finditer(text))
    if iso:
        if _DAY.search(text) or re.search(r"[+-]\d{2}:\d{2}", text):
            return None
        ranges = list(_ISO_RANGE.finditer(text))
        if not ranges or any(not any(r.start() <= m.start() and m.end() <= r.end() for r in ranges) for m in iso):
            return None
        if any(m[5] for m in iso) and not all(m[5] for m in iso):
            return None
        points = []
        indexed_points = {}
        try:
            for m in iso:
                day = date.fromisoformat(m[1]).toordinal() * 86400
                h, minute, second = int(m[2] or 0), int(m[3] or 0), int(m[4] or 0)
                if h > 23 or minute > 59 or second > 59:
                    return None
                point = day + h * 3600 + minute * 60 + second
                points.append(point)
                indexed_points[m.start(), m.end()] = point
            for interval in ranges:
                endpoints = [indexed_points[m.start(), m.end()] for m in iso
                             if interval.start() <= m.start() and m.end() <= interval.end()]
                if len(endpoints) != 2 or endpoints[0] > endpoints[1]:
                    return None
            # A range must repeat its ISO date: do not guess trailing clock dates.
            if len(list(_CLOCK.finditer(text))) != sum(m[2] is not None for m in iso):
                return None
            return ("iso_utc" if all(m[5] for m in iso) else "iso_local", min(points), max(points))
        except ValueError:
            return None
    days = list(_DAY.finditer(text))
    if not days or re.search(r"第[^，。;；]*卷", text):
        return None
    day_values = [_number(m[1] or m[2]) for m in days]
    if any(day is None or day < 1 for day in day_values):
        return None
    clocks = list(_CLOCK.finditer(text))
    if not clocks:
        if not re.fullmatch(r"\s*" + _DAY_TEXT + r"(?:\s*(?:—|–|-|至|到|~|～|\bto\b)\s*" + _DAY_TEXT + r")?\s*[。.]?\s*", text, re.I):
            return None
        return ("relative_day", min(day_values) * 86400, (max(day_values) + 1) * 86400 - 1)
    ranges = list(_RELATIVE_RANGE.finditer(text))
    if not ranges or any(not any(r.start() <= m.start() and m.end() <= r.end() for r in ranges) for m in [*days, *clocks]):
        return None
    points = []
    for clock in clocks:
        preceding = [i for i, day in enumerate(days) if day.end() <= clock.start()]
        if not preceding:
            return None
        day = day_values[preceding[-1]]
        hour, minute, second = int(clock[1]), int(clock[2]), int(clock[3] or 0)
        if hour > 23 or minute > 59 or second > 59:
            return None
        points.append(day * 86400 + hour * 3600 + minute * 60 + second)
    # Descending endpoints can be an unstated midnight crossing. Never repair it.
    if any(b < a for a, b in zip(points, points[1:])):
        return None
    return "relative_day", min(points), max(points)


def automatic_scene_links(scene_properties, *, target_ids=None):
    """At most one proven predecessor per target, O(n²) comparisons/O(n) edges.

    Choose the latest strictly completed predecessor. Parallel branches whose
    state cannot be established by this sound suborder remain ambiguous.
    """
    times = {ref: parse_scene_interval(p.get("timeline_position")) for ref, p in scene_properties.items()}
    result = []
    for target in sorted(scene_properties):
        interval = times.get(target)
        if interval is None:
            continue
        prior = [ref for ref, other in times.items() if ref != target and other is not None
                 and other[0] == interval[0] and other[2] < interval[1]]
        if not prior:
            continue
        source = max(prior, key=lambda ref: (times[ref][2], times[ref][1], ref))
        if target_ids is not None and source not in target_ids and target not in target_ids:
            continue
        proof = {"origin": "accepted_timeline_position",
                 "source_timeline_sha256": timeline_hash(scene_properties[source].get("timeline_position")),
                 "target_timeline_sha256": timeline_hash(scene_properties[target].get("timeline_position"))}
        result.append((source, target, proof))
    return result


def _derived_scene(node):
    p = node.properties
    parent, local = p.get("longform_blueprint_id"), p.get("longform_scene_id")
    return isinstance(parent, str) and isinstance(local, str) and node.id == "scene_lp_" + hashlib.sha256(parent.encode()).hexdigest()[:16] + "_" + local


def _automatic_creation(node, event, creations):
    p = event.payload
    props = p.get("properties", {})
    if event.operation != "create_node" or event.target != node.id or p.get("id") != node.id or p.get("type") != "Scene" or p.get("status") != "CANON":
        return False
    if p.get("source_ref") != event.source_ref or p.get("event_id") != event.event_id or not event.source_ref or not event.reviewer or not event.rationale:
        return False
    if props.get("project_id") != node.properties.get("project_id"):
        return False
    source = _AUTO_SOURCE.fullmatch(event.source_ref)
    if source and source[2] in {"longform", "longform-book"} and _derived_scene(node):
        return all(props.get(k) == node.properties.get(k) for k in ("longform_blueprint_id", "longform_scene_id"))
    composition = props.get("source_composition_proposal_id")
    if source and source[2] == "composition" and composition == source[1]:
        prefix = "scene_cmp_" + hashlib.sha256(composition.encode()).hexdigest()[:20] + "_"
        return re.fullmatch(re.escape(prefix) + r"\d+_\d+", node.id) is not None and node.properties.get("source_composition_proposal_id") == composition
    structure = props.get("source_structure_proposal_id")
    if isinstance(structure, str) and structure and type(props.get("source_structure_proposal_version")) is int:
        if any(props.get(k) != node.properties.get(k) for k in ("source_structure_proposal_id", "source_structure_proposal_version")):
            return False
        chapter = creations.get(props.get("chapter_id"), ())
        if len(chapter) != 1:
            return False
        cp = chapter[0].payload.get("properties", {})
        # Imported structure IDs use generated ordinal slots, while the author
        # may override displayed chapter_index/scene_index. Creation-event order
        # is used ONLY to verify that ID recipe, never as story chronology.
        owned = [events[0] for events in creations.values() if len(events) == 1
                 and events[0].payload.get("properties", {}).get("project_id") == props.get("project_id")
                 and events[0].payload.get("properties", {}).get("source_structure_proposal_id") == structure]
        chapters = [e.target for e in owned if e.payload.get("type") == "Chapter"]
        scenes = [e.target for e in owned if e.payload.get("type") == "Scene"
                  and e.payload.get("properties", {}).get("chapter_id") == props.get("chapter_id")]
        if props.get("chapter_id") not in chapters or node.id not in scenes:
            return False
        chapter_slot, scene_slot = chapters.index(props["chapter_id"]) + 1, scenes.index(node.id) + 1
        return (cp.get("project_id") == props.get("project_id") and cp.get("source_structure_proposal_id") == structure
                and chapter[0].source_ref == event.source_ref and chapter[0].reviewer and chapter[0].rationale
                and node.id == slug_id("scene", f"{props['project_id']}_{chapter_slot}_{scene_slot}_{props.get('title')}"))
    return False


def _creation_index(snapshot):
    result = {}
    for event in snapshot.event_log.list():
        if event.operation == "create_node":
            result.setdefault(event.target, []).append(event)
    return result


def _approved_intervals(snapshot, nodes):
    creations = _creation_index(snapshot)
    changes = {}
    for event in snapshot.event_log.list():
        if event.target in nodes and event.operation in {"create_node", "update_node"}:
            changes.setdefault(event.target, []).append(event)
    result = {}
    for ref, node in nodes.items():
        events = changes.get(ref, ())
        if not events or len(creations.get(ref, ())) != 1 or not _automatic_creation(node, events[0], creations):
            continue
        props = dict(events[0].payload.get("properties", {}))
        valid = True
        for event in events[1:]:
            if event.operation != "update_node" or not event.source_ref or not event.reviewer or not event.rationale:
                valid = False
                break
            props.update(event.payload)
        latest = events[-1]
        if not valid or props != node.properties or any(getattr(node, k) != getattr(latest, k) for k in ("event_id", "source_ref", "reviewer", "rationale")):
            continue
        interval = parse_scene_interval(props.get("timeline_position"))
        if interval is not None:
            result[ref] = interval
    return result


def reliable_scene_edges(snapshot, project_id):
    """Consume one caller-owned snapshot, including its immutable event evidence.

    Recognized old automatic edges are revalidated, not migrated. Explicit
    manually authored NEXT_SCENE links retain their existing authority.
    """
    nodes = {ref: node for ref, node in snapshot.nodes.items() if node.type == "Scene"
             and node.status == "CANON" and node.properties.get("project_id") == project_id}
    edges = {ref: set() for ref in nodes}
    events = {e.event_id: e for e in snapshot.event_log.list()}
    creations = _creation_index(snapshot)
    relation_creations = {}
    for event in events.values():
        if event.operation == "create_relation":
            relation_creations.setdefault(event.target, []).append(event)

    def original_time(node):
        original = [e for e in creations.get(node.id, ()) if e.source_ref == e.payload.get("source_ref")
                    and e.payload.get("id") == node.id and e.payload.get("type") == "Scene"
                    and e.payload.get("event_id") == e.event_id and e.payload.get("status") == "CANON"
                    and _automatic_creation(node, e, creations)
                    and e.payload.get("properties", {}).get("project_id") == project_id
                    and e.reviewer and e.rationale]
        return original[0].payload.get("properties", {}).get("timeline_position") if len(original) == 1 else None

    for rel in snapshot.relationships.values():
        if rel.type != "NEXT_SCENE" or rel.status != "CANON" or rel.properties.get("project_id") != project_id:
            continue
        a, b = nodes.get(rel.source_id), nodes.get(rel.target_id)
        # Retain malformed manual edges so existing cycle/missing-node checks fail closed.
        if a is None or b is None:
            edges.setdefault(rel.source_id, set()).add(rel.target_id)
            continue
        source_refs = {rel.source_ref, *[e.source_ref for e in relation_creations.get(rel.id, ())]}
        sources = [match for ref in source_refs if (match := _AUTO_SOURCE.fullmatch(ref))]
        lp_id = "rel_lp_" + hashlib.sha256(f"{a.id}:NEXT_SCENE:{b.id}".encode()).hexdigest()[:32]
        composition_id = slug_id("rel", f"{a.id}_NEXT_SCENE_{b.id}")
        lp_ids, composition_ids = {lp_id}, {composition_id}
        for creation in relation_creations.get(rel.id, ()):
            p = creation.payload
            if p.get("type") == "NEXT_SCENE" and p.get("source_id") and p.get("target_id"):
                lp_ids.add("rel_lp_" + hashlib.sha256(f"{p['source_id']}:NEXT_SCENE:{p['target_id']}".encode()).hexdigest()[:32])
                composition_ids.add(slug_id("rel", f"{p['source_id']}_NEXT_SCENE_{p['target_id']}"))
        # Classification is based on production provenance/derived relation ID,
        # not mutable Scene metadata. Corrupt automatic provenance must fail
        # validation below, never turn an automatic edge into manual authority.
        looks_auto = any((source[2] in {"longform", "longform-book"} and rel.id in lp_ids)
            or (source[2] == "composition" and rel.id in composition_ids) for source in sources)
        if rel.id in composition_ids:
            for node in (a, b):
                original = creations.get(node.id, ())
                if any(e.source_ref in source_refs and e.payload.get("properties", {}).get("source_structure_proposal_id") for e in original):
                    looks_auto = True
                if node.source_ref == rel.source_ref and node.properties.get("source_structure_proposal_id"):
                    looks_auto = True
        proof = rel.properties.get(PROOF_KEY)
        if proof is None and not looks_auto:
            edges[a.id].add(b.id)
            continue
        event = events.get(rel.event_id)
        if not event or event.operation != "create_relation" or event.target != rel.id or event.source_ref != rel.source_ref or not event.reviewer or not event.rationale:
            continue
        payload = event.payload
        if any(payload.get(k) != getattr(rel, k) for k in ("id", "type", "source_id", "target_id", "source_ref", "event_id")) or payload.get("properties") != rel.properties:
            continue
        if proof is not None:
            if not looks_auto or proof != {"origin": "accepted_timeline_position",
                    "source_timeline_sha256": timeline_hash(a.properties.get("timeline_position")),
                    "target_timeline_sha256": timeline_hash(b.properties.get("timeline_position"))}:
                continue
        elif any(original_time(n) != n.properties.get("timeline_position") for n in (a, b)):
            continue
        x, y = parse_scene_interval(a.properties.get("timeline_position")), parse_scene_interval(b.properties.get("timeline_position"))
        if x is not None and y is not None and x[0] == y[0] and x[2] < y[1]:
            edges[a.id].add(b.id)
    return edges


class SceneOrder:
    """Request-local bitset closure, never serialized as Graph relations."""
    def __init__(self, ids, rows, invalid=False):
        self.index = {ref: i for i, ref in enumerate(ids)}
        self.rows = rows
        self.cyclic = invalid or any(row & (1 << i) for i, row in enumerate(rows))

    def before(self, source, target):
        a, b = self.index.get(source), self.index.get(target)
        return a is not None and b is not None and bool(self.rows[a] & (1 << b))


def reliable_scene_order(snapshot, project_id):
    """Full proven interval/manual order, bounded in memory rather than canon.

    An accepted automatic creation and its fully evidenced approved updates are
    required independently for each interval. Being parsable alone cannot give
    an unreviewed edit authority after an original edge proof has gone stale.
    """
    nodes = {ref: n for ref, n in snapshot.nodes.items() if n.type == "Scene"
             and n.status == "CANON" and n.properties.get("project_id") == project_id}
    ids = sorted(nodes)
    index = {ref: i for i, ref in enumerate(ids)}
    rows = [0] * len(ids)
    invalid = False
    for source, targets in reliable_scene_edges(snapshot, project_id).items():
        for target in targets:
            if source not in index or target not in index:
                invalid = True
            else:
                rows[index[source]] |= 1 << index[target]
    intervals = _approved_intervals(snapshot, nodes)
    for source, a in intervals.items():
        for target, b in intervals.items():
            if source != target and a[0] == b[0] and a[2] < b[1]:
                rows[index[source]] |= 1 << index[target]
    # Bitset Warshall: complete closure without O(n²) stored Graph objects or
    # repeated traversals for each assertion. No mutable/global cache exists.
    for k in range(len(ids)):
        bit = 1 << k
        for i in range(len(ids)):
            if rows[i] & bit:
                rows[i] |= rows[k]
    return SceneOrder(ids, rows, invalid)
