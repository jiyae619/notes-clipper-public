#!/usr/bin/env python3
"""Check capture records against docs/capture-record.md (format capture/1).

usage: validate_record.py RECORD.md [...]
Prints each record's problems and exits 1 if any record has one. A web capture
from before capture/1 (type: web-capture, images:) is read as a web record.
"""
import json, os, re, sys

TYPES = {"web", "scan", "screenshot", "note"}
CATEGORIES = {"AI", "PM", "DESIGN", "CAREER"}


def parse(path):
    """Split a record into (header dict, body). Reads only the frontmatter
    block: the body is page text and may contain lines that look like fields."""
    text = open(path, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n?(.*)", text, re.S)
    if not m:
        return None, text
    header, key = {}, None
    for line in m.group(1).split("\n"):
        item = re.match(r"  - (.*)", line)
        if item and key:
            header.setdefault(key, []).append(item.group(1).strip())
            continue
        kv = re.match(r"([A-Za-z_]+):\s*(.*)", line)
        if not kv:
            continue
        key, value = kv.group(1), kv.group(2).strip()
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                value = value.strip('"')
        header[key] = value if value != "" else []
    return header, m.group(2)


def problems(path):
    h, body = parse(path)
    if h is None:
        return ["no frontmatter block"]
    out = []
    if "record" not in h and h.get("type") == "web-capture":   # before capture/1
        h = {**h, "record": "capture/1", "source_type": "web", "attachments": h.get("images", [])}
    if h.get("record") != "capture/1":
        out.append("record must be capture/1")
    kind = h.get("source_type")
    if kind not in TYPES:
        return out + [f"source_type must be one of {sorted(TYPES)}"]
    if not isinstance(h.get("title"), str) or not h["title"].strip():
        out.append("title is missing")
    if not re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d", str(h.get("captured", ""))):
        out.append("captured must be YYYY-MM-DD HH:MM")

    files = h.get("attachments", [])
    if not isinstance(files, list):
        out.append("attachments must be a list")
        files = []
    here = os.path.dirname(os.path.abspath(path))
    out += [f"attachment {f} is not beside the record" for f in files if not os.path.isfile(os.path.join(here, f))]

    src = str(h.get("source", ""))
    if kind == "web" and not re.match(r"https?://", src):
        out.append("a web record's source must be the page URL")
    if kind == "note" and not (re.match(r"https?://", src) or src == "pasted"):
        out.append("a note record's source must be a URL or 'pasted'")
    if kind == "scan":
        m = re.fullmatch(r"scan: (.+)", src)
        if not m or m.group(1) not in files:
            out.append("a scan record's source must be 'scan: <file>', with that file in attachments")
        if h.get("review") != "transcript":
            out.append("a scan record needs review: transcript (transcripts are approved before routing)")
        if "## Transcript" not in body:
            out.append("a scan record needs a ## Transcript section")
    if kind == "screenshot":
        if not re.fullmatch(r"(photos|file): .+", src):
            out.append("a screenshot record's source must be 'photos: <uuid>' or 'file: <name>'")
        if h.get("category") not in CATEGORIES:
            out.append(f"a screenshot record's category must be one of {sorted(CATEGORIES)}")
        if not files:
            out.append("a screenshot record must attach its image")
    if kind != "scan" and "review" in h:
        out.append("only scan records take review")
    if "video_id" in h and (kind != "web" or not re.fullmatch(r"[\w-]{6,20}", str(h["video_id"]))):
        out.append("video_id is for web records and must be a YouTube id")
    if kind in ("web", "note") and not body.strip():
        out.append("the body (the verbatim content) is empty")
    return out


if __name__ == "__main__":
    bad = 0
    for path in sys.argv[1:]:
        found = problems(path)
        bad += bool(found)
        print(("ok   " if not found else "FAIL ") + path)
        for f in found:
            print("       - " + f)
    sys.exit(1 if bad else 0)
