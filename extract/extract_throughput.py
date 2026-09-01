#!/usr/bin/env python3
"""Canonical throughput extraction for the Kiln doc (A4 pipeline fix).

Reads the banked stack-bench result summaries (stable, self-documenting with
schema_version/env/date) and copies the headline tok/s numbers with source
hashes. Numbers are COPIED, never recomputed — the summaries are the
instrument output.
"""
import hashlib
import json
import os
from datetime import datetime, timezone

SOURCES = [
    "results/LIVE-PARITY-20260830.json",
    "results/hq64k/fork-summary.json",
    "results/hq64k/stock-summary.json",
]
ROOT = os.path.expanduser("~/workspaces/stack-bench")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kiln-throughput-extract.json")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def headline(summary):
    d = summary.get("decode") or {}
    p = summary.get("prefill") or {}
    buckets = p.get("by_measured_prompt_n") or {}
    return {
        "decode_tps": d.get("decode_tps") or d.get("mean_tps"),
        "decode_range": [d.get("min"), d.get("max")] if d.get("min") is not None else None,
        "prefill_by_context": {k: round(v.get("mean_tps", 0), 1) for k, v in buckets.items()},
        "wall_s_total": summary.get("wall_s_total"),
        "env_note": (summary.get("env") or {}).get("tool_version", ""),
    }


def main():
    payload = {}
    source_meta = []
    for rel in SOURCES:
        path = os.path.join(ROOT, rel)
        with open(path) as f:
            summary = json.load(f)
        payload[rel] = headline(summary)
        source_meta.append({"file": rel, "sha256": sha256(path)})
    doc = {
        "schema_version": 1,
        "extracted_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "headline fields copied verbatim from banked stack-bench summaries; never recomputed",
        "sources": source_meta,
        "results": payload,
    }
    with open(OUT, "w") as f:
        json.dump(doc, f, indent=1)
    print(f"{OUT}: {len(payload)} summaries copied")


if __name__ == "__main__":
    main()
