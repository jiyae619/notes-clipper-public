#!/usr/bin/env bash
# verify.sh CAPTURE.md VAULT — did this capture actually reach the vault?
#
# Exit codes say a routing run ended, not that the work happened: on Sep 3 a
# run that couldn't read its capture refused to route and still exited 0. So
# check the vault itself. A capture is routed when:
#   1. an archive file names it as its original_capture,
#   2. that archive file keeps the capture's source URL,
#   3. every attachment it lists (images: in older web captures) is in the archive, and
#   4. a topic note cites that archive file (the summary was integrated).
# Prints why and exits 1 at the first check that fails. When all pass, prints
# the archive file and the notes citing it, one per line.
capture="$1" vault="$2"
archive="$vault/Handwritten/archive" notes="$vault/Handwritten/notes"
name="$(basename "$capture")"
frontmatter() { awk 'NR == 1 && /^---$/ {f = 1; next} f && /^---$/ {exit} f' "$capture"; }

hit=""
for a in "$archive"/*.md; do
  sed -n '/^original_capture:/p' "$a" 2>/dev/null | grep -qF -- "$name" && { hit="$a"; break; }
done
[ -n "$hit" ] || { echo "no archive file names $name as its original_capture"; exit 1; }

src="$(frontmatter | sed -n 's/^source: *"\{0,1\}\([^"]*\)"\{0,1\} *$/\1/p' | head -1)"
if [ -n "$src" ] && ! grep -qF -- "$src" "$hit"; then
  echo "$(basename "$hit") doesn't keep the source URL"; exit 1
fi

while IFS= read -r img; do
  [ -e "$archive/$img" ] || { echo "image $img wasn't copied into the archive"; exit 1; }
done < <(frontmatter | sed -En '/^(attachments|images):/,/^[^ ]/s/^  - //p')

cited="$(grep -lF -- "$(basename "$hit")" "$notes"/*.md 2>/dev/null)"
[ -n "$cited" ] || { echo "no topic note cites $(basename "$hit")"; exit 1; }
# Routed: say where it landed, for the What's new routing report. The archive
# file on the first line, then each topic note that cites it.
basename "$hit"
while IFS= read -r n; do basename "$n" _note.md; done <<< "$cited"
exit 0
