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
            CREATE INDEX IF NOT EXISTS readings_metric_lookup
              ON readings(company, device, metric, timestamp DESC, id DESC);
            CREATE TABLE IF NOT EXISTS drafts (
              id TEXT PRIMARY KEY, company TEXT, key TEXT, device TEXT,
              issue TEXT, created_at TEXT, UNIQUE(company, key));
            CREATE TABLE IF NOT EXISTS audit (
              id INTEGER PRIMARY KEY, company TEXT, role TEXT, action TEXT,
              device TEXT, outcome TEXT, timestamp TEXT);
            CREATE INDEX IF NOT EXISTS audit_company_lookup ON audit(company, id DESC);
            CREATE INDEX IF NOT EXISTS drafts_company_lookup ON drafts(company, created_at DESC);
            CREATE TABLE IF NOT EXISTS device_groups (
              id INTEGER PRIMARY KEY, company TEXT, group_id TEXT,
              name TEXT, description TEXT, parent_group_id TEXT,
              device_ids TEXT, metadata TEXT, created_at TEXT,
              UNIQUE(company, group_id));
            CREATE TABLE IF NOT EXISTS scheduled_tasks (
              id INTEGER PRIMARY KEY, company TEXT, task_id TEXT,
              name TEXT, task_type TEXT, schedule_cron TEXT,
              interval_seconds INTEGER, enabled INTEGER, config TEXT,
              last_run TEXT, next_run TEXT, run_count INTEGER,
              last_status TEXT, created_at TEXT,
              UNIQUE(company, task_id));
            CREATE TABLE IF NOT EXISTS alert_rules (
              id INTEGER PRIMARY KEY, company TEXT, rule_id TEXT,
              name TEXT, description TEXT, device_id TEXT,
              metric TEXT, condition TEXT, threshold_value REAL,
              threshold_value_upper REAL, severity TEXT, enabled INTEGER,
              cooldown_seconds INTEGER, consecutive_breaches INTEGER,
              notification_channels TEXT, tags TEXT,
              UNIQUE(company, rule_id));
            CREATE TABLE IF NOT EXISTS alerts (
              id INTEGER PRIMARY KEY, company TEXT, alert_id TEXT,
              rule_id TEXT, rule_name TEXT, device_id TEXT,
              metric TEXT, severity TEXT, state TEXT, message TEXT,
              current_value REAL, threshold_value REAL,
              triggered_at TEXT, acknowledged_at TEXT, resolved_at TEXT,
              acknowledged_by TEXT, metadata TEXT);
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

    def save_device_groups(self, company, groups):
        with self.connect() as db:
            db.execute("DELETE FROM device_groups WHERE company=?", (company,))
            db.executemany("INSERT INTO device_groups VALUES (NULL,?,?,?,?,?,?,?,?)", [
                (company, g["group_id"], g["name"], g.get("description", ""),
                 g.get("parent_group_id"), json.dumps(g.get("device_ids", [])),
                 json.dumps(g.get("metadata", {})), g.get("created_at", datetime.now(timezone.utc).isoformat()))
                for g in groups])

    def get_device_groups(self, company):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM device_groups WHERE company=?", (company,)).fetchall()
        result = []
        for r in rows:
            result.append({
                "group_id": r["group_id"], "name": r["name"],
                "description": r["description"], "parent_group_id": r["parent_group_id"],
                "device_ids": json.loads(r["device_ids"]), "metadata": json.loads(r["metadata"]),
                "created_at": r["created_at"],
            })
        return result

    def save_scheduled_tasks(self, company, tasks):
        with self.connect() as db:
            db.execute("DELETE FROM scheduled_tasks WHERE company=?", (company,))
            db.executemany("INSERT INTO scheduled_tasks VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                (company, t["task_id"], t["name"], t["task_type"], t.get("schedule_cron"),
                 t.get("interval_seconds"), 1 if t.get("enabled", True) else 0,
                 json.dumps(t.get("config", {})), t.get("last_run"), t.get("next_run"),
                 t.get("run_count", 0), t.get("last_status", "pending"),
                 t.get("created_at", datetime.now(timezone.utc).isoformat()))
                for t in tasks])

    def get_scheduled_tasks(self, company):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM scheduled_tasks WHERE company=?", (company,)).fetchall()
        result = []
        for r in rows:
            result.append({
                "task_id": r["task_id"], "name": r["name"], "task_type": r["task_type"],
                "schedule_cron": r["schedule_cron"], "interval_seconds": r["interval_seconds"],
                "enabled": bool(r["enabled"]), "config": json.loads(r["config"]),
                "last_run": r["last_run"], "next_run": r["next_run"],
                "run_count": r["run_count"], "last_status": r["last_status"],
                "created_at": r["created_at"],
            })
        return result

    def save_alert_rules(self, company, rules):
        with self.connect() as db:
            db.execute("DELETE FROM alert_rules WHERE company=?", (company,))
            db.executemany("INSERT INTO alert_rules VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                (company, r["rule_id"], r["name"], r.get("description", ""),
                 r.get("device_id"), r["metric"], r["condition"],
                 r.get("threshold_value"), r.get("threshold_value_upper"),
                 r.get("severity", "warning"), 1 if r.get("enabled", True) else 0,
                 r.get("cooldown_seconds", 300), r.get("consecutive_breaches", 1),
                 json.dumps(r.get("notification_channels", [])),
                 json.dumps(r.get("tags", {})))
                for r in rules])

    def get_alert_rules(self, company):
        with self.connect() as db:
            rows = db.execute("SELECT * FROM alert_rules WHERE company=?", (company,)).fetchall()
        result = []
        for r in rows:
            result.append({
                "rule_id": r["rule_id"], "name": r["name"], "description": r["description"],
                "device_id": r["device_id"], "metric": r["metric"], "condition": r["condition"],
                "threshold_value": r["threshold_value"], "threshold_value_upper": r["threshold_value_upper"],
                "severity": r["severity"], "enabled": bool(r["enabled"]),
                "cooldown_seconds": r["cooldown_seconds"],
                "consecutive_breaches": r["consecutive_breaches"],
                "notification_channels": json.loads(r["notification_channels"]),
                "tags": json.loads(r["tags"]),
            })
        return result

    def save_alert(self, company, alert):
        with self.connect() as db:
            db.execute("DELETE FROM alerts WHERE company=? AND alert_id=?", (company, alert["alert_id"]))
            db.execute("""INSERT INTO alerts VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                company, alert["alert_id"], alert["rule_id"], alert["rule_name"],
                alert["device_id"], alert["metric"], alert["severity"],
                alert["state"], alert["message"], alert["current_value"],
                alert.get("threshold_value"), alert["triggered_at"],
                alert.get("acknowledged_at"), alert.get("resolved_at"),
                alert.get("acknowledged_by"), json.dumps(alert.get("metadata", {}))))

    def get_alerts(self, company, state=None, limit=100):
        with self.connect() as db:
            if state:
                rows = db.execute("SELECT * FROM alerts WHERE company=? AND state=? ORDER BY id DESC LIMIT ?",
                                  (company, state, limit)).fetchall()
            else:
                rows = db.execute("SELECT * FROM alerts WHERE company=? ORDER BY id DESC LIMIT ?",
                                  (company, limit)).fetchall()
        result = []
        for r in rows:
            result.append({
                "alert_id": r["alert_id"], "rule_id": r["rule_id"],
                "rule_name": r["rule_name"], "device_id": r["device_id"],
                "metric": r["metric"], "severity": r["severity"],
                "state": r["state"], "message": r["message"],
                "current_value": r["current_value"],
                "threshold_value": r["threshold_value"],
                "triggered_at": r["triggered_at"],
                "acknowledged_at": r["acknowledged_at"],
                "resolved_at": r["resolved_at"],
                "acknowledged_by": r["acknowledged_by"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
            })
        return result

    def latest_readings(self, company, device, metrics):
        # One indexed seek per supported metric; never scan all device history.
        with self.connect() as db:
            rows = [db.execute("""SELECT payload FROM readings
                WHERE company=? AND device=? AND metric=?
                ORDER BY timestamp DESC, id DESC LIMIT 1""", (company, device, metric)).fetchone()
                for metric in metrics]
        return [json.loads(r["payload"]) for r in rows if r is not None]

    def get_draft(self, company, draft_id):
        with self.connect() as db:
            row = db.execute("SELECT * FROM drafts WHERE company=? AND id=?", (company, draft_id)).fetchone()
        return {**dict(row), "status": "draft", "sent_to_external_system": False} if row else None
