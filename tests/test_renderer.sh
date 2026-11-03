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
# R7-2: a page keeps its address when a later note would have sorted ahead of it.
mk() { printf -- '---\ntitle: "T %s"\n---\n# T %s\n\n## Part\n\nbody\n' "$1" "$1" > "$NOTES_VAULT/Handwritten/notes/$1_note.md"; }
rm -f "$R/pages.json"   # a fresh setup: no page names given out yet
mk "AI_PM"; build; mk "AI-PM"; build
check "R7-2: an existing note keeps its page address when a colliding note is added" \
  eval 'grep -q "<h1>T AI_PM</h1>" "$NOTES_OUT/handwritten-ai-pm.html" && grep -q "<h1>T AI-PM</h1>" "$NOTES_OUT/handwritten-ai-pm-2.html"'
rm "$NOTES_VAULT/Handwritten/notes/AI_PM_note.md"; mk "AI PM"; build
check "...and a deleted note's address isn't handed to a different note" \
  eval '! grep -q "<h1>T AI PM</h1>" "$NOTES_OUT/handwritten-ai-pm.html" && grep -lq "<h1>T AI PM</h1>" "$NOTES_OUT"/handwritten-ai-pm-*.html'
rm -f "$NOTES_VAULT/Handwritten/notes/"*_note.md
# A new user's pages, built from the starter notes folder: no handwriting
# wording on web clips, and the settings note isn't shown as a topic.
rm -f "$NOTES_VAULT/Handwritten/notes/"*_note.md "$R/pages.json"
cp "$here/../starter-vault/Handwritten/notes/"*.md "$NOTES_VAULT/Handwritten/notes/"
mk "Cooking"; build; IDX="$NOTES_OUT/handwritten-notes-index.html"
check "pages for web clips don't talk about handwriting or scans" \
  eval '! grep -qiE "handwriting|source scans|handwritten notes|Handwritten/notes" "$IDX" "$NOTES_OUT/handwritten-quiz.html" "$NOTES_OUT/handwritten-knowledge-map.html" "$NOTES_OUT/handwritten-cooking.html"'
check "the routing map is a settings note: not a tab, card, map node or search result" \
  eval '! grep -q "Routing map" "$IDX" "$NOTES_OUT/handwritten-cooking.html" "$NOTES_OUT/handwritten-knowledge-map.html" "$NOTES_OUT/handwritten-search-index.js"'
check "General stays hidden until something is filed into it" eval '! grep -q ">General<" "$IDX"'
printf -- '\n## Odds and ends\n- a filed idea\n' >> "$NOTES_VAULT/Handwritten/notes/General_note.md"; build
check "...and shows up once it has content" eval 'grep -q ">General<" "$IDX"'
rm -f "$NOTES_VAULT/Handwritten/notes/"*.md
# Help: one page on how to use it, reached from the ? on every page.
rm -f "$NOTES_VAULT/Handwritten/notes/"*.md "$R/pages.json"; mk "Cooking"; mk "Help"; build
H="$NOTES_OUT/handwritten-help.html"
all_link_help() { for f in "$NOTES_OUT"/handwritten-*.html; do grep -q 'class="helpbtn"[^>]*href="handwritten-help.html"\|href="handwritten-help.html"[^>]*class="helpbtn"\|<a class="helpbtn" href="handwritten-help.html"' "$f" || return 1; done; }
check "every page has the ? button linking the help page" all_link_help
check "the help page covers the extension, scans, the model, the map and the quiz" \
  eval 'grep -q "id=\"install\"" "$H" && grep -q "id=\"scans\"" "$H" && grep -q "id=\"model\"" "$H" && grep -q "id=\"map\"" "$H" && grep -q "id=\"quiz\"" "$H"'
check "the help page says plainly what leaves the Mac and where it goes" eval 'grep -q "What leaves your Mac:" "$H" && grep -q "Anthropic or OpenAI" "$H"'
check "a note called Help gets its own page and can't overwrite the help page" \
  eval 'grep -q "How to use Notes-Clipper</h1>" "$H" && grep -lq "<h1>T Help</h1>" "$NOTES_OUT"/handwritten-help-*.html'
check "pages carry the Notes-Clipper name and the note favicon, and no emoji in the chrome" \
  eval 'grep -q ">Notes-Clipper</a>" "$NOTES_OUT/handwritten-cooking.html" && grep -q "%F0%9F%93%9D" "$NOTES_OUT/handwritten-cooking.html" && ! grep -qE "📓|🕸|🔔|⭐|🏆" "$NOTES_OUT"/handwritten-*.html'
rm -f "$NOTES_VAULT/Handwritten/notes/"*.md
# renderer-config.json: personal settings beside the data, read when no
# environment is set (a note-edit hook), so the scripts themselves stay shared.
rm -f "$NOTES_VAULT/Handwritten/notes/"*.md "$R/pages.json"; mk "Zeta"; mk "Alpha"; mk "PM_UX"
printf 'Zeta talks about rare term here\n' >> "$NOTES_VAULT/Handwritten/notes/Zeta_note.md"
echo '[{"id":"pmux-01","note":"PM_UX","topic":"t","src":"s","q":"q?","opts":["a","b","c","d"],"a":0,"explain":"e"}]' > "$R/quiz-bank.json"
python3 -c "import json,sys; json.dump({'vault':sys.argv[1],'out':sys.argv[2],'tab_order':['Zeta_note.md'],'map_terms':['rare term'],'display_names':{'PM_UX':'PM / UX'}},open(sys.argv[3],'w'))" "$NOTES_VAULT" "$T/cfgout" "$R/renderer-config.json"
( unset NOTES_VAULT NOTES_OUT; PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" python3 "$R/build_quiz.py" && PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" python3 "$R/build_html.py" ) > "$T/out" 2>&1
first_tab() { grep -o 'class="tab[^"]*" href="[^"]*"' "$T/cfgout/handwritten-alpha.html" | head -1 | grep -q "handwritten-zeta.html"; }
check "with no environment, the config's folders are used" eval '[ -s "$T/cfgout/handwritten-notes-index.html" ]'
check "...its tab order puts Zeta first" first_tab
check "...its map terms appear on the map, and its display names in the quiz" \
  eval 'grep -q "rare term" "$T/cfgout/handwritten-knowledge-map.html" && grep -q "PM / UX" "$T/cfgout/handwritten-quiz.html"'
echo '{"tab_order": "not a list", "map_terms": [1, 2]' > "$R/renderer-config.json"
( PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" python3 "$R/build_html.py" ) > "$T/out" 2>&1; rcb=$?
check "a broken config is ignored: the pages still build with the defaults" eval '[ $rcb = 0 ]'
rm -f "$R/renderer-config.json" "$NOTES_VAULT/Handwritten/notes/"*.md
check "diagrams render in Mermaid's strict mode (no script callbacks from diagram text)" \
  eval '! grep -q "securityLevel:.loose" "$here/../renderer/build_html.py" && grep -q "securityLevel:.strict" "$here/../renderer/build_html.py"'
rm -rf "$T"

echo
echo "renderer: $pass passed, $fail failed"
[ "$fail" = 0 ]
