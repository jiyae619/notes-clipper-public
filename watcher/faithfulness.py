#!/usr/bin/env python3
"""The deterministic half of the faithfulness check (the judging is Claude's,
see check-faithfulness.md).

  faithfulness.py added BEFORE AFTER
      Print every line the topic notes gained between two copies of the
      notes folder (new notes count in full), for the checker's prompt.
  faithfulness.py apply DONE_DIR STEM... < checker's reply
      Read the checker's JSON, keep only well-formed entries for the
      captures named, write each to DONE_DIR/<stem>.faithfulness.json (which
      route_report.py attaches to What's new) and log a line per capture.

The reply comes from a model that read web text, so it is data: fields are
type-checked and trimmed, and anything malformed is dropped, never guessed at.
Report only: nothing here blocks or changes a capture.
"""
import difflib, json, os, re, sys


def added(before, after):
    out = []
    for fn in sorted(os.listdir(after)):
        if not fn.endswith(".md"):
            continue
        new = open(os.path.join(after, fn), encoding="utf-8", errors="replace").read().splitlines()
        old_path = os.path.join(before, fn)
        old = open(old_path, encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(old_path) else []
        lines = [l[1:] for l in difflib.unified_diff(old, new, lineterm="", n=0)
                 if l.startswith("+") and not l.startswith("+++") and l[1:].strip()]
        if lines:
            out.append(f"--- {fn}" + (" (new note)" if not old else ""))
            out.extend(lines)
    print("\n".join(out))


def clean_list(v, limit=5):
    return [str(x).strip()[:300] for x in v if isinstance(x, str) and x.strip()][:limit] if isinstance(v, list) else []


def apply(done_dir, stems):
    reply = sys.stdin.read()
    m = re.search(r"\{.*\}", reply, re.S)
    try:
        data = json.loads(m.group(0)) if m else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        print("  faithfulness: the checker's reply wasn't JSON; nothing recorded")
        return 1
    for stem in stems:
        e = data.get(stem)
        if not isinstance(e, dict) or not isinstance(e.get("score"), int) or not 1 <= e["score"] <= 5:
            print(f"  faithfulness: no usable result for {stem}.md")
            continue
        rec = {"score": e["score"], "unsupported": clean_list(e.get("unsupported")),
               "missing": clean_list(e.get("missing"), 3)}
        with open(os.path.join(done_dir, stem + ".faithfulness.json"), "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=1)
        flag = "" if rec["score"] >= 4 else "  ⚠ check this summary"
        print(f"  faithfulness: {stem}.md {rec['score']}/5, {len(rec['unsupported'])} unsupported, "
              f"{len(rec['missing'])} missing{flag}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "added":
        added(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 3 and sys.argv[1] == "apply":
        sys.exit(apply(sys.argv[2], sys.argv[3:]))
    else:
        sys.exit(__doc__)
