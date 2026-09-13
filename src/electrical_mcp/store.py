import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

class Store:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS readings (
              id INTEGER PRIMARY KEY, company TEXT, device TEXT, metric TEXT,
              timestamp TEXT, payload TEXT);
            CREATE INDEX IF NOT EXISTS readings_lookup
              ON readings(company, device, timestamp);
            CREATE TABLE IF NOT EXISTS drafts (
              id TEXT PRIMARY KEY, company TEXT, key TEXT, device TEXT,
              issue TEXT, created_at TEXT, UNIQUE(company, key));
            CREATE TABLE IF NOT EXISTS audit (
              id INTEGER PRIMARY KEY, company TEXT, role TEXT, action TEXT,
              device TEXT, outcome TEXT, timestamp TEXT);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def audit(self, company, role, action, device, outcome):
        with self.connect() as db:
            db.execute("INSERT INTO audit VALUES (NULL,?,?,?,?,?,?)", (
                company, role, action, device, outcome, datetime.now(timezone.utc).isoformat()))

    def save_readings(self, company, device, readings):
        with self.connect() as db:
            db.executemany("INSERT INTO readings VALUES (NULL,?,?,?,?,?)", [
                (company, device, r["metric"], r["timestamp"], json.dumps(r)) for r in readings])

    def history(self, company, device, start, end, limit):
        with self.connect() as db:
            rows = db.execute("""SELECT payload FROM readings
                WHERE company=? AND device=? AND timestamp>=? AND timestamp<=?
                ORDER BY timestamp DESC, id DESC LIMIT ?""",
                (company, device, start, end, limit)).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    def draft(self, company, device, issue, key):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM drafts WHERE company=? AND key=?", (company, key)).fetchone()
            if row:
                if row["device"] != device or row["issue"] != issue:
                    raise ValueError("Idempotency key already used for different request")
            else:
                draft_id = str(uuid.uuid4())
                db.execute("INSERT INTO drafts VALUES (?,?,?,?,?,?)", (
                    draft_id, company, key, device, issue, datetime.now(timezone.utc).isoformat()))
                row = db.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        return {**dict(row), "status": "draft", "sent_to_external_system": False}

    def list_drafts(self, company, limit):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM drafts WHERE company=? ORDER BY created_at DESC LIMIT ?",
                              (company, limit)).fetchall()
        return [{**dict(r), "status": "draft", "sent_to_external_system": False} for r in rows]

    def audit_events(self, company, limit):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM audit WHERE company=? ORDER BY id DESC LIMIT ?",
                              (company, limit)).fetchall()
        return [dict(r) for r in rows]

    def metric_history(self, company, device, metric, start, end, limit):
        with self.connect() as db:
            rows = db.execute("""SELECT payload FROM readings
                WHERE company=? AND device=? AND metric=? AND timestamp>=? AND timestamp<=?
                ORDER BY timestamp DESC, id DESC LIMIT ?""",
                (company, device, metric, start, end, limit)).fetchall()
        return [json.loads(r["payload"]) for r in rows]
