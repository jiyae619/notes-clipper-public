#!/usr/bin/env bash
# One-time install / re-install of the notes-inbox watcher. Run this yourself —
# it registers a launchd agent that runs whenever ~/Downloads/notes-inbox
# changes (and every 15 min) and runs headless Claude (acceptEdits) when
# captures are waiting, so arming
# that automation is your call.
#
# Everything machine-specific is generated here, outside the repo:
#   ~/.config/notes-clipper/watcher.env     claude's path + PATH, found via your shell,
#       and where the vault, pages and build scripts live (setup_paths.sh)
#   ~/Library/Application Support/notes-clipper/Notes Clipper Runner.app
#       the signed launcher launchd starts; macOS folder access is granted to it
#   ~/Library/LaunchAgents/<WATCHER_LABEL>.plist  (from the template)
#   ~/.claude/skills/route-capture   a link to skills/route-capture (the /route-capture command)
#
# The log and processed/ live in a sibling dir, not inside the inbox. This
# script migrates them out of the old in-inbox layout if it finds one.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
plist_src="$here/com.notes-clipper.watcher.plist"
inbox="$HOME/Downloads/notes-inbox"
processed="$HOME/Downloads/notes-inbox-processed"
config_dir="$HOME/.config/notes-clipper"
app="$HOME/Library/Application Support/notes-clipper/Notes Clipper Runner.app"
runner="$app/Contents/MacOS/notes-clipper-runner"

mkdir -p "$inbox" "$processed" "$config_dir" "$HOME/Library/Logs" "$HOME/Library/LaunchAgents"

# Migrate the pre-QueueDirectories layout out of the queue dir (else launchd
# sees a non-empty dir and re-fires forever).
[ -d "$inbox/processed" ] && { mv "$inbox/processed"/* "$processed"/ 2>/dev/null || true; rmdir "$inbox/processed" 2>/dev/null || true; }
[ -f "$inbox/watcher.log" ] && mv "$inbox/watcher.log" "$processed/watcher.log" 2>/dev/null || true

# The page build runs python3 and pandoc under launchd's PATH (watcher.env below).
for tool in python3 pandoc; do
  PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" command -v "$tool" >/dev/null \
    || { echo "✗ $tool not found. Install it first: brew install $tool"; exit 1; }
done
# Vault, rendered pages and build scripts; see setup_paths.sh for the settings.
paths="$(bash "$here/setup_paths.sh")" || exit 1
agent="$(eval "$paths"; printf '%s' "$NOTES_AGENT")"
# launchd can't see nvm, so record where your shell finds the agent's CLI.
# Re-run this after a Node upgrade moves it. CLAUDE_BIN / CODEX_BIN override
# the lookup.
find_cli() { command -v "$1" || zsh -ic "command -v $1" 2>/dev/null | tail -1; }
if [ "$agent" = codex ]; then
  agent_bin="${CODEX_BIN:-$(find_cli codex)}"; bin_line="CODEX_BIN=\"$agent_bin\""
  [ -x "$agent_bin" ] || { echo "✗ Can't find the codex CLI. Install it (npm i -g @openai/codex), or re-run with CODEX_BIN=/path/to/codex"; exit 1; }
else
  agent_bin="${CLAUDE_BIN:-$(find_cli claude)}"; bin_line="CLAUDE_BIN=\"$agent_bin\""
  [ -x "$agent_bin" ] || { echo "✗ Can't find the claude CLI. Re-run with CLAUDE_BIN=/path/to/claude"; exit 1; }
fi
label="$(eval "$paths"; printf '%s' "$WATCHER_LABEL")"   # read the way the watcher will
plist_dst="$HOME/Library/LaunchAgents/$label.plist"
cat > "$config_dir/watcher.env" <<EOF
# Written by watcher/install.sh on $(date '+%Y-%m-%d'). Re-run it to refresh.
$bin_line
WATCHER_PATH="$(dirname "$agent_bin"):/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
$paths
EOF

# Rebuild the runner only when its source changed. macOS ties the folder-access
# grant to this exact build, so a needless rebuild would make you grant it again.
src_hash="$(cat "$here/runner/main.c" "$here/runner/Info.plist" | shasum -a 256 | cut -d' ' -f1)"
if [ "$(cat "$app/Contents/Resources/source.sha256" 2>/dev/null)" != "$src_hash" ]; then
  rm -rf "$app"
  mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
  cp "$here/runner/Info.plist" "$app/Contents/Info.plist"
  clang -O2 -o "$runner" "$here/runner/main.c"
  echo "$src_hash" > "$app/Contents/Resources/source.sha256"
  codesign --force --sign - --identifier com.notes-clipper.runner "$app"
  echo "• Built Notes Clipper Runner (a new build needs folder access granted again)"
fi

# /route-capture, the interactive way to run this watcher now. Linked rather
# than copied, so it stays in step with the repo.
mkdir -p "$HOME/.claude/skills"
ln -sfn "$here/../skills/route-capture" "$HOME/.claude/skills/route-capture"

sed -e "s|__LABEL__|$label|" -e "s|__RUNNER__|$runner|" -e "s|__SCRIPT__|$here/process_inbox.sh|" -e "s|__HOME__|$HOME|g" \
  "$plist_src" > "$plist_dst"
plutil -lint "$plist_dst" >/dev/null

# One watcher per checkout: a job left from an install under another name
# would process the same inbox alongside this one, so it goes first.
for other in $(grep -l "$here/process_inbox.sh" "$HOME/Library/LaunchAgents/"*.plist 2>/dev/null); do
  old="$(/usr/bin/plutil -extract Label raw "$other" 2>/dev/null)"
  [ -n "$old" ] && [ "$old" != "$label" ] || continue
  launchctl bootout "gui/$(id -u)/$old" 2>/dev/null || true
  rm -f "$other"; echo "• Removed the earlier job $old (it ran this same watcher)"
done
launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$plist_dst"
launchctl print "gui/$(id -u)/$label" >/dev/null 2>&1 \
  && echo "✓ Watcher installed (runs when a capture lands, every 15 min, and once now). If macOS asks whether Notes Clipper Runner may access Downloads and Documents, click Allow. Then save a capture and check $processed/watcher.log" \
  || { echo "✗ Agent did not load — check: launchctl print gui/$(id -u)/$label"; exit 1; }
