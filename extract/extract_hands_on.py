#!/usr/bin/env python3
"""Canonical hands-on-minutes extraction for the Kiln doc (A4 pipeline fix,
A1 recompute correction: blocks split at local midnight).

Reads the LOCAL AGENT-SESSION DATABASE (read-only URI), keeps HUMAN turns
only, clusters turns within 5 minutes into active blocks, splits blocks at
the local-midnight boundary so each day keeps its own minutes, and emits
per-day hands-on minutes with a PINNED db_cutoff_utc so reruns compare.

Turn filter (exact): message.role == 'user' AND NOT metadata.visibility ==
'model-only' AND metadata.source NOT IN {'todo_reminder','system_reminder'}.
Block rule: turns with gaps <= 300s join one block; blocks split at local
midnight; each segment's minutes = max(segment span, 1.0); single-turn block
= 1.0. Day: America/Los_Angeles. Span-counting includes idle gaps under 5
minutes inside a block — stated openly in the published method.
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DB = "file:" + os.path.expanduser("~/.zcode/cli/db/db.sqlite") + "?mode=ro"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kiln-hands-on-extract-20260901.json")
GAP_MS = 5 * 60 * 1000
LA = ZoneInfo("America/Los_Angeles")


def day_of(ms):
    return datetime.fromtimestamp(ms / 1000, tz=LA).date().isoformat()


def add_segment(per_day, stamps, a, b):
    d = per_day.setdefault(day_of(stamps[a]), {"minutes": 0.0, "blocks": 0, "turns": 0})
    d["minutes"] += (stamps[b] - stamps[a]) / 60000.0 if b > a else 1.0


def main():
    # --cutoff-ms pins the extraction to a frozen point (C5 blocker fix):
    # reruns at the same cutoff reproduce the same extract byte-for-byte;
    # without it, the live MAX(time_created) drifts with every new session.
    cutoff_ms = None
    args = sys.argv[1:]
    if "--cutoff-ms" in args:
        cutoff_ms = int(args[args.index("--cutoff-ms") + 1])
    db = sqlite3.connect(DB, uri=True)
    if cutoff_ms is None:
        cutoff_ms, = db.execute("SELECT MAX(time_created) FROM message").fetchone()
    rows = db.execute(
        "SELECT time_created, data FROM message "
        "WHERE json_extract(data,'$.role')='user' AND time_created <= ?",
        (cutoff_ms,),
    ).fetchall()
    human = []
    for t, data in rows:
        try:
            d = json.loads(data)
        except ValueError:
            continue
        meta = d.get("metadata") or {}
        if meta.get("visibility") == "model-only":
            continue
        if meta.get("source") in ("todo_reminder", "system_reminder"):
            continue
        human.append(t)
    human.sort()
    per_day = {}
    i = 0
    while i < len(human):
        j = i
        while j + 1 < len(human) and human[j + 1] - human[j] <= GAP_MS:
            j += 1
        seg_start = i
        for k in range(i, j):
            if day_of(human[k]) != day_of(human[k + 1]):
                add_segment(per_day, human, seg_start, k)
                seg_start = k + 1
        add_segment(per_day, human, seg_start, j)
        for k in range(i, j + 1):
            per_day[day_of(human[k])]["turns"] += 1
        per_day[day_of(human[i])]["blocks"] += 1
        i = j + 1
    doc = {
        "schema_version": 3,
        "extracted_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "db_cutoff_utc": datetime.fromtimestamp(cutoff_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": {
            "clustering_gap_min": 5,
            "day_timezone": "America/Los_Angeles",
            "day_split": "blocks split at local midnight; each side keeps its own minutes",
            "turn_filter": "role=user; exclude metadata.visibility=model-only; exclude metadata.source in {todo_reminder, system_reminder}",
            "span_rule": "segment minutes = max(segment span,1.0); single-turn block = 1.0; idle gaps under 5 min count as active",
        },
        "human_turns": len(human),
        "days": {d: {k: (round(v, 1) if k == "minutes" else v) for k, v in s.items()}
                 for d, s in sorted(per_day.items())},
    }
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"{OUT}: {len(human)} human turns, cutoff {doc['db_cutoff_utc']}")


if __name__ == "__main__":
    main()
