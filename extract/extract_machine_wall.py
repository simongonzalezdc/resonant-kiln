#!/usr/bin/env python3
"""Canonical machine-wall extraction for the Kiln doc (A4 pipeline fix).

Reads every ~/workspaces/delegation-bench/results/*.jsonl (stable, dated),
computes per-campaign trial counts, machine minutes, and per-cell medians,
and emits kiln-extract-20260901.json WITH a full metadata block.

Method (the formula, written down): minutes = sum(wall_ms)/60000 per
campaign; cell medians over wall_ms/1000. Rerun rule: any upstream change ->
regenerate + diff; never hand-edit the JSON.
"""
import glob
import hashlib
import json
import os
import statistics
import sys
from datetime import datetime, timezone

SOURCES_GLOB = os.path.expanduser("~/workspaces/delegation-bench/results/*.jsonl")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kiln-extract-20260901.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    sources = sorted(glob.glob(SOURCES_GLOB))
    if not sources:
        sys.exit("no result logs found")
    payload = {}
    source_meta = []
    for path in sources:
        recs = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if isinstance(r, dict) and isinstance(r.get("wall_ms"), (int, float)):
                    recs.append(r)
        if not recs:
            continue
        name = os.path.basename(path)[:-6]
        cells = {}
        for r in recs:
            cells.setdefault(str(r.get("cell", "?")), []).append(r["wall_ms"] / 1000.0)
        payload[name] = {
            "trials": len(recs),
            "minutes": round(sum(r["wall_ms"] for r in recs) / 60000.0, 2),
            "cells": {
                cid: {"n": len(ws), "median_s": round(statistics.median(ws), 1),
                      "max_s": round(max(ws), 1)}
                for cid, ws in sorted(cells.items())
            },
        }
        source_meta.append({
            "file": os.path.basename(path),
            "sha256": sha256(path),
            "rows": len(recs),
        })
    doc = {
        "schema_version": 2,
        "extracted_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": ("minutes = sum(wall_ms)/60000 per campaign; cell medians over "
                   "wall_ms/1000; rows must be dicts with numeric wall_ms"),
        "sources": source_meta,
        "total_trials": sum(p["trials"] for p in payload.values()),
        "campaigns": payload,
    }
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"{OUT}: {doc['total_trials']} trials across {len(payload)} campaigns")


if __name__ == "__main__":
    main()
