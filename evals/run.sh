#!/usr/bin/env bash
# Run a fixed set of captures through the real watcher, with your real Claude
# and model, in a throwaway home, and score the result (score.py). Use it after
# changing the routing prompt, the model or the watcher, to see whether filing
# got better or worse. It spends real usage: one routing run and one
# faithfulness check for the whole set.
#
#   bash evals/run.sh                 the public set (evals/public)
#   bash evals/run.sh ~/my-eval-set   your own set, same layout
#
# A set is a folder with captures/ (capture/1 records, plus any attachments),
# notes/ (the topic notes to start from, with a Routing_map_note.md) and
# expected.json. Results go to ~/.cache/notes-clipper/evals/<set>/, and each run
# is compared with the one before. Your inbox, notes and pages aren't touched.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/.." && pwd)"
set_dir="$(cd "${1:-$here/public}" && pwd)"
[ -f "$set_dir/expected.json" ] && [ -d "$set_dir/captures" ] && [ -d "$set_dir/notes" ] \
  || { echo "✗ $set_dir needs captures/, notes/ and expected.json"; exit 1; }

# Your claude and model, read the way the watcher reads them.
env_file="$HOME/.config/notes-clipper/watcher.env"
CLAUDE_BIN="$( [ -f "$env_file" ] && . "$env_file" >/dev/null 2>&1; printf '%s' "${CLAUDE_BIN:-}")"
CLAUDE_BIN="${CLAUDE_BIN:-$(command -v claude)}"
model="${EVAL_MODEL:-$( [ -f "$env_file" ] && . "$env_file" >/dev/null 2>&1; printf '%s' "${CLAUDE_MODEL:-}")}"
[ -x "$CLAUDE_BIN" ] || { echo "✗ claude not found. Run watcher/install.sh first."; exit 1; }
# The set's routing map: Routing_map_note.md if it has one, else yours.
map=Routing_map_note.md
[ -f "$set_dir/notes/$map" ] || map="$( [ -f "$env_file" ] && . "$env_file" >/dev/null 2>&1; printf '%s' "${NOTES_ROUTING_MAP:-$map}")"
# The sandbox has its own home, so the watcher's Keychain sign-in is passed in.
token="$(security find-generic-password -a "$USER" -s notes-clipper-claude-token -w 2>/dev/null)"
[ -n "$token" ] && export CLAUDE_CODE_OAUTH_TOKEN="$token"

SB="$(mktemp -d)"
mkdir -p "$SB/notes/Handwritten/archive" "$SB/notes/Handwritten/inbox" "$SB/pages" "$SB/refs" \
  "$SB/Downloads/notes-inbox" "$SB/.config/notes-clipper" "$SB/stubs"
cp -R "$set_dir/notes" "$SB/notes/Handwritten/notes"
for f in build_html.py build_quiz.py build_review.py; do ln -s "$repo/renderer/$f" "$SB/refs/$f"; done
echo '[]' > "$SB/refs/quiz-bank.json"; echo '[]' > "$SB/refs/glossary-extra.json"
printf '#!/bin/bash\nexit 0\n' > "$SB/stubs/open"; chmod +x "$SB/stubs/open"   # no browser windows
cat > "$SB/.config/notes-clipper/watcher.env" <<EOF
CLAUDE_BIN="$CLAUDE_BIN"
WATCHER_PATH="$SB/stubs:$(dirname "$CLAUDE_BIN"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
NOTES_VAULT="$SB/notes"
NOTES_OUT="$SB/pages"
NOTES_REFS="$SB/refs"
NOTES_ROUTING_MAP="$map"
CLAUDE_MODEL="$model"
EOF
cp "$set_dir/captures/"* "$SB/Downloads/notes-inbox/"

echo "• Running $(ls "$set_dir/captures/"*.md | wc -l | tr -d ' ') captures from $(basename "$set_dir") with ${model:-the account default model} (a few minutes)…"
for i in 1 2 3; do
  HOME="$SB" CLIP_NOTIFY_BIN=/bin/true bash "$repo/watcher/process_inbox.sh"
  [ -z "$(ls "$SB/Downloads/notes-inbox/"*.md 2>/dev/null)" ] && break
done
python3 "$here/score.py" "$set_dir" "$SB" "$HOME/.cache/notes-clipper/evals/$(basename "$set_dir")" "${model:-account default}"
rc=$?
echo "  sandbox kept for a look: $SB (notes in notes/Handwritten/notes, log in Downloads/notes-inbox-processed/watcher.log)"
exit $rc
