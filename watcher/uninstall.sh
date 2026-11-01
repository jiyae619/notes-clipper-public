#!/usr/bin/env bash
# Disarm the automation: unload and remove the launchd agent.
# Its name is WATCHER_LABEL in watcher.env (written by install.sh); an install
# from before that setting is found by the job that runs this checkout's watcher.
here="$(cd "$(dirname "$0")" && pwd)"
label="$( . "$HOME/.config/notes-clipper/watcher.env" >/dev/null 2>&1; printf '%s' "${WATCHER_LABEL-}")"
[ -n "$label" ] || label="$(grep -l "$here/process_inbox.sh" "$HOME/Library/LaunchAgents/"*.plist 2>/dev/null | head -1 \
  | xargs -I{} /usr/bin/plutil -extract Label raw {} 2>/dev/null)"
label="${label:-com.notes-clipper.watcher}"
launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$label.plist"
echo "✓ Watcher removed ($label). Captures still land in ~/Downloads/notes-inbox/ and route once you run install.sh again."
