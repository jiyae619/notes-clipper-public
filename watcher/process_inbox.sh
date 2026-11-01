#!/usr/bin/env bash
# Invoked by launchd whenever ~/Downloads/notes-inbox changes, so what you save
# routes within minutes, plus a 15-min StartInterval poll (and once at load)
# for scans and the screenshot backlog. If any
# captures are waiting in ~/Downloads/notes-inbox, drain them (each *.md plus
# the <stem>-imgN.* files it embeds) to ../notes-inbox-processed/ and run one
# headless Claude session in the vault to route them into the notes pipeline
# (archive verbatim, integrate summary into topic notes, quiz + map). Empty
# polls make no Claude call, so most wakes cost nothing.
#
# Opens the rendered notes hub ONCE at the very end — never per rebuild (the
# PostToolUse hook rebuilds silently; only this poller opens, after routing).
#
# Test without spending tokens: CLIP_CLAUDE_BIN=/bin/echo ./process_inbox.sh
# (add CLIP_NOTIFY_BIN=/bin/echo to print alerts instead of posting them).

# launchd has a minimal PATH and can't see nvm, where claude lives. install.sh
# finds claude through your shell and writes its path and a PATH to watcher.env;
# re-run install.sh after a Node upgrade. yt-dlp is a Homebrew install
# (/opt/homebrew on Apple Silicon) — without that entry the transcript step
# silently reports "yt-dlp not installed" on a machine that has it.
config="$HOME/.config/notes-clipper/watcher.env"
[ -f "$config" ] && . "$config"
export PATH="${WATCHER_PATH:-/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin}"

# The CLI's own sign-in lapses when you don't use it (you work in the desktop
# app), and on Sep 27 that failed the first unattended route. So claude runs
# on a long-lived token from `claude setup-token`, kept in your login Keychain
# (see README), never in a file. Without one, claude falls back to its own
# sign-in.
token="$(security find-generic-password -a "$USER" -s notes-clipper-claude-token -w 2>/dev/null)"
[ -n "$token" ] && export CLAUDE_CODE_OAUTH_TOKEN="$token"
unset token

here="$(cd "$(dirname "$0")" && pwd)"
inbox="$HOME/Downloads/notes-inbox"
processed="$HOME/Downloads/notes-inbox-processed"

# launchd drops inbox changes made while a run is going (tested Sep 28: a file
# saved mid-run started no second run), and a routing run takes minutes. So
# after each pass, go again if you saved something meanwhile. Bounded, so a
# capture that can't be claimed never loops forever; the backlog doesn't count.
if [ -z "${NC_PASS:-}" ]; then
  mark="$(mktemp)"
  for pass in 1 2 3 4 5; do
    touch "$mark"
    NC_PASS=$pass "$BASH" "$0" "$@"; rc=$?
    [ -z "$(find "$inbox" -maxdepth 1 -name '*.md' ! -name '*-screenshot-*' -newer "$mark" 2>/dev/null)" ] && break
  done
  rm -f "$mark"; exit $rc
fi
# Capture states. A capture used to be moved to processed/ before routing and
# left there whatever happened, so a failed run looked finished (twice on Sep 27).
#   processing/  claimed by this run
#   done/        verify.sh confirmed it reached the vault
#   failed/      it didn't; retried on the next polls, up to max_attempts
#   skipped/     a video with no captions, so nothing to route (see below)
processing="$processed/processing" done_dir="$processed/done"
failed="$processed/failed" skipped="$processed/skipped"
#   needs-review/  a transcribed scan, waiting for you to approve its transcript
#                  on the review page (review/review.html)
needs_review="$processed/needs-review" review_dir="$processed/review"
max_attempts=3
# A screenshot import can queue hundreds of screenshots, more than one routing run
# can hold, so a poll takes at most this many; the rest wait for the next poll.
max_per_run=10 capped=0
# Where things live; install.sh records any you changed in watcher.env.
# NOTES_REFS holds the build scripts and their data (quiz bank, map keywords).
configured="${NOTES_VAULT:-}"   # empty: settings predate this version (checked below)
vault="${NOTES_VAULT:-$HOME/Documents/Notes}"
hw_inbox="$vault/Handwritten/inbox"   # where your phone saves scans
skills_ref="${NOTES_REFS:-$HOME/.config/notes-clipper/renderer}"
previews="${NOTES_OUT:-$HOME/Documents/Notes Pages}"
routing_map="${NOTES_ROUTING_MAP:-Routing_map_note.md}"   # the note that says which topic gets what
export NOTES_VAULT="$vault" NOTES_OUT="$previews"   # read by the build scripts
log="$processed/watcher.log"
claude_bin="${CLIP_CLAUDE_BIN:-$CLAUDE_BIN}"
# CLAUDE_MODEL pins the model for every Claude call here, so quality doesn't
# shift when the account's default model changes. Unset: Claude's default.
model_args=(); [ -n "${CLAUDE_MODEL:-}" ] && model_args=(--model "$CLAUDE_MODEL")
alert_stamps="$HOME/Library/Caches/notes-clipper-watcher"

# Nobody reads this log while things run unattended: from Sep 5 every poll failed
# silently for 24 days. So a failure also posts a macOS notification. Each kind
# of alert (KEY) notifies at most once per 6 h, so a fault that persists doesn't
# nag on every poll, while a different fault (say "gave up" after "retrying")
# still gets through. The log sits in ~/Downloads too, so when TCC blocks the
# watcher it blocks the log as well; the alert line then goes to ~/Library/Logs
# (unprotected, visible in Console.app).
alert() {  # alert KEY MESSAGE
  local stamp="$alert_stamps/$1.alert" line="[$(date '+%Y-%m-%d %H:%M:%S')] ALERT: $2"
  { echo "$line" >> "$log"; } 2>/dev/null \
    || echo "$line" >> "$HOME/Library/Logs/notes-clipper-watcher.log"
  [ -n "$(find "$stamp" -mmin -360 2>/dev/null)" ] && return
  mkdir -p "$alert_stamps" && touch "$stamp"
  if [ -n "$CLIP_NOTIFY_BIN" ]; then "$CLIP_NOTIFY_BIN" "$2"
  else osascript -e "display notification \"$2\" with title \"Notes Clipper\""; fi
}

mkdir -p "$processing" "$done_dir" "$failed" "$skipped" "$needs_review" "$review_dir"

if [ -z "$claude_bin" ]; then
  alert setup "The watcher isn't set up (no claude path in ~/.config/notes-clipper/watcher.env). Run watcher/install.sh."
  exit 1
fi
# Settings from an older install name no folders; guessing would file captures
# into a new, empty notes folder and leave the real one behind.
if [ -z "$configured" ]; then
  alert setup "The watcher's settings are from an older version and name no notes folder. Run watcher/install.sh (see the README's Settings)."
  exit 1
fi

# An unreadable folder globs to nothing, exactly like an empty one, which is how
# macOS privacy controls (TCC) hid this watcher's failure. Check both ends before
# touching anything, so a blocked run never moves captures it can't route.
if ! ls "$inbox" >/dev/null 2>&1; then
  alert inbox "Can't read ~/Downloads/notes-inbox, so captures won't route. macOS privacy settings are likely blocking the watcher."
  exit 1
fi
if ! ls "$vault/Handwritten/notes" >/dev/null 2>&1; then
  alert vault "Can't read your notes folder, so captures won't route. macOS privacy settings are likely blocking the watcher."
  exit 1
fi

# Safety net for whatever the checks above don't foresee: however this run ends,
# a capture over an hour old still in the inbox means something kept a poll from
# taking it. Checked at exit, not on arrival, so a capture saved before the Mac
# slept and routed on the first poll after waking doesn't raise a false alarm.
stale_check() {
  [ $capped = 1 ] && return   # captures past the per-poll cap are waiting on purpose
  local n
  n=$(find "$inbox" -maxdepth 1 -name '*.md' -mmin +60 2>/dev/null | wc -l | tr -d ' ')
  [ "$n" -gt 0 ] && alert stale "$n capture(s) have waited over an hour in notes-inbox and this poll didn't take them. See watcher.log."
}
trap stale_check EXIT

sleep 2  # let Chrome finish renaming .crdownload -> .md
find "$inbox" -maxdepth 1 -name '*.crdownload' -mmin +5 -delete 2>/dev/null

shopt -s nullglob
# The frontmatter block only. The body is page text, which can say anything:
# an article that quotes "video_id: abc" is still an article.
frontmatter() { awk 'NR == 1 && /^---$/ {f = 1; next} f && /^---$/ {exit} f' "$1"; }

attachments_of() { frontmatter "$1" | sed -En '/^(attachments|images):/,/^[^ ]/s/^  - //p'; }

# A capture is its .md plus every file its header lists under attachments:
# (images: in web captures from before capture/1), and later the
# <stem>-transcript.* captions, <stem>.proposals.json and <stem>.lowconf.json, beside it. The
# extension writes the .md only after its images have landed, so they always
# move together. A listed name with a "/" is refused: a record can only bring
# files from its own folder. Partial downloads (.crdownload) stay behind.
# Prints the new path.
move_capture() {
  local md="$1" dest="$2" dir stem f listed
  dir="$(dirname "$md")" stem="$(basename "${md%.md}")"
  listed="$(attachments_of "$md")"
  mv "$md" "$dest/" 2>/dev/null || return 1
  while IFS= read -r f; do
    case "$f" in ""|*/*) continue;; esac
    [ -e "$dir/$f" ] && mv "$dir/$f" "$dest/" 2>/dev/null
  done <<< "$listed"
  for f in "$dir/$stem"-img* "$dir/$stem"-transcript* "$dir/$stem".proposals.json "$dir/$stem".lowconf.json; do
    case "$f" in *.crdownload) continue;; esac
    mv "$f" "$dest/" 2>/dev/null
  done
  echo "$dest/$stem.md"
}

attempts() { cat "$failed/$(basename "${1%.md}").attempts" 2>/dev/null || echo 0; }
# What you save routes as soon as it lands, in a run of its own so it's quick
# (one page takes a few minutes, a batch of 10 up to 12). The rest goes on a
# 15-min schedule: a failed capture waits 15 min after each try, so a passing
# outage doesn't use up its 3 tries in minutes, and a screenshot backlog goes 5
# at a time, so the runs it keeps busy stay short and never hold up your next
# save for long. Names start with the capture date, so within each group the
# oldest go first.
backlog_every=14 backlog_per_run=5
backlog_stamp="$alert_stamps/backlog.stamp"
retry=()
for f in "$failed"/*.md; do
  [ "$(attempts "$f")" -lt $max_attempts ] || continue
  [ -z "$(find "$failed/$(basename "${f%.md}").attempts" -mmin -$backlog_every 2>/dev/null)" ] && retry+=("$f")
done
fresh=() backlog=()
for f in "$inbox"/*.md; do
  case "$(basename "$f")" in *-screenshot-*) backlog+=("$f");; *) fresh+=("$f");; esac
done
if [ ${#fresh[@]} -gt 0 ]; then
  files=("${fresh[@]}")
  [ ${#retry[@]} -gt 0 ] || [ ${#backlog[@]} -gt 0 ] && capped=1
else
  files=("${retry[@]}")
  if [ ${#backlog[@]} -gt 0 ] && [ -z "$(find "$backlog_stamp" -mmin -$backlog_every 2>/dev/null)" ]; then
    files+=("${backlog[@]:0:$backlog_per_run}")
    [ ${#backlog[@]} -gt $backlog_per_run ] && capped=1
    mkdir -p "$alert_stamps" && touch "$backlog_stamp"
  elif [ ${#backlog[@]} -gt 0 ]; then
    capped=1
  fi
fi
if [ ${#files[@]} -gt $max_per_run ]; then files=("${files[@]:0:$max_per_run}"); capped=1; fi

# Scans your phone saved into the vault, once iCloud has finished writing them
# (untouched for a minute).
scans=()
for f in "$hw_inbox"/*; do
  case "$(printf '%s' "${f##*.}" | tr '[:upper:]' '[:lower:]')" in pdf|jpg|jpeg|png|heic) ;; *) continue;; esac
  [ -n "$(find "$f" -mmin +1 2>/dev/null)" ] && scans+=("$f")
done
# Same per-poll cap as captures: a backlog of scans is transcribed 10 at a time.
if [ ${#scans[@]} -gt $max_per_run ]; then scans=("${scans[@]:0:$max_per_run}"); capped=1; fi
# Corrections downloaded from the review page, when scans are waiting on them.
corrections=()
[ -n "$(ls "$needs_review"/*.md 2>/dev/null)" ] && corrections=("$HOME/Downloads"/handwritten-corrections*.json)

waiting=$(( ${#files[@]} + ${#scans[@]} + ${#corrections[@]} ))
[ $waiting -eq 0 ] && exit 0   # nothing waiting -> silent, no cost

# Confirm claude is signed in before moving anything, so a signed-out claude
# leaves captures where they are. Only proves a token is present, not valid;
# a bad token fails the run, and verify.sh then sends the capture to failed/.
# Skipped for ad-hoc CLIP_CLAUDE_BIN runs; tests/ configures a stand-in that
# answers `auth`, so the suite still exercises this check.
if [ -z "$CLIP_CLAUDE_BIN" ] && ! "$claude_bin" auth status 2>/dev/null | grep -q '"loggedIn": *true'; then
  alert signin "Claude isn't signed in, so $waiting capture(s) are waiting. Set up the watcher's token (see README) or run claude auth login."
  exit 1
fi

moved=()
for f in "${files[@]}"; do
  new="$(move_capture "$f" "$processing")" && moved+=("$new")
done

# A new scan becomes a capture/1 record (docs/capture-record.md), with the scan
# attached and its transcript still to be written. HEIC, which the transcriber
# can't read, gets a JPEG copy beside it; both are kept.
pending_line="(transcript pending)"
yaml_str() { printf '"%s"' "$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')"; }
for f in "${scans[@]}"; do
  name="$(basename "$f")" stem="$(basename "${f%.*}")"
  if [ -e "$processing/$stem.md" ] || [ -e "$needs_review/$stem.md" ]; then
    echo "  ! scan $name has the same name as a capture already in progress; left in the inbox" >> "$log"; continue
  fi
  mv "$f" "$processing/" 2>/dev/null || continue
  list="  - $name"
  case "$name" in *.[hH][eE][iI][cC])
    sips -s format jpeg "$processing/$name" --out "$processing/$stem.jpg" >/dev/null 2>&1 && list="$list
  - $stem.jpg";;
  esac
  printf -- '---\nrecord: capture/1\nsource_type: scan\ntitle: %s\nsource: %s\ncaptured: %s\nreview: transcript\nattachments:\n%s\n---\n\n## Transcript\n\n%s\n' \
    "$(yaml_str "$stem")" "$(yaml_str "scan: $name")" "$(date -r "$processing/$name" '+%Y-%m-%d %H:%M')" "$list" "$pending_line" \
    > "$processing/$stem.md"
  moved+=("$processing/$stem.md")
done

# Approval: the review page's "Download corrections" saves every transcript on
# it to ~/Downloads/handwritten-corrections*.json. A file naming scans that wait
# here approves them: apply its text and route them in this run. A file that
# names none (an interactive /handwritten session's) is left where it is.
review_changed=0
for c in "${corrections[@]}"; do
  stems="$(python3 "$here/apply_corrections.py" "$c" "$needs_review")"
  [ -z "$stems" ] && continue
  while IFS= read -r stem; do
    new="$(move_capture "$needs_review/$stem.md" "$processing")" && moved+=("$new")
    echo "  ✓ transcript approved: $stem" >> "$log"
  done <<< "$stems"
  mv "$c" "$review_dir/applied-$(date +%Y%m%d-%H%M%S)-$(basename "$c")"
  review_changed=1
done
[ ${#moved[@]} -eq 0 ] && exit 0

echo "[$(date '+%Y-%m-%d %H:%M:%S')] processing ${#moved[@]} capture(s):" >> "$log"
printf '  %s\n' "${moved[@]}" >> "$log"

# A capture with `video_id:` is a Summarize-this-video request. Pull the caption
# track here rather than in the browser — yt-dlp lives on this side, and a caption
# file is ~50 KB against a ~400 MB video.
#
# A video capture carries NO content of its own — just a placeholder line — so the
# transcript is the only thing there is to summarize. If it can't be fetched, the
# capture is not routed at all: sending it on would ask the router to summarize
# nothing, and an empty summary in the archive is worse than no entry, because
# later claims would anchor to it. Such captures go to skipped/ as the paper
# trail; re-clip the video by hand (or "Paste text instead") to get it in.
#
# Only the captures claimed this run: done/ is a growing paper trail, and
# globbing it would re-fetch every past video every poll and append the
# transcript again.
# Scans still without a transcript get one from an unattended run with the same
# limits as routing (file tools only, no shell, web or MCP). A transcribed scan
# then waits in needs-review/ for you; it never routes before you approve it.
transcript_empty() { [ -z "$(awk '/^## Transcript$/ {f = 1; next} f' "$1" | grep -vxF "$pending_line" | tr -d '[:space:]')" ]; }
is_scan() { frontmatter "$1" | grep -qx 'source_type: scan'; }
to_transcribe=() others=()
for md in "${moved[@]}"; do
  if is_scan "$md" && grep -qxF "$pending_line" "$md"; then to_transcribe+=("$md"); else others+=("$md"); fi
done
if [ ${#to_transcribe[@]} -gt 0 ]; then
  tprompt="Transcribe these handwritten scans:

$(printf '%s\n' "${to_transcribe[@]}")

$(cat "$here/transcribe-scan.md")"
  ( cd "$processing" && "$claude_bin" -p "$tprompt" "${model_args[@]}" --restricted --strict-mcp-config --tools "Read,Write,Edit,Glob,Grep" \
      --permission-mode acceptEdits --add-dir "$processed" ) >> "$log" 2>&1
  for md in "${to_transcribe[@]}"; do
    stem="$(basename "${md%.md}")"
    if grep -qxF "$pending_line" "$md" || transcript_empty "$md"; then
      n=$(( $(attempts "$md") + 1 )); echo "$n" > "$failed/$stem.attempts"
      move_capture "$md" "$failed" >/dev/null
      echo "  ✗ not transcribed (attempt $n of $max_attempts): $stem.md" >> "$log"
      [ "$n" -ge $max_attempts ] && alert gave-up "Gave up transcribing $stem after $max_attempts tries. It's in notes-inbox-processed/failed; see watcher.log."
    else
      move_capture "$md" "$needs_review" >/dev/null
      echo "  ✎ transcribed, waiting for your review: $stem.md" >> "$log"
      review_changed=2
    fi
  done
fi
if [ $review_changed -gt 0 ]; then
  page="$(python3 "$here/review_page.py" "$needs_review" "$review_dir" "$skills_ref/build_review.py" 2>> "$log")"
  if [ $review_changed = 2 ] && [ -n "$page" ]; then
    n=$(ls "$needs_review"/*.md | wc -l | tr -d ' ')
    alert review "$n scan(s) are ready for your review. Check each transcript, then click Download corrections to approve."
    open "$page" >/dev/null 2>&1
  fi
fi

route=()
for md in "${others[@]}"; do
  vid=$(frontmatter "$md" | sed -n 's/^video_id:[[:space:]]*//p' | head -1)
  if [ -z "$vid" ]; then route+=("$md"); continue; fi
  if grep -q '^## Transcript (' "$md"; then route+=("$md"); continue; fi
  if command -v yt-dlp >/dev/null 2>&1; then
    vtt="${md%.md}-transcript" url="https://youtu.be/$vid"
    # Captions in the video's own language, human-made when they exist (yt-dlp
    # prefers them over auto-captions). Asking for "en,ko" blindly would pull
    # YouTube's machine translation of a Korean talk into English, and the
    # archive keeps the words as spoken. Unknown language: English or Korean.
    lang="$(yt-dlp --print '%(language)s' --skip-download --no-warnings "$url" 2>/dev/null | head -1)"
    case "$lang" in ""|NA) langs="en.*,ko.*";; *) langs="$lang.*";; esac
    ( cd "$(dirname "$md")" && yt-dlp --write-subs --write-auto-subs --sub-langs "$langs" \
        --sub-format vtt --skip-download --no-warnings -o "$(basename "$vtt")" \
        "$url" >/dev/null 2>&1 )
    # NOT `ls "$vtt"*.vtt | head -1`: nullglob is on, so an unmatched glob
    # disappears and that degrades to a bare `ls` of the cwd — which would hand
    # back an unrelated local file and append it as the "transcript".
    got=""
    for c in "$vtt.$lang.vtt" "$vtt"*.vtt; do [ -f "$c" ] && { got="$c"; break; }; done
    if [ -n "$got" ] && [ -f "$got" ]; then
      printf '\n\n## Transcript (captions, %s)\n\n' "$(basename "$got")" >> "$md"
      # strip vtt cues/timing to plain text, keep it readable for summarizing
      sed -e '1,/^$/d' -e '/-->/d' -e '/^WEBVTT/d' -e 's/<[^>]*>//g' "$got" \
        | awk 'NF && $0!=prev {print; prev=$0}' >> "$md"
      echo "  + transcript for $vid" >> "$log"
      route+=("$md")
    else
      echo "  ! NOT ROUTED — no captions for $vid, nothing to summarize: $md" >> "$log"
      move_capture "$md" "$skipped" >/dev/null
    fi
  else
    echo "  ! NOT ROUTED — yt-dlp missing, no transcript for $vid: $md" >> "$log"
    move_capture "$md" "$skipped" >/dev/null
  fi
done

# Every capture this run may have been a caption-less video — don't spend a Claude
# call on an empty file list.
if [ ${#route[@]} -eq 0 ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] nothing to route this run" >> "$log"
  exit 0
fi
file_list="$(printf '%s\n' "${route[@]}")"


# Copy each capture's attachments (images: in web captures from before
# capture/1) into the vault archive here, so the unattended run never needs a
# shell (see the claude call below). -n: a file already archived is never
# overwritten.
for md in "${route[@]}"; do
  attachments_of "$md" | while IFS= read -r img; do
    case "$img" in ""|*/*) continue;; esac   # only files from the record's own folder
    cp -n "$(dirname "$md")/$img" "$vault/Handwritten/archive/" 2>/dev/null
  done
done

# The routing instructions live in one file, route-capture.md, which the
# interactive /route-capture command also runs through (it starts this script),
# so the two paths can't drift apart the way archive naming did on Sep 3.
prompt="Route these capture records into the notes pipeline:

$file_list

$(sed "s/{{ROUTING_MAP}}/$routing_map/g" "$here/route-capture.md")"

cd "$vault" || { echo "  ERROR: vault not found" >> "$log"; exit 1; }
# The notes as they were before this run, so the faithfulness check (below)
# sees exactly what the run added.
snap="$processed/.notes-before"; rm -rf "$snap"; cp -R "$vault/Handwritten/notes" "$snap" 2>/dev/null
# The run reads untrusted web text, so it gets the least it needs. --restricted
# drops the tools that run commands or fetch URLs, ignores the user/project
# settings files (and their broad allow rules), and confines file tools to the
# vault and processed/. --strict-mcp-config loads no MCP servers, so there's no
# mail, Slack or browser to act through. --tools names the file tools, and only
# them. The quiz bank and build scripts are out of reach; see step (3).
"$claude_bin" -p "$prompt" "${model_args[@]}" --restricted --strict-mcp-config --tools "Read,Write,Edit,Glob,Grep" \
  --permission-mode acceptEdits --add-dir "$processed" >> "$log" 2>&1
rc=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] done (exit $rc)" >> "$log"

# The exit code only says the run ended. verify.sh checks, per capture, that
# the work reached the vault; that alone decides done/ or failed/.
failures=0 gave_up=0 report=""
for md in "${route[@]}"; do
  stem="$(basename "${md%.md}")"
  if why="$("$here/verify.sh" "$md" "$vault")"; then
    move_capture "$md" "$done_dir" >/dev/null
    rm -f "$failed/$stem.attempts"
    where="$(printf '%s' "$why" | tr '\n' ',')"   # archive file, then the notes citing it
    echo "  ✓ routed: $stem.md → $where" >> "$log"
    report+="done	$done_dir/$stem.md	$where"$'\n'
  else
    n=$(( $(attempts "$md") + 1 ))
    echo "$n" > "$failed/$stem.attempts"
    move_capture "$md" "$failed" >/dev/null
    echo "  ✗ not routed (attempt $n of $max_attempts): $stem.md — $why" >> "$log"
    report+="failed	$failed/$stem.md	$why (attempt $n of $max_attempts)"$'\n'
    failures=$((failures + 1))
    [ "$n" -ge $max_attempts ] && gave_up=$((gave_up + 1))
  fi
done
# Faithfulness: one read-only Claude call checks what each filed capture added
# to the notes against its verbatim archive file (check-faithfulness.md). It
# reports a score per capture in What's new; it never changes an outcome.
done_list="$(printf '%s' "$report" | awk -F'\t' '$1=="done"{n=$2; sub(/.*\//,"",n); sub(/\.md$/,"",n); split($3,a,","); print n "\tHandwritten/archive/" a[1]}')"
if [ -n "$done_list" ] && [ -d "$snap" ]; then
  fprompt="$(cat "$here/check-faithfulness.md")

Captures (name, then its archive file):
$done_list

What the topic notes gained in this run:
$(python3 "$here/faithfulness.py" added "$snap" "$vault/Handwritten/notes")"
  "$claude_bin" -p "$fprompt" "${model_args[@]}" --restricted --strict-mcp-config --tools "Read,Glob,Grep" 2>> "$log" \
    | python3 "$here/faithfulness.py" apply "$done_dir" $(printf '%s\n' "$done_list" | cut -f1) >> "$log" 2>&1
fi
rm -rf "$snap"
# Apply the quiz/keyword proposals of the captures that made it, then rebuild
# the notes, quiz and map once. The hooks that normally rebuild on each edit
# don't fire under --restricted.
done_props=()
for md in "${route[@]}"; do
  f="$done_dir/$(basename "${md%.md}").proposals.json"; [ -f "$f" ] && done_props+=("$f")
done
if [ ${#done_props[@]} -gt 0 ]; then
  python3 "$here/merge_proposals.py" --refs "$skills_ref" --notes "$vault/Handwritten/notes" "${done_props[@]}" >> "$log" 2>&1 \
    || alert merge "Couldn't apply quiz/keyword proposals; see watcher.log."
fi
# One What's new entry per run: each capture's source, title and where it went
# (or why not). build_html.py attaches this report to the run's entry.
printf '%s' "$report" | ROUTE_MODEL="${CLAUDE_MODEL:-account default}" python3 "$here/route_report.py" "$skills_ref/routing-pending.json" >> "$log" 2>&1
{ python3 "$skills_ref/build_quiz.py" && python3 "$skills_ref/build_html.py"; } >> "$log" 2>&1 \
  || alert build "Rebuilding the notes HTML failed; see watcher.log."

if [ $gave_up -gt 0 ]; then
  alert gave-up "Gave up on $gave_up capture(s) after $max_attempts tries. They're in notes-inbox-processed/failed; see watcher.log."
elif [ $failures -gt 0 ]; then
  alert failed "$failures capture(s) didn't reach the vault (claude exit $rc). Retrying on the next poll; see watcher.log."
fi

# open the rendered hub ONCE, after all routing + rebuilds are complete
[ -f "$previews/handwritten-notes-index.html" ] && open "$previews/handwritten-notes-index.html" >/dev/null 2>&1 || true
exit $(( failures > 0 ))  # 1 when any capture failed, so `launchctl print` shows it
