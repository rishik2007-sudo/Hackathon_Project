"""SQLite store: the policy table and the decision log.

policies   seeded from policies.json, so retrieval can be filtered in SQL later
decisions  every answer we gave, with the policies it rested on, for auditing
"""

import json
import os
import sqlite3
from datetime import datetime

HERE = os.path.dirname(__file__)
PATH = os.path.join(HERE, "policylens.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS policies (
    policy_id      TEXT NOT NULL,
    version        TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    region         TEXT NOT NULL,
    department     TEXT NOT NULL,
    vendor         TEXT NOT NULL,
    supersedes     TEXT,
    title          TEXT NOT NULL,
    content        TEXT NOT NULL,
    PRIMARY KEY (policy_id, version)
);

CREATE INDEX IF NOT EXISTS idx_policies_scope
    ON policies (region, department, effective_date);

CREATE TABLE IF NOT EXISTS decisions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    asked_at   TEXT NOT NULL,
    question   TEXT NOT NULL,
    context    TEXT NOT NULL,
    verdict    TEXT NOT NULL,
    reason     TEXT NOT NULL,
    sources    TEXT NOT NULL,
    discarded  TEXT NOT NULL
);
"""


def connect():
    con = sqlite3.connect(PATH)
    con.row_factory = sqlite3.Row
    return con


def seed():
    """Create the tables and load policies.json into them. Safe to run repeatedly."""
    policies = json.load(open(os.path.join(HERE, "policies.json"), encoding="utf-8"))
    con = connect()
    con.executescript(SCHEMA)
    con.executemany(
        """INSERT OR REPLACE INTO policies
           (policy_id, version, effective_date, region, department, vendor,
            supersedes, title, content)
           VALUES (:policy_id, :version, :effective_date, :region, :department,
                   :vendor, :supersedes, :title, :content)""",
        policies,
    )
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM policies").fetchone()[0]
    con.close()
    return n


def log(question, result):
    """Record one decision so it can be audited later."""
    con = connect()
    con.executescript(SCHEMA)
    con.execute(
        """INSERT INTO decisions
           (asked_at, question, context, verdict, reason, sources, discarded)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().isoformat(timespec="seconds"),
            question,
            json.dumps(result["context"]),
            result["verdict"],
            result["reason"],
            json.dumps(result["sources"]),
            json.dumps(result["dropped"]),
        ),
    )
    con.commit()
    con.close()


def history(limit=20):
    con = connect()
    con.executescript(SCHEMA)
    rows = con.execute(
        "SELECT asked_at, question, verdict, sources FROM decisions ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    con.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    print(f"seeded {seed()} policies into {PATH}")
