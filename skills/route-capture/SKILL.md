---
name: route-capture
description: Route the captures waiting in the Notes Clipper inbox now, instead of waiting for the watcher (a fresh save already starts it; this is for the backlog, retries and scans), and report what happened to each. Runs the same watcher, with the same routing instructions, as the unattended poll. Trigger on "/route-capture", "route my captures", "route the inbox now", or "process the web inbox".
---

# Route captures now

Starts the Notes Clipper watcher immediately and reports the result. It never
routes anything by hand: interactive and unattended routing must be the same
code with the same instructions (`watcher/route-capture.md`), or they drift
apart, as archive naming did on 2026-09-03.

Repo: wherever you cloned notes-clipper. Inbox: `~/Downloads/notes-inbox/`. Log:
`~/Downloads/notes-inbox-processed/watcher.log`. The watcher's launchd job is
named by `WATCHER_LABEL` in `~/.config/notes-clipper/watcher.env`
(`com.notes-clipper.watcher` if it isn't set); `<label>` below means that name.

## Steps

1. **See what's waiting.** Count `~/Downloads/notes-inbox/*.md`, and failed
   captures still due a retry in `~/Downloads/notes-inbox-processed/failed/`.
   If nothing is waiting, say so and stop.
2. **Note where the log ends** (`wc -l` of watcher.log), so you report only
   this run.
3. **Start the watcher** with
   `launchctl kickstart gui/$(id -u)/<label>`.
   It runs under Notes Clipper Runner, which holds the macOS folder access. If
   the agent isn't loaded, tell the user to run
   `bash <repo>/watcher/install.sh` and stop.
4. **Wait for it to finish**: check
   `launchctl print gui/$(id -u)/<label>` every ~15 s
   until `state = not running` (a batch usually takes 2 to 5 minutes; give up
   after 20).
5. **Report from the new log lines**, per capture:
   - `✓ routed:` reached the vault (verify.sh checked the archive, attachments
     and the topic-note citation). Name the archive file and note(s) Claude
     reported.
   - `✗ not routed (attempt N of 3): … — reason`: it's in `failed/` and will be
     retried on the next poll. Give the reason as written.
   - `NOT ROUTED`: a video with no captions, filed under `skipped/`.
   - The `proposals:` line: quiz ids and map keywords added, and anything
     dropped with its reason.
   - Any `ALERT:` line.
   Also give the watcher's exit code from `launchctl print` (`last exit code`).

## Don't

- Don't edit notes, the archive, the quiz bank or the map yourself, and don't
  move captures between folders. If a capture failed, report why; the watcher
  retries it.
- Don't print or handle the watcher's token (Keychain item
  `notes-clipper-claude-token`).
