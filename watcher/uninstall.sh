#!/usr/bin/env bash
# Disarm the automation: unload and remove the launchd agent.
launchctl bootout "gui/$(id -u)/com.notes-clipper.watcher" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/com.notes-clipper.watcher.plist"
echo "✓ Watcher removed. Captures still land in ~/Downloads/notes-inbox/ — say \"process the web inbox\" in Claude to route them manually."
