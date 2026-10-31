#!/usr/bin/env python3
"""Apply a downloaded review-page corrections file to scans waiting for review.

The review page's "Download corrections" saves every transcript on the page as
handwritten-corrections.json: {"files": [{"base": ..., "transcript": ...}]}.
Downloading it is the person's approval. For each entry whose base names a
record waiting in NEEDS_REVIEW, the record's transcript is replaced with the
corrected text, verbatim, and the base is printed so the watcher can route it.
Entries naming no waiting record (say, from an interactive /handwritten
session) are ignored, and if none match, nothing is printed.

usage: apply_corrections.py CORRECTIONS.json NEEDS_REVIEW_DIR
"""
import json, os, sys

corrections, waiting = sys.argv[1], sys.argv[2]
try:
    files = json.load(open(corrections, encoding="utf-8")).get("files", [])
except (OSError, ValueError, AttributeError):
    sys.exit(0)   # not a corrections file we can read: leave it alone

for entry in files:
    if not isinstance(entry, dict):
        continue
    base, text = entry.get("base"), entry.get("transcript")
    if not isinstance(base, str) or "/" in base or not isinstance(text, str):
        continue
    path = os.path.join(waiting, base + ".md")
    if not os.path.isfile(path):
        continue
    record = open(path, encoding="utf-8").read()
    head, sep, _ = record.partition("\n## Transcript\n")
    if not sep:
        continue
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + sep + "\n" + text.strip("\n") + "\n")
    print(base)
