#!/usr/bin/env bash
# Add one of your own filed captures to a private eval set (kept outside the
# repo, so it never reaches the public copy). Then run: bash evals/run.sh SET
#
#   bash evals/add_capture.sh ~/Downloads/notes-inbox-processed/done/<capture>.md [SET]
#
# SET defaults to ~/.config/notes-clipper/evals/my-set. The first capture you
# add also copies your current topic notes into SET/notes/ as the starting
# point. Pick captures that came in after that snapshot: for older ones the
# notes already hold their content, so their fact checks prove little.
# Where the capture went is filled in from your watcher log; the facts it must
# keep are yours to write, in SET/expected.json.
set -eu
here="$(cd "$(dirname "$0")" && pwd)"
rec="${1:?usage: add_capture.sh DONE_CAPTURE.md [SET]}"
set_dir="${2:-$HOME/.config/notes-clipper/evals/my-set}"
[ -f "$rec" ] || { echo "✗ No such capture: $rec"; exit 1; }
stem="$(basename "${rec%.md}")"
vault="$( . "$HOME/.config/notes-clipper/watcher.env" >/dev/null 2>&1; printf '%s' "${NOTES_VAULT:-$HOME/Documents/Notes}")"

mkdir -p "$set_dir/captures"
if [ ! -d "$set_dir/notes" ]; then
  cp -R "$vault/Handwritten/notes" "$set_dir/notes"
  echo "• Started $set_dir with a copy of your $(ls "$set_dir/notes" | wc -l | tr -d ' ') topic notes"
fi
cp "$rec" "$set_dir/captures/"
# its attachments, as listed in the record
sed -n '/^attachments:/,/^[^ ]/s/^  - //p' "$rec" | while read -r a; do
  [ -f "$(dirname "$rec")/$a" ] && cp "$(dirname "$rec")/$a" "$set_dir/captures/"
done
went="$(grep -h "✓ routed: $stem.md → " "$HOME/Downloads/notes-inbox-processed/watcher.log" 2>/dev/null | tail -1 | sed 's/.*→ //' | cut -d, -f2-)"
python3 - "$set_dir/expected.json" "$stem" "$went" <<'PY'
import json, os, sys
path, stem, went = sys.argv[1:]
exp = json.load(open(path)) if os.path.exists(path) else {}
exp[stem] = {"probes": "your own capture", "notes": [n for n in went.split(",") if n],
             "facts": [], "todo": "add 1-3 phrases the note must keep from this capture"}
json.dump(exp, open(path, "w"), ensure_ascii=False, indent=1)
PY
echo "✓ Added $stem (went to: ${went:-unknown}). Now write its facts in $set_dir/expected.json"
