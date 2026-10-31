#!/usr/bin/env bash
# Capture-record tests: watcher/validate_record.py must accept a well-formed
# record from every source and reject each way a record can be wrong, because
# everything downstream (queue, router, verify.sh) trusts what it accepts.
# Fixtures are written into a temp dir, so nothing binary lives in the repo.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
validate="$here/../watcher/validate_record.py"
D="$(mktemp -d)"; trap 'rm -rf "$D"' EXIT
pass=0 fail=0
echo pdf > "$D/page.pdf"; echo png > "$D/shot.png"; echo png > "$D/img1.png"

rec() {  # rec NAME HEADER-LINES [BODY]
  printf -- '---\n%s\n---\n\n%s\n' "$2" "${3:-body text}" > "$D/$1.md"
}
expect() {  # expect ok|reject NAME [text the complaint must contain]
  local out rc; out="$(python3 "$validate" "$D/$2.md" 2>&1)"; rc=$?
  if { [ "$1" = ok ] && [ $rc = 0 ]; } || { [ "$1" = reject ] && [ $rc = 1 ] && grep -q -- "${3:-}" <<< "$out"; }; then
    pass=$((pass+1)); echo "  ok    $1: $2"
  else
    fail=$((fail+1)); echo "  FAIL  $1: $2"; sed 's/^/        | /' <<< "$out"
  fi
}
base='record: capture/1
title: "A title"
captured: 2026-09-28 10:00'

# ---- one good record per source -------------------------------------------
rec web "$base
source_type: web
source: \"https://example.com/a\"
attachments:
  - img1.png" "## Clip 1

> quoted"
expect ok web
rec scan "$base
source_type: scan
source: \"scan: page.pdf\"
review: transcript
attachments:
  - page.pdf" "## Transcript

a word[?] and [illegible?]"
expect ok scan
rec shot "$base
source_type: screenshot
source: \"file: shot.png\"
category: DESIGN
attachments:
  - shot.png" "## Text in the screenshot

DESIGN articulates the solution"
expect ok shot
rec note "$base
source_type: note
source: \"pasted\""
expect ok note
rec legacy 'type: web-capture
title: "Saved before capture/1"
source: "https://example.com/b"
captured: 2026-09-27 23:49
images:
  - img1.png' "## Clip 1 — image

![[img1.png]]"
expect ok legacy      # the extension's current format needs no change
rec escaped "$base
source_type: note
source: \"pasted\"
title: \"He said \\\"hi\\\" in C:\\\\new\""
expect ok escaped     # JSON-escaped titles (the extension writes them this way)

# ---- each way a record can be wrong -----------------------------------------
rec missing_file "$base
source_type: web
source: \"https://example.com/a\"
attachments:
  - gone.png" "x"
expect reject missing_file "gone.png is not beside"
rec scan_no_review "$base
source_type: scan
source: \"scan: page.pdf\"
attachments:
  - page.pdf" "## Transcript"
expect reject scan_no_review "review: transcript"
rec scan_wrong_file "$base
source_type: scan
source: \"scan: other.pdf\"
review: transcript
attachments:
  - page.pdf" "## Transcript"
expect reject scan_wrong_file "scan: <file>"
rec scan_no_transcript "$base
source_type: scan
source: \"scan: page.pdf\"
review: transcript
attachments:
  - page.pdf" "just text"
expect reject scan_no_transcript "Transcript section"
rec shot_mindset "$base
source_type: screenshot
source: \"file: shot.png\"
category: MINDSET
attachments:
  - shot.png"
expect reject shot_mindset "category must be"      # other categories stay out of the queue
rec web_no_url "$base
source_type: web
source: \"pasted\""
expect reject web_no_url "page URL"
rec note_review "$base
source_type: note
source: \"pasted\"
review: transcript"
expect reject note_review "only scan records take review"
rec note_video "$base
source_type: note
source: \"pasted\"
video_id: abc123def"
expect reject note_video "video_id"
rec empty_note "$base
source_type: note
source: \"pasted\"" " "
expect reject empty_note "body"
rec bad_date 'record: capture/1
source_type: note
title: "t"
source: "pasted"
captured: yesterday'
expect reject bad_date "captured must be"
rec unknown_type "$base
source_type: podcast
source: \"pasted\""
expect reject unknown_type "source_type must be"
# The header decides, never the body: page text that looks like a header field
# (the G6 bug, for video_id) must not change how the record is read.
rec body_fields "$base
source_type: scan
source: \"scan: page.pdf\"
attachments:
  - page.pdf" "## Transcript

review: transcript
source_type: note"
expect reject body_fields "review: transcript"

echo
echo "records: $pass passed, $fail failed"
[ "$fail" = 0 ]
