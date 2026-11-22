"""Local author-only context. Never exported to Writer or canon."""
import hashlib
import json
from storygraph.core.errors import ContractError
from storygraph.core.ids import new_id
from storygraph.core.time import utc_now


class AuthorContextStore:
    def __init__(self, sessions):
        self.sessions = sessions
        self.db, self.lock = sessions._connection, sessions._lock
        with self.lock, self.db:
            self.db.execute("CREATE TABLE IF NOT EXISTS author_context (project_id TEXT PRIMARY KEY, version INTEGER NOT NULL, instructions TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS author_memories (project_id TEXT, id TEXT, version INTEGER, payload TEXT, evidence_key TEXT, PRIMARY KEY(project_id,id), UNIQUE(project_id,evidence_key))")
            self.db.execute("CREATE TABLE IF NOT EXISTS author_titles (project_id TEXT, session_id TEXT, version INTEGER, title TEXT, origin TEXT, state TEXT, language TEXT, PRIMARY KEY(project_id,session_id))")
            self.db.execute("CREATE TABLE IF NOT EXISTS author_message_index (project_id TEXT, session_id TEXT, message_id TEXT, role TEXT, content TEXT, position INTEGER, payload TEXT, PRIMARY KEY(project_id,session_id,message_id))")
            columns = {r[1] for r in self.db.execute("PRAGMA table_info(author_message_index)")}
            if "payload" not in columns:
                self.db.execute("ALTER TABLE author_message_index ADD COLUMN payload TEXT")
            self.db.execute("CREATE INDEX IF NOT EXISTS author_message_scope ON author_message_index(project_id,session_id,position)")

    def context(self, project_id):
        with self.lock:
            row = self.db.execute("SELECT version,instructions FROM author_context WHERE project_id=?", (project_id,)).fetchone()
            return {"project_id": project_id, "version": row[0] if row else 0, "instructions": row[1] if row else ""}

    def instructions(self, project_id, text, expected_version):
        if len(text) > 16000:
            raise ContractError("authoring_instructions_too_long")
        with self.lock, self.db:
            if self.context(project_id)["version"] != expected_version:
                raise ContractError("authoring_stale_version")
            if expected_version == 0:
                changed = self.db.execute("INSERT OR IGNORE INTO author_context VALUES (?,1,?)", (project_id,text))
            else:
                changed = self.db.execute("UPDATE author_context SET version=version+1,instructions=? WHERE project_id=? AND version=?", (text,project_id,expected_version))
            if changed.rowcount != 1:
                raise ContractError("authoring_stale_version")
        return self.context(project_id)

    def memories(self, project_id, query="", include_withdrawn=False, offset=0, limit=30):
        if not 0 <= offset or not 1 <= limit <= 100 or len(query) > 500:
            raise ContractError("authoring_invalid_history_page")
        with self.lock:
            rows = self.db.execute("SELECT payload FROM author_memories WHERE project_id=? ORDER BY rowid DESC", (project_id,)).fetchall()
        values = [json.loads(r[0]) for r in rows]
        values = [v for v in values if (include_withdrawn or v["status"] != "withdrawn") and query.casefold() in v["text"].casefold()]
        selected = values[offset:offset + limit]
        return {"records": selected, "total_matches": len(values), "offset": offset, "more": offset + len(selected) < len(values), "next_offset": offset + len(selected) if offset + len(selected) < len(values) else None}

    def relevant(self, project_id, text, language, limit=12):
        import re
        text = text[-12000:].casefold()
        tokens = set(re.findall(r"[a-z0-9_]{3,}",text))
        chinese = re.findall(r"[\u3400-\u9fff]+",text)
        tokens.update(part[i:i+2] for part in chinese for i in range(len(part)-1))
        tokens.difference_update({"继续","讨论","一下","我们","这个","作者","记忆"})
        tokens = sorted(tokens)[:128]
        if not tokens:
            return []
        score = "+".join("(instr(lower(json_extract(payload,'$.text')||' '||json_extract(payload,'$.evidence')),?)>0)" for _ in tokens)
        with self.lock:
            rows = self.db.execute("SELECT payload,(" + score + ") score FROM author_memories WHERE project_id=? AND json_extract(payload,'$.status')!='withdrawn' AND json_extract(payload,'$.content_language')=? AND score>0 ORDER BY score DESC,rowid DESC LIMIT ?", tokens + [project_id,language,limit]).fetchall()
        return [json.loads(row[0]) for row in rows]

    @staticmethod
    def validate_memory(*, text, kind, status, evidence):
        import re
        if kind not in {"preference", "decision", "tentative"} or status not in {"active", "tentative"} or (kind == "tentative" and status != "tentative"):
            raise ContractError("authoring_memory_status")
        if not text.strip() or len(text) > 2000 or not evidence.strip() or len(evidence) > 4000:
            raise ContractError("authoring_memory_evidence")
        if status == "active" and re.search(r"暂不决定|还没决定|可能|或许|也许|待定|先不|不确定|考虑|maybe|perhaps|might|undecided",evidence,re.I):
            raise ContractError("authoring_memory_tentative_required")
        if kind == "decision" and status == "active" and not re.search(r"决定|确定|采用|定下|确认|就这样|decid|choose|chosen|confirmed",evidence,re.I):
            raise ContractError("authoring_memory_decision_evidence")

    def record(self, project_id, session_id, *, text, kind, source_message_id, evidence, status, operation="record", memory_id=None):
        self.validate_memory(text=text,kind=kind,status=status,evidence=evidence)
        with self.lock:
            row = self.db.execute("SELECT payload FROM authoring_sessions WHERE project_id=? AND id=? ORDER BY version DESC LIMIT 1", (project_id,session_id)).fetchone()
            if not row:
                raise ContractError("authoring_session_not_found")
            session = json.loads(row[0])
        try:
            message = self.message(project_id,session_id,source_message_id)["message"]
        except ContractError:
            raise ContractError("authoring_memory_evidence") from None
        if message["role"] != "author" or evidence not in message["content"]:
            raise ContractError("authoring_memory_evidence")
        if operation not in {"record", "withdraw", "replace"} or (operation != "record" and not memory_id):
            raise ContractError("authoring_memory_operation")
        key = hashlib.sha256((session_id + "\0" + source_message_id + "\0" + evidence).encode()).hexdigest()
        with self.lock, self.db:
            if operation != "record":
                prior_row = self.db.execute("SELECT payload FROM author_memories WHERE project_id=? AND id=?", (project_id,memory_id)).fetchone()
                if not prior_row:
                    raise ContractError("authoring_memory_not_found")
                prior = json.loads(prior_row[0])
                if prior["edited_by"] == "author" or prior["status"] == "withdrawn":
                    return prior
                prior.update(status="withdrawn",version=prior["version"]+1,withdrawal={"source_session_id":session_id,"source_message_id":source_message_id,"evidence":evidence})
                self.db.execute("UPDATE author_memories SET version=?,payload=? WHERE project_id=? AND id=?", (prior["version"],json.dumps(prior,ensure_ascii=False),project_id,memory_id))
                if operation == "withdraw":
                    return prior
            old = self.db.execute("SELECT payload FROM author_memories WHERE project_id=? AND (evidence_key=? OR (json_extract(payload,'$.source_message_id')=? AND json_extract(payload,'$.source_session_id')=? AND (json_extract(payload,'$.edited_by')='author' OR json_extract(payload,'$.status')='withdrawn'))) ORDER BY rowid DESC LIMIT 1", (project_id, key, source_message_id, session_id)).fetchone()
            if old:
                return json.loads(old[0])  # Includes manual edits and durable withdrawal tombstones.
            value = dict(id=new_id("amem"), project_id=project_id, version=1, text=text, kind=kind, status=status, source_session_id=session_id, source_message_id=source_message_id, evidence=evidence, content_language=session["content_language"], created_at=utc_now(), edited_by="main")
            self.db.execute("INSERT INTO author_memories VALUES (?,?,?,?,?)", (project_id, value["id"], 1, json.dumps(value, ensure_ascii=False), key))
            return value

    def edit(self, project_id, memory_id, *, expected_version, text, status):
        if not text.strip() or len(text) > 2000 or status not in {"active", "tentative", "withdrawn"}:
            raise ContractError("authoring_memory_status")
        with self.lock, self.db:
            row = self.db.execute("SELECT payload FROM author_memories WHERE project_id=? AND id=?", (project_id, memory_id)).fetchone()
            if not row:
                raise ContractError("authoring_memory_not_found")
            value = json.loads(row[0])
            if value["version"] != expected_version:
                raise ContractError("authoring_stale_version")
            value.update(text=text, status=status, version=expected_version + 1, edited_by="author")
            changed = self.db.execute("UPDATE author_memories SET version=?,payload=? WHERE project_id=? AND id=? AND version=?", (value["version"], json.dumps(value, ensure_ascii=False), project_id, memory_id,expected_version))
            if changed.rowcount != 1:
                raise ContractError("authoring_stale_version")
            return value

    def history_overrides(self, project_id, session_id, message_ids):
        if not message_ids:
            return []
        # Bound the lookup by the actual request window, not the age of a withdrawal.
        slots = ",".join("?" for _ in message_ids)
        with self.lock:
            rows = self.db.execute(f"""
                SELECT payload FROM author_memories WHERE project_id=?
                  AND json_extract(payload,'$.source_session_id')=?
                  AND json_extract(payload,'$.source_message_id') IN ({slots})
                  AND (json_extract(payload,'$.edited_by')='author'
                       OR json_extract(payload,'$.status')='withdrawn')
                ORDER BY rowid
            """, (project_id, session_id, *message_ids)).fetchall()
        return [{"source_message_id": memory["source_message_id"], "status": memory["status"],
                 "replacement": memory["text"] if memory["status"] != "withdrawn" else None}
                for memory in (json.loads(row[0]) for row in rows)]

    def title(self, project_id, session_id):
        with self.lock:
            row = self.db.execute("SELECT version,title,origin,state,language FROM author_titles WHERE project_id=? AND session_id=?", (project_id,session_id)).fetchone()
        return dict(zip(("version", "title", "origin", "state", "content_language"), row)) if row else None

    def initialize_title(self, session, *, automatic=False):
        with self.lock, self.db:
            self.db.execute("INSERT OR IGNORE INTO author_titles VALUES (?,?,1,?,?,?,?)", (session.project_id,session.id,session.title,"prefix","pending" if automatic else "disabled",session.content_language))

    def rename(self, project_id, session_id, title, expected_version):
        if not title.strip() or len(title) > 500:
            raise ContractError("authoring_invalid_title")
        self.sessions.get(project_id,session_id)
        with self.lock, self.db:
            row = self.title(project_id,session_id)
            version = row["version"] if row else 0
            auto_only_race = bool(row and row["origin"] == "automatic" and row["state"] == "done" and version == expected_version + 1)
            if version != expected_version and not auto_only_race:
                raise ContractError("authoring_stale_version")
            if row:
                changed = self.db.execute("UPDATE author_titles SET title=?,origin='manual',state='done',version=version+1 WHERE project_id=? AND session_id=? AND version=?", (title.strip(),project_id,session_id,version))
                if changed.rowcount != 1:
                    raise ContractError("authoring_stale_version")
            else:
                changed = self.db.execute("INSERT OR IGNORE INTO author_titles VALUES (?,?,?,?,?,?,?)", (project_id,session_id,1,title.strip(),"manual","done",""))
                if changed.rowcount != 1:
                    raise ContractError("authoring_stale_version")
        return self.title(project_id,session_id)

    def generate_title(self, project_id, session_id, callback, language_resolver):
        with self.lock, self.db:
            row = self.title(project_id,session_id)
            if not row or row["state"] != "pending":
                return
            claimed = self.db.execute("UPDATE author_titles SET state='started' WHERE project_id=? AND session_id=? AND state='pending'", (project_id,session_id))
            if claimed.rowcount != 1:
                return
        try:
            session = self.sessions.get(project_id,session_id,full=True)
            if language_resolver(project_id) != row["content_language"]:
                raise ValueError("language changed")
            first = next(m["content"] for m in session["messages"] if m["role"] == "author")
            title = callback(project_id, first[:12000], row["content_language"])
            if not isinstance(title,str) or not title.strip() or len(title) > 120 or "\n" in title or language_resolver(project_id) != row["content_language"]:
                raise ValueError("invalid title")
        except Exception:
            with self.lock, self.db:
                self.db.execute("UPDATE author_titles SET state='failed' WHERE project_id=? AND session_id=? AND version=? AND state='started'", (project_id,session_id,row["version"]))
            return
        with self.lock, self.db:
            self.db.execute("UPDATE author_titles SET title=?,origin='automatic',state='done',version=version+1 WHERE project_id=? AND session_id=? AND version=? AND state='started'", (title.strip(),project_id,session_id,row["version"]))

    def session_page(self, project_id, query="", offset=0, limit=100):
        if offset < 0 or not 1 <= limit <= 100 or len(query) > 500:
            raise ContractError("authoring_invalid_history_page")
        with self.lock:
            sql = "FROM authoring_sessions s JOIN (SELECT id,MAX(version) version FROM authoring_sessions WHERE project_id=? GROUP BY id) v ON s.id=v.id AND s.version=v.version LEFT JOIN author_titles t ON t.project_id=s.project_id AND t.session_id=s.id WHERE s.project_id=? AND instr(lower(COALESCE(t.title,json_extract(s.payload,'$.title'))),lower(?))>0"
            args = [project_id,project_id,query]
            count = self.db.execute("SELECT count(*) " + sql,args).fetchone()[0]
            rows = self.db.execute("SELECT s.payload " + sql + " ORDER BY s.rowid DESC LIMIT ? OFFSET ?", args+[limit,offset]).fetchall()
            values = []
            for row in rows:
                payload = json.loads(row[0])
                value = {k:payload.get(k) for k in ("id","title","version","turn_status","updated_at")}
                value["title_metadata"] = self.title(project_id,value["id"])
                if value["title_metadata"]:
                    value["title"] = value["title_metadata"]["title"]
                values.append(value)
        return {"sessions":values,"total_matches":count,"offset":offset,"more":offset+len(values)<count,"next_offset":offset+len(values) if offset+len(values)<count else None}

    def index_messages(self, project_id, session_id, messages):
        for position,message in enumerate(messages):
            if message["role"] in {"author", "assistant"}:
                self.db.execute("INSERT INTO author_message_index VALUES (?,?,?,?,?,?,?) ON CONFLICT(project_id,session_id,message_id) DO UPDATE SET payload=excluded.payload WHERE author_message_index.payload IS NULL", (project_id,session_id,message["id"],message["role"],message["content"],position,json.dumps(message,ensure_ascii=False)))

    def message(self, project_id, session_id, message_id):
        with self.lock:
            row = self.db.execute("SELECT payload,position FROM author_message_index WHERE project_id=? AND session_id=? AND message_id=?", (project_id,session_id,message_id)).fetchone()
            if row and row[0]:
                return {"message":json.loads(row[0]),"session_id":session_id,"position":row[1]}
            # Legacy journals are migrated once, on first project search/message access.
            self.search(project_id,"",limit=1,session_id=session_id)
            row = self.db.execute("SELECT payload,position FROM author_message_index WHERE project_id=? AND session_id=? AND message_id=?", (project_id,session_id,message_id)).fetchone()
            if row and row[0]:
                return {"message":json.loads(row[0]),"session_id":session_id,"position":row[1]}
        raise ContractError("authoring_message_not_found")

    def search(self, project_id, query, offset=0, limit=40, session_id=None):
        if len(query) > 500 or offset < 0 or not 1 <= limit <= 100:
            raise ContractError("authoring_invalid_history_page")
        # Index only this project's historical journals; never inspect settings or unrelated tables.
        with self.lock, self.db:
            rows = self.db.execute("SELECT s.payload FROM authoring_sessions s JOIN (SELECT id,MAX(version) version FROM authoring_sessions WHERE project_id=? GROUP BY id) v ON s.id=v.id AND s.version=v.version WHERE s.project_id=? AND NOT EXISTS (SELECT 1 FROM author_message_index i WHERE i.project_id=s.project_id AND i.session_id=s.id)", (project_id,project_id)).fetchall()
            for row in rows:
                payload = json.loads(row[0])
                refs = payload.get("_journal_v1")
                if refs is None:
                    self.index_messages(project_id,payload["id"],payload.get("messages",[]))
                else:
                    records = self.db.execute("SELECT b.payload,j.key FROM json_each(?) j JOIN authoring_blobs b ON b.sha256=j.value WHERE json_extract(b.payload,'$.role') IN ('author','assistant')", (json.dumps(refs["messages"]),)).fetchall()
                    for message_payload,position in records:
                        message = json.loads(message_payload)
                        self.db.execute("INSERT INTO author_message_index VALUES (?,?,?,?,?,?,?) ON CONFLICT(project_id,session_id,message_id) DO UPDATE SET payload=excluded.payload WHERE author_message_index.payload IS NULL", (project_id,payload["id"],message["id"],message["role"],message["content"],position,message_payload))
            clause = "project_id=? AND instr(lower(content),lower(?))>0"
            args = [project_id,query]
            if session_id:
                clause += " AND session_id=?"
                args.append(session_id)
            count = self.db.execute("SELECT count(*) FROM author_message_index WHERE " + clause,args).fetchone()[0]
            rows = self.db.execute("SELECT session_id,message_id,role,content,position FROM author_message_index WHERE " + clause + " ORDER BY json_extract(payload,'$.created_at') DESC,session_id,position DESC LIMIT ? OFFSET ?", args + [limit,offset]).fetchall()
        records = [dict(zip(("session_id","message_id","role","content","position"),r)) for r in rows]
        return {"records":records,"total_matches":count,"offset":offset,"more":offset+len(rows)<count,"next_offset":offset+len(rows) if offset+len(rows)<count else None}
