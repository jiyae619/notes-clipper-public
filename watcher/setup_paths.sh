#!/usr/bin/env bash
# Decide where the vault, the build scripts and the rendered pages live, and
# make sure each exists. install.sh runs this and writes what it prints into
# watcher.env; it touches no launchd or Keychain state, so tests run it in a
# throwaway HOME.
#
# Each setting comes from, in order: the environment, the previous
# watcher.env, then the default. So `NOTES_VAULT=~/Notes bash install.sh`
# changes the vault once and later re-installs keep it.
#
#   NOTES_VAULT        your notes folder          default ~/Documents/Notes
#   NOTES_OUT          the rendered HTML pages    default ~/Documents/Notes Pages
#   NOTES_REFS         build scripts + their data (quiz bank, map keywords,
#                      What's new)                default ~/.config/notes-clipper/renderer
#   NOTES_ROUTING_MAP  the note in Handwritten/notes/ that says which topic
#                      gets what                  default Routing_map_note.md
#   WATCHER_LABEL      the launchd job's name     default com.notes-clipper.watcher
#   CLAUDE_MODEL       the model every Claude call uses, e.g. claude-opus-5-5
#                                                 default: unset (Claude's own default)
#
# Upgrading an install from before these settings existed (a watcher.env with
# no NOTES_VAULT): the folders it used can't be known from here, so this stops
# and asks for them rather than quietly switching to the defaults. Its launchd
# job keeps its name: a job already running this checkout's process_inbox.sh
# lends its label, so install.sh replaces it instead of adding a second one.
#
# Nothing here overwrites a file that exists: a new vault gets the starter
# layout from starter-vault/, a new NOTES_REFS gets links to renderer/ and an
# empty quiz bank, and an existing one is left as it is.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/.." && pwd)"
env_file="$HOME/.config/notes-clipper/watcher.env"

# watcher.env is a shell file the watcher sources, so it is read back the same
# way (in a subshell), and every value is written escaped for double quotes.
prev() { [ -f "$env_file" ] || return 0; ( . "$env_file" >/dev/null 2>&1; eval "printf '%s' \"\${$1-}\"" ); }
q() { printf '%s' "$1" | sed 's/[\\"$`]/\\&/g'; }
if [ -f "$env_file" ] && [ -z "$(prev NOTES_VAULT)" ] && [ -z "${NOTES_VAULT:-}" ]; then
  cat >&2 <<EOF
✗ This install was made by an older version, before the folders became settings.
  Re-run install.sh naming the folders it should keep using, for example:
    NOTES_VAULT="\$HOME/path/to/notes" NOTES_OUT="\$HOME/path/to/pages" \\
    NOTES_REFS="\$HOME/path/to/build-scripts" NOTES_ROUTING_MAP="Your_map_note.md" \\
    bash $here/install.sh
  Any you leave out get the defaults (see the README's Settings).
EOF
  exit 1
fi
# A launchd job already running this checkout's watcher (from an earlier install)
running_label() {
  grep -l "$here/process_inbox.sh" "$HOME/Library/LaunchAgents/"*.plist 2>/dev/null | head -1 \
    | xargs -I{} /usr/bin/plutil -extract Label raw {} 2>/dev/null
}
vault="${NOTES_VAULT:-$(prev NOTES_VAULT)}"; vault="${vault:-$HOME/Documents/Notes}"
out="${NOTES_OUT:-$(prev NOTES_OUT)}";       out="${out:-$HOME/Documents/Notes Pages}"
refs="${NOTES_REFS:-$(prev NOTES_REFS)}";    refs="${refs:-$HOME/.config/notes-clipper/renderer}"
map="${NOTES_ROUTING_MAP:-$(prev NOTES_ROUTING_MAP)}"; map="${map:-Routing_map_note.md}"
model="${CLAUDE_MODEL-$(prev CLAUDE_MODEL)}"
label="${WATCHER_LABEL:-$(prev WATCHER_LABEL)}"; label="${label:-$(running_label)}"; label="${label:-com.notes-clipper.watcher}"

if [ ! -d "$vault/Handwritten/notes" ]; then
  mkdir -p "$vault"
  cp -Rn "$repo/starter-vault/" "$vault/"
  echo "• Created the starter vault layout in $vault" >&2
fi
mkdir -p "$vault/Handwritten/inbox" "$vault/Handwritten/archive" "$out"

if [ ! -f "$refs/build_html.py" ]; then
  mkdir -p "$refs"
  # Linked, not copied: a `git pull` updates them. Their data stays beside the
  # links in $refs, outside the repo, since the scripts keep it next to themselves.
  for f in build_html.py build_quiz.py build_review.py; do ln -sfn "$repo/renderer/$f" "$refs/$f"; done
  [ -f "$refs/quiz-bank.json" ] || echo '[]' > "$refs/quiz-bank.json"
  [ -f "$refs/glossary-extra.json" ] || echo '[]' > "$refs/glossary-extra.json"
  echo "• Set up the notes renderer in $refs" >&2
fi

printf 'NOTES_VAULT="%s"\nNOTES_OUT="%s"\nNOTES_REFS="%s"\nNOTES_ROUTING_MAP="%s"\nWATCHER_LABEL="%s"\nCLAUDE_MODEL="%s"\n' \
  "$(q "$vault")" "$(q "$out")" "$(q "$refs")" "$(q "$map")" "$(q "$label")" "$(q "$model")"
