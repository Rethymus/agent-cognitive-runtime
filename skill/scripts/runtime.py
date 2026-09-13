"""Local, single-user Cognitive Runtime adapter. Python 3.10+, stdlib only.

No network, model calls, background worker, independent evaluator or publisher.
The API checks prevent accidental misuse; unrestricted shell access can bypass them.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import uuid

VERSION = "0.3.2"
KINDS = {"user", "project", "episodic", "failure", "procedural", "skill_library", "evaluation", "task"}
TTL = {"user": 180, "project": 90, "episodic": 14, "failure": 90, "procedural": 90, "skill_library": 90, "evaluation": 180, "task": 14}
ASSET = {"problem_pattern", "decision", "evidence", "failure_mode", "heuristic", "validation_result"}
PHASES = {"contract", "plan", "act", "verify", "delivered", "blocked"}


def dump(x):
    return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def need(condition, message):
    if not condition:
        raise ValueError(message)


def keys(x, required, optional=()):
    need(isinstance(x, dict), "expected object")
    need(set(required) <= x.keys(), "missing required fields: " + ",".join(sorted(set(required) - x.keys())))
    need(x.keys() <= set(required) | set(optional), "unknown fields are not accepted")


def string(x, limit=2000):
    need(isinstance(x, str) and 0 < len(x) <= limit, "expected nonempty bounded string")


def integer(x, low, high):
    need(type(x) is int and low <= x <= high, "integer outside allowed range")


def texts(x, limit=20):
    need(isinstance(x, list) and 0 < len(x) <= limit, "expected bounded nonempty list")
    for s in x:
        string(s)


def project_scope(project):
    string(project, 1000)
    p = Path(project)
    need(p.is_absolute() and p.is_dir(), "project must be an existing absolute directory")
    return "project:" + hashlib.sha256(os.path.normcase(str(p.resolve())).encode()).hexdigest()


def file_hash(path):
    p = Path(path)
    need(p.is_absolute() and p.is_file(), "evidence must be an existing absolute file")
    need(p.stat().st_size <= 64 * 1024 * 1024, "evidence file exceeds 64 MiB")
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Runtime:
    def __init__(self, state_dir):
        self.root = Path(state_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / "memory.sqlite3", timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA secure_delete=ON")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS records(
          id TEXT PRIMARY KEY, scope TEXT NOT NULL, kind TEXT NOT NULL,
          status TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL,
          created REAL NOT NULL, updated REAL NOT NULL, review REAL NOT NULL,
          expires REAL NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS scope_idx ON records(scope,kind,status);
        CREATE TABLE IF NOT EXISTS edges(parent TEXT NOT NULL, child TEXT NOT NULL,
          PRIMARY KEY(parent,child), FOREIGN KEY(parent) REFERENCES records(id),
          FOREIGN KEY(child) REFERENCES records(id));
        CREATE TABLE IF NOT EXISTS requests(key TEXT PRIMARY KEY,digest TEXT NOT NULL,
          record_id TEXT NOT NULL,revision INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,at REAL NOT NULL,
          action TEXT NOT NULL,record_id TEXT NOT NULL,revision INTEGER NOT NULL);
        """)

    def close(self):
        self.db.close()

    def event(self, action, record_id, revision):
        self.db.execute("INSERT INTO events(at,action,record_id,revision) VALUES(?,?,?,?)", (time.time(), action, record_id, revision))

    def scope(self, q):
        return project_scope(q["project"]) if "project" in q else "user:local"

    def row(self, rid, scope):
        string(rid, 100)
        row = self.db.execute("SELECT * FROM records WHERE id=? AND scope=?", (rid, scope)).fetchone()
        need(row is not None and not row["deleted"], "record unavailable in scope")
        return row

    def public(self, row):
        body = json.loads(row["body"])
        stale = False
        for parent, revision in body.get("parent_revisions", {}).items():
            prow = self.db.execute("SELECT * FROM records WHERE id=?", (parent,)).fetchone()
            if prow is None or prow["deleted"] or prow["revision"] != revision or prow["status"] == "deprecated" or prow["review"] <= time.time():
                stale = True
            elif self.public(prow)["dependency_stale"]:
                stale = True
        for dependency in body.get("files", []):
            try:
                stale |= file_hash(dependency["path"]) != dependency["sha256"]
            except (ValueError, OSError):
                stale = True
        return {"id": row["id"], "scope": row["scope"], "kind": row["kind"], "status": row["status"],
                "revision": row["revision"], "review_due": row["review"] <= time.time(),
                "expired": row["expires"] <= time.time(), "dependency_stale": stale,
                "instruction_authority": "none", "body": body}

    def erase(self, rid):
        # Retain tombstone ids, never retained bodies, for non-resurrection and cascading deletion.
        pending, seen = [rid], set()
        while pending:
            item = pending.pop()
            if item in seen:
                continue
            seen.add(item)
            pending.extend(r[0] for r in self.db.execute("SELECT child FROM edges WHERE parent=?", (item,)))
            row = self.db.execute("SELECT revision,deleted FROM records WHERE id=?", (item,)).fetchone()
            if row and not row["deleted"]:
                self.db.execute("UPDATE records SET body='{}',deleted=1,status='forgotten',revision=revision+1,updated=? WHERE id=?", (time.time(), item))
                self.event("forget", item, row["revision"] + 1)
        return len(seen)

    def gc(self):
        expired = self.db.execute("SELECT id FROM records WHERE expires<=? AND deleted=0", (time.time(),)).fetchall()
        for row in expired:
            self.erase(row[0])
        return len(expired)

    def request(self, q):
        need(isinstance(q, dict) and len(dump(q)) <= 24000, "request must be an object up to 24000 characters")
        action = q.get("action")
        # A real write transaction makes CAS, idempotency, GC and dependent edits atomic.
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.gc()
            result = self.dispatch(action, q)
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            raise

    def dispatch(self, action, q):
        if action == "status":
            keys(q, {"action"})
            return {"version": VERSION, "storage": str(self.root / "memory.sqlite3"), "live_records": self.db.execute("SELECT count(*) FROM records WHERE deleted=0").fetchone()[0], "automatic_promotion": False, "independent_verifier": False, "model_dispatch": False, "network_calls": 0, "trust_boundary": "single_os_user_advisory"}
        if action == "check_file":
            keys(q, {"action", "path"})
            digest = file_hash(q["path"])
            return {"path": str(Path(q["path"]).resolve()), "sha256": digest, "check": "bytes_observed_only", "business_result": "unknown"}
        if action in {"promote", "verify_candidate"}:
            raise ValueError("independent evaluator and publisher unavailable; candidate cannot be advanced")
        if action == "gc":
            keys(q, {"action"})
            return {"ok": True, "expired_content_removed_on_access": True}
        if action == "recommend_route":
            keys(q, {"action", "task_type", "verifiable", "failed_attempts"})
            need(q["task_type"] in {"routine", "architecture", "critique", "promotion_review"}, "unknown task type")
            need(type(q["verifiable"]) is bool, "verifiable must be boolean")
            integer(q["failed_attempts"], 0, 100)
            from subagent_router import load, resolve
            registry, policy = load()
            role = "acr_architect" if q["task_type"] == "architecture" else ("acr_reviewer" if q["task_type"] != "routine" or q["failed_attempts"] >= 2 or not q["verifiable"] else "acr_worker")
            resolved = resolve(role, registry, policy)
            return dict(resolved, recommended_model=resolved["model"], dispatch_performed=False, current_model_unchanged=True, quality_calibration="not_run", deprecated_interface="Use subagent_router.py route with complete task features before delegation")
        if action == "retrieve":
            keys(q, {"action", "project", "query"}, {"include_user", "include_candidates", "limit", "max_chars", "kind"})
            string(q["query"], 200)
            limit, chars = q.get("limit", 6), q.get("max_chars", 8000)
            integer(limit, 1, 6)
            integer(chars, 100, 8000)
            for flag in ("include_user", "include_candidates"):
                need(type(q.get(flag, False)) is bool, "flags must be boolean")
            if "kind" in q:
                need(q["kind"] in KINDS, "unknown kind")
            scopes = [self.scope(q)] + (["user:local"] if q.get("include_user") else [])
            terms = q["query"].casefold().split()
            ranked = []
            for scope in scopes:
                for row in self.db.execute("SELECT * FROM records WHERE scope=? AND deleted=0 AND status!='deprecated' ORDER BY updated DESC LIMIT 500", (scope,)):
                    if row["status"] == "candidate" and not q.get("include_candidates"):
                        continue
                    if "kind" in q and row["kind"] != q["kind"]:
                        continue
                    body = json.loads(row["body"])
                    hay = (body["title"] + " " + dump(body["content"]) + " " + " ".join(body["tags"])).casefold()
                    score = sum(term in hay for term in terms)
                    if not score:
                        continue
                    view = self.public(row)
                    if view["dependency_stale"] or view["review_due"] or view["expired"]:
                        continue
                    ranked.append((score, row["updated"], view))
            result, used = [], 0
            for _, _, item in sorted(ranked, key=lambda v: (v[0], v[1]), reverse=True):
                size = len(dump(item))
                if used + size > chars:
                    continue
                result.append(item)
                used += size
                if len(result) >= limit:
                    break
            return {"entries": result, "characters": used, "ranking": "bounded_keyword_recency", "instruction_authority": "none"}
        if action in {"get", "forget", "deprecate"}:
            keys(q, {"action", "id"}, {"project", "expected_revision"})
            row = self.row(q["id"], self.scope(q))
            if action == "get":
                return self.public(row)
            integer(q.get("expected_revision"), 1, 2147483647)
            need(q["expected_revision"] == row["revision"], "revision conflict; read latest before modifying")
            if action == "forget":
                return {"forgotten_records": self.erase(row["id"])}
            self.db.execute("UPDATE records SET status='deprecated',revision=revision+1,updated=? WHERE id=?", (time.time(), row["id"]))
            self.event("deprecate", row["id"], row["revision"] + 1)
            return {"id": row["id"], "status": "deprecated", "revision": row["revision"] + 1}
        if action == "put":
            return self.put(q)
        raise ValueError("unknown action")

    def put(self, q):
        keys(q, {"action", "kind", "title", "content", "provenance", "idempotency_key"}, {"project", "id", "expected_revision", "ttl_days", "review_days", "tags", "derived_from", "files", "sensitivity", "consent_ref"})
        need(q["kind"] in KINDS, "unknown kind")
        need((q["kind"] == "user") == ("project" not in q), "user entries require global scope; all other kinds require project")
        string(q["title"], 200)
        string(q["idempotency_key"], 100)
        sensitivity = q.get("sensitivity", "ordinary")
        need(sensitivity in {"ordinary", "sensitive"}, "credentials and secret payloads are not supported")
        prov = q["provenance"]
        keys(prov, {"source_type", "source_ref"})
        need(prov["source_type"] in {"user_stated", "tool_observed", "agent_inferred", "teacher_critique"}, "unsupported provenance")
        string(prov["source_ref"], 1500)
        if sensitivity == "sensitive":
            need(prov["source_type"] == "user_stated", "sensitive personal inference cannot be persisted")
            string(q.get("consent_ref"), 1000)
        if q["kind"] == "user":
            need(prov["source_type"] == "user_stated", "global user facts require explicit user attribution")
        content = q["content"]
        if q["kind"] in {"failure", "procedural", "skill_library"}:
            keys(content, ASSET)
            for value in content.values():
                string(value, 1500)
        elif q["kind"] == "task":
            keys(content, {"goal", "deliverables", "success_criteria", "constraints", "phase", "next_action", "budget"})
            for key in ("goal", "constraints", "next_action"):
                string(content[key])
            texts(content["deliverables"])
            texts(content["success_criteria"])
            need(content["phase"] in PHASES, "invalid task phase")
            keys(content["budget"], {"max_retries", "max_teacher_rounds", "max_usd"})
            integer(content["budget"]["max_retries"], 0, 2)
            integer(content["budget"]["max_teacher_rounds"], 0, 1)
            cost = content["budget"]["max_usd"]
            need(cost is None or (type(cost) in (int, float) and 0 < cost <= 100), "invalid cost budget; unknown is null")
        else:
            string(content, 5000)
        tags = q.get("tags", [])
        need(isinstance(tags, list) and len(tags) <= 10, "too many tags")
        for tag in tags:
            string(tag, 80)
        files = q.get("files", [])
        need(isinstance(files, list) and len(files) <= 10, "too many file dependencies")
        for dep in files:
            keys(dep, {"path", "sha256"})
            need(file_hash(dep["path"]) == dep["sha256"], "file dependency mismatch")
        parents = q.get("derived_from", [])
        need(isinstance(parents, list) and len(parents) <= 10, "too many provenance dependencies")
        scope = self.scope(q)
        digest = hashlib.sha256(dump(q).encode()).hexdigest()
        previous = self.db.execute("SELECT * FROM requests WHERE key=?", (q["idempotency_key"],)).fetchone()
        if previous:
            need(previous["digest"] == digest, "idempotency key reused for a different request")
            row = self.row(previous["record_id"], scope)
            return {"id": row["id"], "revision": previous["revision"], "current_revision": row["revision"], "replayed": True}
        parent_revisions = {}
        for parent in parents:
            # Cross-scope derivations are disabled in this local adapter.
            prow = self.row(parent, scope)
            need(prow["status"] != "deprecated", "cannot derive from deprecated record")
            pview = self.public(prow)
            need(not pview["dependency_stale"] and not pview["review_due"], "cannot derive from stale record")
            parent_revisions[parent] = prow["revision"]
        ttl, review = q.get("ttl_days", TTL[q["kind"]]), q.get("review_days", min(7, q.get("ttl_days", TTL[q["kind"]])))
        integer(ttl, 1, 365)
        integer(review, 1, ttl)
        rid, rev, now = q.get("id", str(uuid.uuid4())), 1, time.time()
        if "id" in q:
            row = self.row(rid, scope)
            need(row["kind"] == q["kind"], "kind cannot be changed")
            need(q.get("expected_revision") == row["revision"], "revision conflict; read latest before modifying")
            # Preserve dependency graph on edits; a new candidate is used for new derivations.
            old_parents = {r[0] for r in self.db.execute("SELECT parent FROM edges WHERE child=?", (rid,))}
            need(set(parents) == old_parents, "derived_from cannot change on edit")
            rev = row["revision"] + 1
        else:
            need("expected_revision" not in q, "new records have no previous revision")
        status = "candidate" if q["kind"] in {"failure", "procedural", "skill_library"} or prov["source_type"] in {"agent_inferred", "teacher_critique"} else "active"
        body = {"title": q["title"], "content": content, "provenance": prov, "confidence": "source_attribution_only" if status == "active" else "unverified", "tags": tags, "files": files, "sensitivity": sensitivity, "consent_ref": q.get("consent_ref"), "derived_from": parents, "parent_revisions": parent_revisions}
        if "id" in q:
            self.db.execute("UPDATE records SET status=?,revision=?,body=?,updated=?,review=?,expires=? WHERE id=?", (status, rev, dump(body), now, now + review*86400, now + ttl*86400, rid))
        else:
            self.db.execute("INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,0)", (rid, scope, q["kind"], status, rev, dump(body), now, now, now + review*86400, now + ttl*86400))
            for parent in parents:
                self.db.execute("INSERT INTO edges VALUES(?,?)", (parent, rid))
        self.db.execute("INSERT INTO requests VALUES(?,?,?,?)", (q["idempotency_key"], digest, rid, rev))
        self.event("put", rid, rev)
        return {"id": rid, "revision": rev, "status": status, "replayed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default_home = Path(os.environ.get("CODEX_HOME") or Path.home()/".codex")
    parser.add_argument("--state-dir", default=str(default_home/"cognitive-runtime"/"state"))
    parser.add_argument("--request", help="UTF-8 JSON path; omit to read one object from stdin")
    args = parser.parse_args()
    runtime = None
    try:
        raw = Path(args.request).read_text(encoding="utf-8-sig") if args.request else sys.stdin.read(100000)
        q = json.loads(raw)
        runtime = Runtime(args.state_dir)
        result = runtime.request(q)
        print(dump({"ok": True, "result": result}))
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(dump({"ok": False, "error": str(exc)}))
        return 2
    finally:
        if runtime:
            runtime.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
