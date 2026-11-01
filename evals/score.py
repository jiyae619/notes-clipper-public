#!/usr/bin/env python3
"""Score one eval run against the set's expected.json, save the result and
compare it with the previous run of the same set. Deterministic: it only
reads what the watcher left behind (watcher.log, done/, the notes, the
faithfulness files). The judging of summaries happened in the run itself.

usage: score.py SET_DIR SANDBOX RESULTS_DIR MODEL
"""
import datetime, glob, json, os, re, sys

set_dir, sb, results_dir, model = sys.argv[1:5]
expected = json.load(open(os.path.join(set_dir, "expected.json"), encoding="utf-8"))
proc = os.path.join(sb, "Downloads", "notes-inbox-processed")
notes_dir = os.path.join(sb, "notes", "Handwritten", "notes")
archive_dir = os.path.join(sb, "notes", "Handwritten", "archive")
log = open(os.path.join(proc, "watcher.log"), encoding="utf-8", errors="replace").read()
notes = {f[:-len("_note.md")]: open(os.path.join(notes_dir, f), encoding="utf-8").read()
         for f in os.listdir(notes_dir) if f.endswith("_note.md")}
start = {f[:-len("_note.md")]: open(os.path.join(set_dir, "notes", f), encoding="utf-8").read()
         for f in os.listdir(os.path.join(set_dir, "notes")) if f.endswith("_note.md")}

rows, totals = {}, {"checks": 0, "passed": 0}
for stem, exp in expected.items():
    r = {"probes": exp.get("probes", ""), "checks": {}}
    done = os.path.exists(os.path.join(proc, "done", stem + ".md"))
    r["checks"]["filed"] = done
    m = re.search(r"✓ routed: " + re.escape(stem) + r"\.md → (.*)", log)
    went = [x for x in (m.group(1).split(",")[1:] if m else []) if x]
    r["notes"] = went
    for n in exp.get("notes", []):
        r["checks"][f"went to {n}"] = n in went
    targets = [notes.get(n, "") for n in (exp.get("notes") or went)]
    for fact in exp.get("facts", []):
        r["checks"][f"keeps '{fact}'"] = any(fact.lower() in t.lower() for t in targets)
    if exp.get("flag"):
        r["checks"][f"flagged '{exp['flag']}'"] = any(exp["flag"] in t for t in targets)
    for bad in exp.get("forbid", []):
        r["checks"][f"no '{bad}' anywhere"] = not any(bad in t for t in notes.values())
    if exp.get("keep_files"):
        # Nothing the set started with may be lost: every starting line survives,
        # and the archive keeps the capture's text word for word.
        r["checks"]["no starting note lost a line"] = all(
            all(l in notes.get(n, "") for l in body.splitlines() if l.strip()) for n, body in start.items())
        # This capture's own archive file (the one the log says it went to)
        # must hold its whole text, whitespace aside.
        flat = lambda t: " ".join(t.split())
        own = os.path.join(archive_dir, m.group(1).split(",")[0]) if m else ""
        src = open(os.path.join(set_dir, "captures", stem + ".md"), encoding="utf-8").read().split("---", 2)[2]
        r["checks"]["archived word for word"] = bool(own) and os.path.isfile(own) and \
            flat(src) in flat(open(own, encoding="utf-8").read())
    try:
        f = json.load(open(os.path.join(proc, "done", stem + ".faithfulness.json"), encoding="utf-8"))
        r["faithfulness"] = f["score"]; r["unsupported"] = f.get("unsupported", [])
    except (OSError, ValueError, KeyError):
        r["faithfulness"] = None
    q = re.findall(r"proposals: \+(\d+) quiz", log)
    r["passed"] = sum(r["checks"].values()); r["total"] = len(r["checks"])
    totals["checks"] += r["total"]; totals["passed"] += r["passed"]
    rows[stem] = r

faith = [r["faithfulness"] for r in rows.values() if r["faithfulness"]]
result = {"set": os.path.basename(os.path.normpath(set_dir)), "model": model,
          "at": datetime.datetime.now().isoformat(timespec="seconds"),
          "checks_passed": totals["passed"], "checks_total": totals["checks"],
          "faithfulness_mean": round(sum(faith) / len(faith), 2) if faith else None,
          "quiz_added": sum(int(x) for x in re.findall(r"proposals: \+(\d+) quiz", log)),
          "captures": rows}

os.makedirs(results_dir, exist_ok=True)
previous = sorted(glob.glob(os.path.join(results_dir, "*.json")))
prev = json.load(open(previous[-1], encoding="utf-8")) if previous else None
out = os.path.join(results_dir, result["at"].replace(":", "") + ".json")
json.dump(result, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

for stem, r in rows.items():
    mark = "✓" if r["passed"] == r["total"] else "✗"
    fs = f"{r['faithfulness']}/5" if r["faithfulness"] else "—"
    print(f"{mark} {stem:24} {r['passed']}/{r['total']} checks  faithfulness {fs}  → {', '.join(r['notes']) or '(none)'}")
    for k, ok in r["checks"].items():
        if not ok:
            print(f"      ✗ {k}")
    for u in r.get("unsupported") or []:
        print(f"      ? not in source: {u}")
print(f"\n{result['set']} · {model}: {totals['passed']}/{totals['checks']} checks, "
      f"faithfulness mean {result['faithfulness_mean']}, {result['quiz_added']} quiz questions")
if prev:
    print(f"previous ({prev['at']}, {prev['model']}): {prev['checks_passed']}/{prev['checks_total']} checks, "
          f"faithfulness mean {prev['faithfulness_mean']}")
    for stem, r in rows.items():
        p = prev["captures"].get(stem)
        if p and p["passed"] > r["passed"]:
            print(f"  ↓ {stem} regressed: {p['passed']} → {r['passed']} checks")
print(f"saved {out}")
sys.exit(0 if totals["passed"] == totals["checks"] else 1)
