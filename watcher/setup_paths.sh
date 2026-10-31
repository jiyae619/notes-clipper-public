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
#
# Nothing here overwrites a file that exists: a new vault gets the starter
# layout from starter-vault/, a new NOTES_REFS gets links to renderer/ and an
# empty quiz bank, and an existing one is left as it is.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
repo="$(cd "$here/.." && pwd)"
env_file="$HOME/.config/notes-clipper/watcher.env"

prev() { [ -f "$env_file" ] || return 0; sed -n "s/^$1=\"\(.*\)\"$/\1/p" "$env_file" | tail -1; }
vault="${NOTES_VAULT:-$(prev NOTES_VAULT)}"; vault="${vault:-$HOME/Documents/Notes}"
out="${NOTES_OUT:-$(prev NOTES_OUT)}";       out="${out:-$HOME/Documents/Notes Pages}"
refs="${NOTES_REFS:-$(prev NOTES_REFS)}";    refs="${refs:-$HOME/.config/notes-clipper/renderer}"
map="${NOTES_ROUTING_MAP:-$(prev NOTES_ROUTING_MAP)}"; map="${map:-Routing_map_note.md}"

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

printf 'NOTES_VAULT="%s"\nNOTES_OUT="%s"\nNOTES_REFS="%s"\nNOTES_ROUTING_MAP="%s"\n' "$vault" "$out" "$refs" "$map"
