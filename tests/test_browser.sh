#!/usr/bin/env bash
# Browser tests: build every page with an injection planted in every field a
# capture can reach, then have headless Chrome use the pages — every quiz
# screen, every map card, What's new, search, highlighting — and fail if any
# planted code runs. Text from a captured web page must only ever show as text.
# Needs python3, pandoc and Google Chrome; reports SKIPPED without Chrome.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
[ -x "$CH" ] || { echo "browser: SKIPPED (Google Chrome not found)"; exit 0; }
pass=0 fail=0
check() { local d="$1"; shift; if "$@"; then pass=$((pass+1)); echo "  ok    $d"
          else fail=$((fail+1)); echo "  FAIL  $d"; fi; }

T="$(mktemp -d)"; export NOTES_VAULT="$T/notes" NOTES_OUT="$T/pages"
R="$T/refs"; NOTES="$NOTES_VAULT/Handwritten/notes"; mkdir -p "$R" "$NOTES" "$NOTES_VAULT/Handwritten/archive"
for f in build_html.py build_quiz.py; do ln -s "$here/../renderer/$f" "$R/$f"; done
cp "$here/../renderer/mermaid.min.js" "$R/"

# The payload marks the page if it ever runs. A note's filename can carry it
# too: the router creates topic notes, so their names come from captures.
P="<img src=x onerror=\"document.documentElement.setAttribute('data-pwned','1')\">"
EVIL="Evil${P}"
printf -- '---\ntitle: "Plain"\n---\n# Plain\n\n## Basics\n\ncontext layer and agent words\n' > "$NOTES/Plain_note.md"
printf -- '---\ntitle: "기초"\n---\n# 기초\n\n## 개념\n\nagent 기초\n' > "$NOTES/기초 개념_note.md"
printf -- '---\ntitle: "Quiz topic"\n---\n# Quiz topic\n\n## Part\n\nagent\n' > "$NOTES/Quiz_note.md"
printf -- '---\ntitle: "%s"\ntags: [x]\n---\n# Evil\n\n## Heading %s\n\ncontext layer with %s and agent\n' "$P" "$P" "$P" > "$NOTES/${EVIL}_note.md"
python3 - "$R" "$P" "$EVIL" <<'PY'
import json, sys
r, p, evil = sys.argv[1:]
q = lambda i, note: {"id": f"{note}-0{i}", "note": note, "topic": "T " + p, "src": "S " + p, "q": f"Q{i} " + p,
                     "opts": ["A " + p, "B", "C", "D"], "a": 1, "explain": "E " + p, "level": "apply", "type": "scenario"}
json.dump([q(1, evil), q(2, evil), q(3, "Plain"), q(4, "기초 개념"), q(5, "Quiz")], open(f"{r}/quiz-bank.json", "w"))
json.dump(["context layer", "agent", p], open(f"{r}/glossary-extra.json", "w"))
json.dump([{"title": p, "type": "web", "state": "done", "notes": [evil], "archive": "a.md", "link": "file:///x"},
           {"title": p, "type": "web", "state": "failed", "why": p, "link": "x"}], open(f"{r}/routing-pending.json", "w"))
PY
build() { PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" python3 "$R/build_quiz.py" && PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" python3 "$R/build_html.py"; } > "$T/out" 2>&1
build
check "the pages build with the payload in every field" eval '[ -s "$NOTES_OUT/handwritten-quiz.html" ] && [ -s "$NOTES_OUT/handwritten-knowledge-map.html" ]'

# drive PAGE "JS" [QUERY]: a copy of the page with a script that uses it, run in
# Chrome; prints "pwned" if any planted code ran, "clean" if not, "broken" if the
# page never reached the end of the script.
drive() {
  local page="$NOTES_OUT/$1" copy="$NOTES_OUT/drive-$1"
  { cat "$page"; printf '<script>try{%s}catch(e){document.documentElement.setAttribute("data-err",String(e))}document.documentElement.setAttribute("data-done","1")</script>' "$2"; } > "$copy"
  perl -e 'alarm 60; exec @ARGV' "$CH" --headless=new --disable-gpu --no-first-run --no-default-browser-check \
    --user-data-dir="$T/chrome" --allow-file-access-from-files --virtual-time-budget=5000 \
    --dump-dom "file://$copy${3:-}" 2>/dev/null > "$T/dom"
  if grep -q 'data-pwned="1"' "$T/dom"; then echo pwned
  elif grep -q 'data-done="1"' "$T/dom" && ! grep -q 'data-err=' "$T/dom"; then echo clean
  else echo broken; grep -o 'data-err="[^"]*"' "$T/dom" >&2; fi
}

QUIZ='const sel=document.getElementById("topic"); for (const o of [...sel.options]) { sel.value=o.value; }
sel.value="__all"; document.getElementById("start").click();
for (let k=0; k<12 && document.querySelector(".opt"); k++) { document.querySelector(".opt").click(); document.getElementById("next").click(); }
if (!document.querySelector(".big")) throw "quiz never reached its results";'
check "quiz: topic list, every question, its answer and the results screen run no planted code" eval '[ "$(drive handwritten-quiz.html "$QUIZ")" = clean ]'

LINKS='document.getElementById("start").click(); const seen=new Set();
for (let k=0; k<12 && document.querySelector(".opt"); k++) { document.querySelector(".opt").click(); document.querySelectorAll(".src a").forEach(a=>seen.add(a.getAttribute("href"))); document.getElementById("next").click(); }
document.querySelectorAll(".src a").forEach(a=>seen.add(a.getAttribute("href")));
document.documentElement.setAttribute("data-links",[...seen].join(" "));'
all_exist() { [ $# -gt 0 ] || return 1; for l in "$@"; do [ -e "$NOTES_OUT/$l" ] || return 1; done; }
drive handwritten-quiz.html "$LINKS" > /dev/null; links="$(sed -n 's/.*data-links="\([^"]*\)".*/\1/p' "$T/dom")"
check "quiz links to a note's page reach the page the build wrote (same page-name rule)" \
  all_exist $links

MAP='for (let i=0; i<N.length; i++) card(i); if (!document.querySelector("#card h3")) throw "no card shown";'
check "map: every node's card runs no planted code" eval '[ "$(drive handwritten-knowledge-map.html "$MAP")" = clean ]'

USE='document.getElementById("wn-fab").click(); if (!document.querySelector("#wn-body .rec")) throw "no What'"'"'s new";
const b=document.getElementById("q"); b.value="context"; b.dispatchEvent(new Event("input")); b.value="Heading"; b.dispatchEvent(new Event("input"));'
for p in handwritten-notes-index.html $(cd "$NOTES_OUT" && ls handwritten-evil*.html handwritten-plain.html); do
  check "$p: What's new, search and ?q= highlighting run no planted code" eval '[ "$(drive "$p" "$USE" "?q=context")" = clean ]'
done
check "the note keeps its content: the planted image stays, minus its handler" \
  eval 'grep -q "Heading <img src=\"x\"" "$NOTES_OUT"/handwritten-evil*.html && ! grep -qE "<img[^>]* onerror" "$NOTES_OUT"/handwritten-evil*.html'
rm -rf "$T"

echo
echo "browser: $pass passed, $fail failed"
[ "$fail" = 0 ]
