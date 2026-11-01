#!/usr/bin/env bash
# Page builder tests: run the real renderer/ scripts on a throwaway notes folder.
# Quiz questions, map concepts and note text come from captured web pages, so
# none of it may be able to close a <script> tag and run code of its own.
# Needs python3 and pandoc.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
pass=0 fail=0
check() { local d="$1"; shift; if "$@"; then pass=$((pass+1)); echo "  ok    $d"
          else fail=$((fail+1)); echo "  FAIL  $d"; tail -5 "$T/out" | sed 's/^/        | /'; fi; }

T="$(mktemp -d)"; export NOTES_VAULT="$T/notes" NOTES_OUT="$T/pages"
R="$T/refs"; mkdir -p "$R" "$NOTES_VAULT/Handwritten/notes" "$NOTES_VAULT/Handwritten/archive"
for f in build_html.py build_quiz.py; do ln -s "$here/../renderer/$f" "$R/$f"; done
build() { PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" python3 "$R/build_quiz.py" > "$T/out" 2>&1 \
          && PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" python3 "$R/build_html.py" >> "$T/out" 2>&1; }
scripts() {   # script elements the browser would see in one page
  python3 -c '
import sys; from html.parser import HTMLParser
class P(HTMLParser):
    n = 0
    def handle_starttag(s, t, a): P.n += t == "script"
P().feed(open(sys.argv[1]).read()); print(P.n)' "$NOTES_OUT/$1"; }

# A clean build first: the script count every page should keep.
printf -- '---\ntitle: "Topic"\n---\n# Topic\n\n## Basics\n\nplain words about context layer\n' > "$NOTES_VAULT/Handwritten/notes/Topic_note.md"
echo '[{"id":"topic-01","note":"Topic","topic":"t","src":"s","q":"plain?","opts":["a","b","c","d"],"a":0,"explain":"e"}]' > "$R/quiz-bank.json"
echo '["context layer"]' > "$R/glossary-extra.json"
build; pages="handwritten-quiz.html handwritten-knowledge-map.html handwritten-notes-index.html handwritten-topic.html"
for p in $pages; do eval "clean_$(echo "$p" | tr -c 'a-z\n' _)=$(scripts "$p")"; done

# Now the same, with a closing script tag in every field a capture can reach.
X='</script><script>window.pwned=1</script>'
printf -- '---\ntitle: "Topic"\n---\n# Topic\n\n## Basics\n\nplain words about context layer and %s\n\n## %s\n\nmore\n' "$X" "$X" \
  > "$NOTES_VAULT/Handwritten/notes/Topic_note.md"
python3 - "$R" "$X" <<'PY'
import json, sys
r, x = sys.argv[1], sys.argv[2]
q = {"id": "topic-02", "note": "Topic", "topic": x, "src": x, "q": "Which? " + x,
     "opts": [x, "b", "c", "d"], "a": 0, "explain": x}
bank = json.load(open(f"{r}/quiz-bank.json")); bank.append(q)
json.dump(bank, open(f"{r}/quiz-bank.json", "w"))
json.dump(["context layer", x], open(f"{r}/glossary-extra.json", "w"))
json.dump([{"title": x, "type": "web", "state": "done", "notes": ["Topic"], "archive": "a.md", "link": "x"}],
          open(f"{r}/routing-pending.json", "w"))
PY
build
check "the pages still build with a closing script tag in the notes, quiz, map concepts and What's new" eval '[ -s "$NOTES_OUT/handwritten-quiz.html" ]'
for p in $pages; do
  v="clean_$(echo "$p" | tr -c 'a-z\n' _)"
  check "$p: injected text adds no script element (${!v} before and after)" eval '[ "$(scripts "$p")" = "${!v}" ]'
done
check "no page carries the injected tag as live markup" eval '! grep -l "</script><script>window.pwned" "$NOTES_OUT"/*.html'
check "the quiz still holds the question word for word once the page reads it" eval 'python3 - "$NOTES_OUT/handwritten-quiz.html" "$X" <<'"'"'PY'"'"'
import json, sys
page, x = open(sys.argv[1]).read(), sys.argv[2]
i = page.index("const BANK=") + len("const BANK=")
bank, _ = json.JSONDecoder().raw_decode(page, i)
assert any(q["q"] == "Which? " + x and q["opts"][0] == x for q in bank)
PY'
printf -- '---\ntitle: "Topic"\n---\n# Topic\n\n## Basics\n\nA <img src=x onerror="window.pwned=1"> and [a link](javascript:window.pwned=1) and <a href="javascript:void(0)" onclick="window.pwned=1">another</a>.\n\nKept: one<br/>two, <i>it</i>, <b>bold</b>, <u>under</u>, and [a real link](https://example.com).\n\n`<script>code stays code</script>`\n' > "$NOTES_VAULT/Handwritten/notes/Topic_note.md"
build; P="$NOTES_OUT/handwritten-topic.html"
check "event handlers and javascript: links from a note are dropped" \
  eval '! grep -qiE "<[a-z][^>]* on(error|click)=|href=\"javascript:" "$P"'
check "the formatting notes use on purpose still renders: <br/>, <i>, <b>, <u>, real links" \
  eval 'grep -q "one<br/>two" "$P" && grep -q "<i>it</i>" "$P" && grep -q "<b>bold</b>" "$P" && grep -q "<u>under</u>" "$P" && grep -q "href=\"https://example.com\"" "$P"'
check "code that shows a tag stays visible as code" eval 'grep -q "<code>&lt;script&gt;code stays code&lt;/script&gt;</code>" "$P"'
printf -- '---\ntitle: "Topic"\n---\n# Topic\n\n## Basics\n\n![[scan.pdf#"><img src=x onerror="window.pwned=1">]]\n\n![[scan.pdf#page=3]]\n' > "$NOTES_VAULT/Handwritten/notes/Topic_note.md"
build
check "a scan embed's #fragment can't break out of its link (it is put back after the sanitizer runs)" \
  eval '! grep -qiE "<[a-z][^>]* on(error|click)=" "$P" && [ "$(scripts handwritten-topic.html)" = "$clean_handwritten_topic_html" ]'
check "...while a plain page fragment still links to that page" eval 'grep -q "scan.pdf#page=3\"" "$P"'
# Topic notes are created by the router, so a filename is capture-controlled too.
EVIL="$NOTES_VAULT/Handwritten/notes/x\"><img"$'\t'"src=x"$'\t'"onerror=window.pwned=1>_note.md"
printf -- '---\ntitle: "Odd"\n---\n# Odd\n\nbody\n' > "$EVIL"; build
check "a topic note's filename can't inject markup into the tab bar, index or map" \
  eval '! grep -lqiE "<[a-z][^>]*[[:space:]]on(error|click)=" "$NOTES_OUT"/*.html && [ "$(scripts handwritten-notes-index.html)" = "$clean_handwritten_notes_index_html" ]'
check "...and its page still gets built under a plain name" eval 'ls "$NOTES_OUT" | grep -qE "^handwritten-x-img-src-x-onerror-window-pwned-1\.html$"'
rm -f "$EVIL"
# R5-1: names that reduce to the same page, or to a built-in page, must not
# overwrite each other; names in any script keep their own page.
rm -f "$NOTES_VAULT/Handwritten/notes/"*_note.md
for n in "AI_PM" "AI-PM" "Quiz" "기초 개념" "심화 개념" "!!!"; do
  printf -- '---\ntitle: "T %s"\n---\n# T %s\n\n## Part\n\nbody of %s\n' "$n" "$n" "$n" > "$NOTES_VAULT/Handwritten/notes/${n}_note.md"; done
build
pages_with() { grep -l "<h1>T $1</h1>" "$NOTES_OUT"/handwritten-*.html 2>/dev/null | wc -l | tr -d ' '; }
each_own_page() { for n in "AI_PM" "AI-PM" "Quiz" "기초 개념" "심화 개념" "!!!"; do [ "$(pages_with "$n")" = 1 ] || return 1; done; }
tabs_exist() { for l in $(grep -o 'class="tab[^"]*" href="[^"]*"' "$NOTES_OUT/handwritten-notes-index.html" | sed 's/.*href="//; s/"$//'); do [ -e "$NOTES_OUT/$l" ] || return 1; done; }
check "R5-1: six notes whose names collide or are unusual get six separate pages" each_own_page
check "...a note called Quiz doesn't overwrite the quiz page" eval 'grep -q "const BANK=" "$NOTES_OUT/handwritten-quiz.html"'
check "...names in another script keep their letters" eval 'ls "$NOTES_OUT" | grep -q "기초"'
check "...and every tab links to a page that exists" tabs_exist
rm -f "$NOTES_VAULT/Handwritten/notes/"*_note.md
check "diagrams render in Mermaid's strict mode (no script callbacks from diagram text)" \
  eval '! grep -q "securityLevel:.loose" "$here/../renderer/build_html.py" && grep -q "securityLevel:.strict" "$here/../renderer/build_html.py"'
rm -rf "$T"

echo
echo "renderer: $pass passed, $fail failed"
[ "$fail" = 0 ]
