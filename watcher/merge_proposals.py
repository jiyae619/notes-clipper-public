#!/usr/bin/env python3
"""Apply quiz and map-keyword proposals from unattended routing runs.

The unattended Claude run reads web page text, so it must not be able to write
code that later runs: Claude Code already refuses its writes under ~/.claude,
and build_html.py runs on every notes rebuild. So Claude only writes data, one
<stem>.proposals.json per capture, and this script, run by the watcher, checks
every field and applies what passes:
  - quiz entries are appended to quiz-bank.json with ids assigned here;
  - keywords are appended to glossary-extra.json, which build_html.py reads as data.
Anything malformed is dropped with a reason printed, never guessed at.

usage: merge_proposals.py --refs DIR --notes DIR PROPOSALS.json [...]
"""
import argparse, ast, datetime, json, os, re, shutil, sys, tempfile
from collections import Counter

p = argparse.ArgumentParser()
p.add_argument("--refs", required=True, help="the handwritten skill's references/ dir")
p.add_argument("--notes", required=True, help="the vault's Handwritten/notes/ dir")
p.add_argument("proposals", nargs="+")
args = p.parse_args()

bank_path = os.path.join(args.refs, "quiz-bank.json")
extra_path = os.path.join(args.refs, "glossary-extra.json")


def write_atomic(path, data):
    """Write JSON so a crash mid-write can't leave a half-written bank."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def glossary_in_code():
    """Read the GLOSSARY list from build_html.py as a literal; never execute it."""
    src = open(os.path.join(args.refs, "build_html.py"), encoding="utf-8").read()
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "GLOSSARY" for t in node.targets):
            return ast.literal_eval(node.value)
    return []


notes = {f[: -len("_note.md")]: open(os.path.join(args.notes, f), encoding="utf-8").read().lower()
         for f in os.listdir(args.notes) if f.endswith("_note.md")}
bank = json.load(open(bank_path, encoding="utf-8"))
extra = json.load(open(extra_path, encoding="utf-8")) if os.path.exists(extra_path) else []
known_kw = {k.lower() for k in glossary_in_code() + extra}
seen_q = {re.sub(r"\s+", " ", q["q"]).strip().lower() for q in bank}

# Keep each note's existing id prefix (AI_evals -> "evals"); a note with no
# questions yet gets one from its stem.
prefix_of = {}
for note, c in Counter((q["note"], q["id"].rsplit("-", 1)[0]) for q in bank).most_common():
    prefix_of.setdefault(note[0], note[1])


def next_id(note):
    pre = prefix_of.setdefault(note, note.lower().replace("_", "-"))
    nums = [int(q["id"].rsplit("-", 1)[1]) for q in bank
            if q["id"].rsplit("-", 1)[0] == pre and q["id"].rsplit("-", 1)[1].isdigit()]
    return f"{pre}-{max(nums, default=0) + 1:02d}"


def quiz_problem(e):
    if not isinstance(e, dict):
        return "not an object"
    if e.get("note") not in notes:
        return f"note {e.get('note')!r} isn't a topic note"
    for k in ("topic", "src", "q", "explain"):
        if not isinstance(e.get(k), str) or not e[k].strip():
            return f"missing {k}"
    opts = e.get("opts")
    if not (isinstance(opts, list) and len(opts) == 4 and all(isinstance(o, str) and o.strip() for o in opts)
            and len({o.strip().lower() for o in opts}) == 4):
        return "needs exactly 4 distinct options"
    if not (isinstance(e.get("a"), int) and 0 <= e["a"] <= 3):
        return "answer index must be 0-3"
    if re.sub(r"\s+", " ", e["q"]).strip().lower() in seen_q:
        return "same question is already in the bank"
    return None


def keyword_problem(k):
    if not isinstance(k, str) or not re.fullmatch(r"[\w][\w .+&/-]{1,39}", k.strip()):
        return "not a short plain term"
    if k.strip().lower() in known_kw:
        return "already on the map"
    # build_html.py links a keyword to a note by whole-word match. One no note
    # contains would be a node with no edges; one most notes contain (say
    # "design") links everything, so it distinguishes nothing.
    pattern = r"\b" + re.escape(k.strip().lower()) + r"\b"
    hits = sum(1 for body in notes.values() if re.search(pattern, body))
    if hits == 0:
        return "doesn't appear in any note"
    if len(notes) >= 4 and hits > len(notes) / 2:   # with fewer notes, "most" means nothing
        return f"too common to link anything (in {hits} of {len(notes)} notes)"
    return None


added_q, added_k, dropped = [], [], []
for path in args.proposals:
    try:
        prop = json.load(open(path, encoding="utf-8"))
    except (OSError, ValueError) as err:
        dropped.append(f"{os.path.basename(path)}: unreadable ({err})")
        continue
    for e in prop.get("quiz", []) if isinstance(prop, dict) else []:
        why = quiz_problem(e)
        if why:
            dropped.append(f"quiz {str(e.get('q', ''))[:50]!r}: {why}" if isinstance(e, dict) else f"quiz entry: {why}")
            continue
        entry = {"id": next_id(e["note"]), **{k: e[k] for k in ("note", "topic", "src")},
                 **{k: e[k] for k in ("type", "level") if isinstance(e.get(k), str)},
                 "q": e["q"].strip(), "opts": [o.strip() for o in e["opts"]], "a": e["a"], "explain": e["explain"].strip()}
        bank.append(entry)
        seen_q.add(re.sub(r"\s+", " ", entry["q"]).lower())
        added_q.append(entry["id"])
    for k in prop.get("keywords", []) if isinstance(prop, dict) else []:
        why = keyword_problem(k)
        if why:
            dropped.append(f"keyword {k!r}: {why}")
            continue
        extra.append(k.strip())
        known_kw.add(k.strip().lower())
        added_k.append(k.strip())

if added_q:
    shutil.copy2(bank_path, bank_path + ".bak-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    write_atomic(bank_path, bank)
if added_k:
    write_atomic(extra_path, extra)
print(f"  proposals: +{len(added_q)} quiz {added_q}, +{len(added_k)} keywords {added_k}, {len(dropped)} dropped")
for d in dropped:
    print(f"    dropped {d}")
