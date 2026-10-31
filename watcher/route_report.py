#!/usr/bin/env python3
"""Add this run's per-capture outcomes to the What's new routing report.

Reads lines on stdin, one per capture, tab-separated:
    done    <record path>    <archive file>,<note>,<note>...
    failed  <record path>    <why>
and appends an entry for each to PENDING (a JSON list). build_html.py, run
right after, attaches the list to this run's What's new entry and removes the
file, so the report reads: source type, title, where it went (or why not),
with a link to the record in done/ or failed/.

Titles come from web pages and screenshots, so they are stored as data here
and escaped when the page renders them.

usage: route_report.py PENDING.json < lines
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_record import parse

pending = sys.argv[1]
try:
    report = json.load(open(pending, encoding="utf-8"))
except (OSError, ValueError):
    report = []

for line in sys.stdin:
    parts = line.rstrip("\n").split("\t")
    if len(parts) != 3:
        continue
    state, path, detail = parts
    header, _ = parse(path) if os.path.isfile(path) else ({}, "")
    header = header or {}
    kind = header.get("source_type") or ("web" if header.get("type") == "web-capture" else "capture")
    entry = {"type": kind, "title": str(header.get("title") or os.path.basename(path)),
             "state": state, "link": "file://" + os.path.abspath(path)}
    if state == "done":
        archive, *notes = [x for x in detail.split(",") if x]
        entry.update(archive=archive, notes=notes)
    else:
        entry["why"] = detail
    report.append(entry)

with open(pending, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
