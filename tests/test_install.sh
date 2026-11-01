#!/usr/bin/env bash
# Install and upgrade tests: run the real watcher/install.sh and uninstall.sh in
# a throwaway HOME, with stand-ins for launchctl (it keeps the loaded jobs in a
# file), clang and codesign, so nothing is registered with your real launchd.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
W="$(cd "$here/../watcher" && pwd)"
pass=0 fail=0

new_home() {
  H="$(mktemp -d)"; mkdir -p "$H/stubs" "$H/.config/notes-clipper" "$H/Library/LaunchAgents"
  # launchctl: bootstrap loads the plist's Label, bootout unloads it, print and
  # list answer from the loaded set.
  cat > "$H/stubs/launchctl" <<'EOF'
#!/bin/bash
J="$HOME/loaded"; touch "$J"
case "$1" in
  bootstrap) /usr/bin/plutil -extract Label raw "$3" >> "$J" ;;
  bootout) l="${2##*/}"; grep -vx "$l" "$J" > "$J.t"; mv "$J.t" "$J" ;;
  print) grep -qx "${2##*/}" "$J" ;;
  list) cat "$J" ;;
esac
EOF
  printf '#!/bin/bash\nwhile [ $# -gt 0 ]; do [ "$1" = -o ] && touch "$2"; shift; done\n' > "$H/stubs/clang"
  printf '#!/bin/bash\nexit 0\n' > "$H/stubs/codesign"
  printf '#!/bin/bash\necho stub\n' > "$H/stubs/claude"
  chmod +x "$H/stubs/"*
}
install() { HOME="$H" PATH="$H/stubs:/usr/bin:/bin" CLAUDE_BIN="$H/stubs/claude" env "$@" bash "$W/install.sh" > "$H/out" 2>&1; rc=$?; }
uninstall() { HOME="$H" PATH="$H/stubs:/usr/bin:/bin" bash "$W/uninstall.sh" > "$H/out" 2>&1; rc=$?; }
jobs() { sort "$H/loaded" 2>/dev/null | tr '\n' ' '; }
setting() { sed -n "s/^$1=\"\(.*\)\"$/\1/p" "$H/.config/notes-clipper/watcher.env" | tail -1; }
check() { local d="$1"; shift; if "$@"; then pass=$((pass+1)); echo "  ok    $d"
          else fail=$((fail+1)); echo "  FAIL  $d"; sed 's/^/        | /' "$H/out" | tail -6; echo "        | jobs: $(jobs)"; fi; }
legacy_job() {   # a job an older install.sh registered for this checkout, under its own name
  printf '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n<plist version="1.0"><dict><key>Label</key><string>%s</string><key>ProgramArguments</key><array><string>runner</string><string>%s/process_inbox.sh</string></array></dict></plist>\n' \
    "$1" "$W" > "$H/Library/LaunchAgents/$1.plist"
  echo "$1" >> "$H/loaded"
  printf 'CLAUDE_BIN="/old/claude"\nWATCHER_PATH="/usr/bin"\n' > "$H/.config/notes-clipper/watcher.env"   # all the old install.sh wrote
}

# ---- a fresh Mac --------------------------------------------------------------

new_home; install
check "a fresh install reports success when its job loaded (it looked for an old name and said it failed)" \
  eval '[ $rc = 0 ] && grep -q "Watcher installed" "$H/out" && [ "$(jobs)" = "com.notes-clipper.watcher " ]'
check "...its plist carries that name, and watcher.env records every setting" \
  eval '[ "$(/usr/bin/plutil -extract Label raw "$H/Library/LaunchAgents/com.notes-clipper.watcher.plist")" = com.notes-clipper.watcher ] && [ "$(setting WATCHER_LABEL)" = com.notes-clipper.watcher ] && [ -n "$(setting NOTES_VAULT)" ] && [ -n "$(setting NOTES_ROUTING_MAP)" ]'
install
check "re-installing replaces the job instead of adding a second one" eval '[ $rc = 0 ] && [ "$(jobs)" = "com.notes-clipper.watcher " ]'
uninstall
check "uninstall removes the job and its plist" eval '[ -z "$(jobs)" ] && [ ! -e "$H/Library/LaunchAgents/com.notes-clipper.watcher.plist" ]'
rm -rf "$H"

new_home; install; install WATCHER_LABEL=com.example.renamed
check "R6-1: re-installing under a new job name removes the old job, so only one watcher runs" \
  eval '[ $rc = 0 ] && [ "$(jobs)" = "com.example.renamed " ] && [ ! -e "$H/Library/LaunchAgents/com.notes-clipper.watcher.plist" ]'
uninstall
check "...and uninstall then leaves nothing running" eval '[ -z "$(jobs)" ] && [ -z "$(ls "$H/Library/LaunchAgents")" ]'
rm -rf "$H"

new_home; install WATCHER_LABEL=com.example.mine
check "a custom job name installs and is verified under that name" \
  eval '[ $rc = 0 ] && [ "$(jobs)" = "com.example.mine " ] && [ "$(setting WATCHER_LABEL)" = com.example.mine ]'
rm -rf "$H"

new_home; printf '#!/bin/bash\necho stub\n' > "$H/stubs/codex"; chmod +x "$H/stubs/codex"
install NOTES_AGENT=codex CODEX_BIN="$H/stubs/codex" CODEX_MODEL=gpt-test CLAUDE_BIN=
check "Codex: installs with NOTES_AGENT=codex and no Claude, recording codex's path and model" \
  eval '[ $rc = 0 ] && [ "$(setting NOTES_AGENT)" = codex ] && [ "$(setting CODEX_BIN)" = "$H/stubs/codex" ] && [ "$(setting CODEX_MODEL)" = gpt-test ] && [ -z "$(setting CLAUDE_BIN)" ]'
install CLAUDE_BIN=
check "...and a re-install keeps Codex without being told again" eval '[ $rc = 0 ] && [ "$(setting NOTES_AGENT)" = codex ]'
rm -rf "$H"

new_home; install NOTES_AGENT=gemini
check "an unknown agent is refused with the choices named" eval '[ $rc = 1 ] && grep -q "claude or codex" "$H/out"'
rm -rf "$H"

# ---- upgrading an install made before the settings existed --------------------

new_home; legacy_job com.example.legacy; install
check "upgrading without naming the folders stops, leaves the old job running and its settings untouched" \
  eval '[ $rc = 1 ] && grep -q "older version" "$H/out" && [ "$(jobs)" = "com.example.legacy " ] && [ -z "$(setting NOTES_VAULT)" ] && [ "$(setting CLAUDE_BIN)" = /old/claude ]'
install NOTES_VAULT="$H/My Notes" NOTES_ROUTING_MAP=Old_map_note.md
check "naming them upgrades in place: one job, still under the old name, with the folders kept" \
  eval '[ $rc = 0 ] && [ "$(jobs)" = "com.example.legacy " ] && [ "$(setting NOTES_VAULT)" = "$H/My Notes" ] && [ "$(setting NOTES_ROUTING_MAP)" = Old_map_note.md ] && [ "$(setting WATCHER_LABEL)" = com.example.legacy ]'
install
check "later re-installs keep all of it without being told again" \
  eval '[ $rc = 0 ] && [ "$(jobs)" = "com.example.legacy " ] && [ "$(setting NOTES_VAULT)" = "$H/My Notes" ]'
rm -rf "$H"

new_home; legacy_job com.example.legacy; uninstall
check "uninstall finds an older install's job by what it runs, not by the new default name" \
  eval '[ -z "$(jobs)" ] && [ ! -e "$H/Library/LaunchAgents/com.example.legacy.plist" ]'
rm -rf "$H"

echo
echo "install: $pass passed, $fail failed"
[ "$fail" = 0 ]
