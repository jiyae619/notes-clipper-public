---
record: capture/1
source_type: note
title: "Git branches in five minutes"
source: "https://example.com/git-branches"
captured: 2026-11-01 09:00
---

A git branch is a movable pointer to a commit. Creating one is cheap, so make a branch for every experiment: git switch -c try-idea. Commit as you go; if the idea fails, switch back to main and delete the branch, and main is untouched. When it works, merge it into main. Small, frequent commits make it easy to see what changed and to undo one step.
