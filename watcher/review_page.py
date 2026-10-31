#!/usr/bin/env python3
"""Build the review page for the scans waiting in NEEDS_REVIEW.

Reuses the handwritten skill's build_review.py, which reads a folder laid out as
  staging/<base>.md    the transcript text
  assets/<base>.jpg    a picture of the page (first page of a PDF)
  lowconf.json         [{base, title, topic, low: [...]}]
and writes review.html there. This lays that folder out in REVIEW_DIR from the
waiting capture records and their <base>.lowconf.json. With nothing waiting it
removes the page, so an old one is never mistaken for pending work.

usage: review_page.py NEEDS_REVIEW_DIR REVIEW_DIR BUILD_REVIEW_PY
"""
import glob, json, os, re, shutil, subprocess, sys

waiting, review, build_review = sys.argv[1:4]
for sub in ("staging", "assets"):
    shutil.rmtree(os.path.join(review, sub), ignore_errors=True)
    os.makedirs(os.path.join(review, sub))

entries = []
for record in sorted(glob.glob(os.path.join(waiting, "*.md"))):
    base = os.path.basename(record)[:-3]
    text = open(record, encoding="utf-8").read()
    _, _, transcript = text.partition("\n## Transcript\n")
    with open(os.path.join(review, "staging", base + ".md"), "w", encoding="utf-8") as f:
        f.write(transcript.strip("\n") + "\n")
    scan = re.search(r'^source: *"scan: (.+)"$', text, re.M)
    if scan:
        subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "1500", os.path.join(waiting, scan.group(1)),
                        "--out", os.path.join(review, "assets", base + ".jpg")], capture_output=True)
    try:
        low = json.load(open(os.path.join(waiting, base + ".lowconf.json"), encoding="utf-8"))
    except (OSError, ValueError):
        low = {}
    entries.append({"base": base, "title": low.get("title", base), "topic": low.get("topic", "other"),
                    "low": [r for r in low.get("low", []) if isinstance(r, dict) and r.get("reads_as")]})

page = os.path.join(review, "review.html")
if not entries:
    if os.path.exists(page):
        os.remove(page)
    sys.exit(0)
json.dump(entries, open(os.path.join(review, "lowconf.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
subprocess.run([sys.executable, build_review, review], check=True, capture_output=True)
print(page)
