#!/usr/bin/env python3
"""Render Handwritten/notes/*.md into styled HTML previews with a tab menu,
per-page section nav (TOC), and a keyword knowledge map.
Output: $NOTES_OUT/handwritten-*.html . Reusable each round."""
import os, re, math, subprocess, urllib.parse, html, json, glob, datetime, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import pages, theme

def js_json(obj, **kw):
    """JSON for embedding inside <script>: '<' is escaped, so text from a capture
    (a quiz question, a title, a keyword) can never close the tag and start its own."""
    return json.dumps(obj, **kw).replace("<", "\\u003c")

# Paths come from the environment (the watcher sets them from watcher.env);
# the defaults are the README's standard layout.
VAULT     = os.path.expanduser(os.environ.get("NOTES_VAULT", "~/Documents/Notes"))
NOTES_DIR = os.path.join(VAULT, "Handwritten/notes")
ARCHIVE   = os.path.join(VAULT, "Handwritten/archive")
OUT       = os.path.expanduser(os.environ.get("NOTES_OUT", "~/Documents/Notes Pages"))

# Handwritten-scan PDFs are named for whatever was scribbled on the scan — fine
# as a filename, not fine surfaced as a citation — so pages show them as
# "Notebook scan N". The real filename is still the link target.
# Filenames of PDFs in archive/ that are published documents, not your scans,
# shown under their own names. Add yours here.
_OFFICIAL_DOCS = set()
def _scan_labels():
    try:
        pdfs = sorted(f for f in os.listdir(ARCHIVE) if f.lower().endswith(".pdf"))
    except OSError:
        return {}
    private = sorted((f for f in pdfs if f not in _OFFICIAL_DOCS), key=str.lower)
    return {f: f"Notebook scan {i}" for i, f in enumerate(private, 1)}
SCAN_LABEL = _scan_labels()
INDEX = "handwritten-notes-index.html"
MAP   = "handwritten-knowledge-map.html"
QUIZ  = "handwritten-quiz.html"
os.makedirs(OUT, exist_ok=True)
# Note pages load mermaid.min.js from beside them; it ships next to this script.
_MERMAID = os.path.join(os.path.dirname(os.path.realpath(__file__)), "mermaid.min.js")
if os.path.exists(_MERMAID) and not os.path.exists(os.path.join(OUT, "mermaid.min.js")):
    shutil.copy(_MERMAID, OUT)
esc = lambda s: html.escape(s or "", quote=True)

# tab order preference; any other *_note.md appended alphabetically
PREF = []   # e.g. ["Routing_map_note.md"]; notes not listed follow alphabetically
found = sorted(os.path.basename(p) for p in glob.glob(os.path.join(NOTES_DIR,"*.md")))
NOTE_FILES = [f for f in PREF if f in found] + [f for f in found if f not in PREF]
# Page names already given out live in pages.json beside the quiz bank (pages.py).
PAGES = pages.page_names(found, os.path.dirname(os.path.abspath(__file__)), save=True)

# Note colors on the map: muted, distinct, all readable on the paper background.
PALETTE = ["#2f4fb3","#2d7a4f","#c0612b","#8a4bb0","#1f7f8f","#b13d63","#5a6ec4","#6b7d2e"]
WORD = {"ai":"AI","agi":"AGI","pm":"PM","ux":"UX","rag":"RAG","llm":"LLM","iam":"IAM"}
def label_of(fn):
    base = fn[:-len("_note.md")] if fn.endswith("_note.md") else fn[:-3]
    return " ".join(WORD.get(w.lower(), w.capitalize()) for w in base.replace("_"," ").split())
def slug_of(fn):
    return PAGES[fn]   # one rule with build_quiz.py: see pages.py

# Concepts the knowledge map always looks for. Routing adds more per capture
# (glossary-extra.json), so this can start empty; add terms you care about.
GLOSSARY = []
# Map keywords proposed by unattended routing runs live in data, not code: the
# notes-clipper watcher's merge script appends validated terms to this JSON list,
# so web-derived text never gets written into (or executed as) this script.
_EXTRA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "glossary-extra.json")
if os.path.exists(_EXTRA):
    GLOSSARY += [k for k in json.load(open(_EXTRA, encoding="utf-8")) if isinstance(k, str) and k not in GLOSSARY]

CSS = theme.BASE + """
/* note page: table of contents + one reading column, inside the page width */
.layout{max-width:var(--w-page);margin:0 auto;display:grid;grid-template-columns:208px minmax(0,var(--w-read));
  justify-content:space-between;gap:var(--s-7);padding:var(--s-7) var(--gutter) var(--s-8)}
.toc{font-size:var(--fs-2)}
.toc details{position:sticky;top:80px}
.toc summary{cursor:pointer;margin-bottom:var(--s-3);list-style:none}
.toc summary::-webkit-details-marker{display:none}
.toc ul{list-style:none;margin:0;padding:0;box-shadow:inset 1px 0 0 var(--line)}
.toc li{margin:0}
.toc li a{display:block;padding:5px var(--s-3);color:var(--ink-2);text-decoration:none;border-left:2px solid transparent;
  transition:color .15s var(--ease),border-color .15s var(--ease)}
.toc .l3 a{padding-left:var(--s-5);font-size:var(--fs-1);color:var(--mut)}
@media (hover:hover){.toc li a:hover{color:var(--accent);border-left-color:var(--accent)}}
.expandall{display:block;width:100%;margin:0 0 var(--s-3);padding:var(--s-2) var(--s-3);font:500 var(--fs-1)/1.2 var(--font-ui);
  color:var(--mut);background:var(--surface);border:0;border-radius:var(--r-md);box-shadow:var(--sh-1);cursor:pointer;text-align:left;
  transition:color .15s var(--ease)}
@media (hover:hover){.expandall:hover{color:var(--accent)}}

main{min-width:0;font:var(--fs-4)/1.7 var(--font-read)}
main h1{font-size:var(--fs-7);line-height:1.15;margin:0 0 var(--s-3)}
main h2{font-size:var(--fs-6);line-height:1.25;margin:var(--s-7) 0 var(--s-3);scroll-margin-top:80px}
main h3{font-size:var(--fs-5);line-height:1.3;margin:var(--s-5) 0 var(--s-2);scroll-margin-top:80px}
main p{margin:0 0 var(--s-4)}
main ul,main ol{margin:0 0 var(--s-4);padding-left:1.3em}
main li{margin:var(--s-1) 0}
main li>ul,main li>ol{margin:var(--s-1) 0}
main strong{font-weight:650}
code{font:.86em/1.4 var(--font-mono);background:var(--sunk);border-radius:4px;padding:.12em .35em}
pre{font:var(--fs-2)/1.55 var(--font-mono);background:#22211e;color:#efece5;border-radius:var(--r-md);padding:var(--s-4);overflow:auto;margin:0 0 var(--s-4)}
pre code{background:none;padding:0;color:inherit;font-size:inherit}
blockquote{margin:var(--s-4) 0;padding:var(--s-3) var(--s-4);background:var(--surface);border-radius:var(--r-md);
  box-shadow:inset 3px 0 0 var(--accent),var(--sh-1);color:var(--ink-2)}
blockquote p:last-child{margin-bottom:0}
table{border-collapse:collapse;width:100%;margin:0 0 var(--s-4);font:var(--fs-2)/1.5 var(--font-ui)}
th,td{padding:var(--s-2) var(--s-3);text-align:left;vertical-align:top;box-shadow:inset 0 -1px 0 var(--line)}
th{font-weight:600;color:var(--ink-2)}
hr{border:0;height:1px;background:var(--line);margin:var(--s-6) 0}
.tags{display:flex;flex-wrap:wrap;gap:var(--s-2);margin:0 0 var(--s-5);font-family:var(--font-ui)}
.callout{font:var(--fs-3)/1.5 var(--font-ui);background:var(--warn-soft);color:var(--warn);border-radius:var(--r-md);padding:var(--s-3) var(--s-4);margin:var(--s-4) 0}

/* sources: scan links and inline citation chips */
.src{display:flex;flex-wrap:wrap;gap:var(--s-2);margin:0 0 var(--s-4)}
.src a,a.doc{display:inline-flex;align-items:center;gap:6px;font:500 var(--fs-2)/1 var(--font-ui);color:var(--ink-2);
  text-decoration:none;background:var(--surface);border-radius:var(--r-sm);box-shadow:var(--sh-1);padding:var(--s-2) var(--s-3);
  transition:color .15s var(--ease),box-shadow .15s var(--ease)}
a.doc::before{content:"";width:11px;height:13px;flex:none;background:currentColor;opacity:.7;
  -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 11 13'%3E%3Cpath d='M1.5 0h5l4 4v7.5A1.5 1.5 0 0 1 9 13H1.5A1.5 1.5 0 0 1 0 11.5v-10A1.5 1.5 0 0 1 1.5 0Zm5 1v3.5H10' fill='none' stroke='black' stroke-width='1.2'/%3E%3C/svg%3E") center/contain no-repeat;
  mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 11 13'%3E%3Cpath d='M1.5 0h5l4 4v7.5A1.5 1.5 0 0 1 9 13H1.5A1.5 1.5 0 0 1 0 11.5v-10A1.5 1.5 0 0 1 1.5 0Zm5 1v3.5H10' fill='none' stroke='black' stroke-width='1.2'/%3E%3C/svg%3E") center/contain no-repeat}
@media (hover:hover){.src a:hover,a.doc:hover{color:var(--accent);box-shadow:var(--sh-2)}}
.srcchip{display:inline-block;vertical-align:super;font:500 10px/1.4 var(--font-ui);color:var(--mut);background:var(--sunk);
  border-radius:4px;padding:0 5px;margin:0 1px;text-decoration:none;white-space:nowrap}
@media (hover:hover){.srcchip:hover{color:var(--accent);background:var(--accent-soft)}}
.srcimg{display:block;margin:var(--s-4) 0}
.srcimg img{display:block;max-width:100%;height:auto;border-radius:var(--r-md);background:var(--surface);
  box-shadow:0 0 0 1px var(--line);cursor:zoom-in}

/* diagrams */
.mermaid{background:var(--surface);border-radius:var(--r-lg);box-shadow:var(--sh-1);padding:var(--s-5) var(--s-4);margin:var(--s-5) 0;
  text-align:center;overflow-x:auto;line-height:1.4}
.mermaid svg{max-width:100%;height:auto;cursor:zoom-in}
.mermaid:not([data-processed]){color:var(--mut);font:var(--fs-1)/1.5 var(--font-mono);text-align:left;white-space:pre}

/* collapsible sections */
details.sec{box-shadow:0 -1px 0 var(--line)}
details.sec>summary{list-style:none;cursor:pointer;display:flex;align-items:baseline;gap:var(--s-3);padding:var(--s-3) var(--s-2);
  margin:0 calc(var(--s-2) * -1);border-radius:var(--r-md);transition:background-color .15s var(--ease)}
details.sec>summary::-webkit-details-marker{display:none}
details.sec>summary::before{content:"";flex:none;width:6px;height:6px;margin-bottom:.18em;border:solid var(--mut);
  border-width:0 1.5px 1.5px 0;transform:rotate(-45deg);transition:transform .2s var(--ease)}
details.sec[open]>summary::before{transform:rotate(45deg)}
details.sec>summary>h2,details.sec>summary>h3{margin:0;flex:none}
@media (hover:hover){details.sec>summary:hover{background:var(--hover)}}
.takeaway{color:var(--mut);font:var(--fs-2)/1.4 var(--font-ui);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
details.sec[open] .takeaway{display:none}
.secbody{padding:var(--s-1) 0 var(--s-5) var(--s-5)}
.secbody>*:first-child{margin-top:0}

/* search */
.searchwrap{position:relative;margin-left:var(--s-3)}
.searchbox{width:188px;transition:width .2s var(--ease),box-shadow .15s var(--ease)}
.searchbox:focus{width:260px}
.qres{position:absolute;right:0;top:48px;width:min(440px,92vw);max-height:62vh;overflow:auto;background:var(--surface);
  border-radius:var(--r-lg);box-shadow:var(--sh-3);display:none;z-index:90;padding:var(--s-1)}
.qres.on{display:block}
.qr{display:block;padding:var(--s-3);border-radius:var(--r-md);text-decoration:none;color:inherit}
.qr:hover,.qr.sel{background:var(--hover)}
.qr .qn{font:600 11px/1.2 var(--font-ui);letter-spacing:.06em;text-transform:uppercase;color:var(--mut)}
.qr .qt{font:600 var(--fs-3)/1.35 var(--font-read);margin:var(--s-1) 0;color:var(--ink)}
.qr .qx{font-size:var(--fs-2);color:var(--mut);line-height:1.45}
.qhint,.qempty{padding:var(--s-3);color:var(--mut);font-size:var(--fs-2)}
.qbanner{display:flex;align-items:center;gap:var(--s-3);font:var(--fs-2)/1.4 var(--font-ui);background:var(--warn-soft);color:var(--warn);
  border-radius:var(--r-md);padding:var(--s-2) var(--s-3);margin:0 0 var(--s-5)}
.qbanner a{margin-left:auto;color:var(--accent);text-decoration:none;font-weight:600}

/* image and diagram viewer */
.lb{position:fixed;inset:0;z-index:200;background:rgba(22,21,19,.82);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
  display:none;opacity:0;transition:opacity .18s var(--ease)}
.lb.on{display:block;opacity:1}
.lbstage{position:absolute;inset:0;overflow:auto;display:flex;align-items:center;justify-content:center;padding:64px var(--gutter) var(--gutter)}
.lbstage>*{display:block;background:var(--surface);border-radius:var(--r-md);box-shadow:0 30px 90px rgba(0,0,0,.5);transition:width .18s var(--ease)}
.lb:not(.zoomed) .lbstage>*{max-width:min(1500px,92vw);max-height:84vh;width:auto;height:auto}
.lb.zoomed .lbstage{align-items:flex-start;justify-content:flex-start}
.lb.zoomed .lbstage>*{max-width:none;max-height:none;cursor:grab}
.lb.zoomed .lbstage>*:active{cursor:grabbing}
.lbbar{position:absolute;top:0;left:0;right:0;display:flex;gap:var(--s-3);align-items:center;padding:var(--s-3) var(--s-4);
  color:#efece5;font:var(--fs-2)/1.2 var(--font-ui);background:linear-gradient(rgba(0,0,0,.45),transparent);z-index:2}
.lbbar .cap{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lbbar .zl{font-variant-numeric:tabular-nums;color:#bdb8ae;flex:none}
.lbbar a,.lbbar button{color:#efece5;background:rgba(255,255,255,.12);border:0;border-radius:var(--r-sm);padding:var(--s-2) var(--s-3);
  font:500 var(--fs-1)/1 var(--font-ui);text-decoration:none;cursor:pointer;flex:none}
@media (hover:hover){.lbbar a:hover,.lbbar button:hover{background:rgba(255,255,255,.22)}}
.lbbar .sp{margin-left:auto}

/* index */
.wrap{max-width:var(--w-page);margin:0 auto;padding:var(--s-7) var(--gutter) var(--s-8)}
.wrap>h1{font-size:var(--fs-7);line-height:1.15;margin:0 0 var(--s-2)}
.lede{color:var(--mut);font-size:var(--fs-3);margin:0 0 var(--s-5)}
.actions{display:flex;flex-wrap:wrap;gap:var(--s-3);margin:0 0 var(--s-6)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:var(--s-4)}
.cardlink{display:flex;flex-direction:column;gap:var(--s-2);background:var(--surface);border-radius:var(--r-lg);box-shadow:var(--sh-1);
  padding:var(--s-5);text-decoration:none;color:inherit;transition:box-shadow .2s var(--ease),transform .2s var(--ease)}
.cardlink h3{margin:0;font-size:var(--fs-5);line-height:1.25}
.cardlink p{margin:0;color:var(--ink-2);font-size:var(--fs-2);line-height:1.5}
.cardlink .c{margin-top:auto;padding-top:var(--s-2);font-size:var(--fs-1);color:var(--mut);font-variant-numeric:tabular-nums}
@media (hover:hover){.cardlink:hover{box-shadow:var(--sh-2);transform:translateY(-1px)}}

@media (max-width:860px){.layout{grid-template-columns:minmax(0,1fr);gap:var(--s-4);padding-top:var(--s-5)}.toc details{position:static}}
"""

def fm_split(t):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", t, re.S)
    return (m.group(1), m.group(2)) if m else ("", t)
def fm_get(fm,k):
    m = re.search(rf"^{k}:\s*(.+?)\s*$", fm, re.M)
    return m.group(1).strip().strip('"').strip("'") if m else ""
def fm_tags(fm):
    inl = fm_get(fm,"tags")
    if inl.startswith("["):
        return [x.strip().strip('"').strip("'") for x in inl.strip("[]").split(",") if x.strip()]
    m = re.search(r"^tags:\s*\n((?:[ \t]*-[ \t]*.+\n?)+)", fm, re.M)
    return [re.sub(r"^[ \t]*-[ \t]*","",l).strip() for l in m.group(1).splitlines() if l.strip()] if m else []
def fm_sources(fm):
    inl = fm_get(fm,"sources")
    items = re.findall(r'"([^"]*)"|\'([^\']*)\'|([^,\[\]]+)', inl)
    return [(a or b or c).strip() for a,b,c in items if (a or b or c).strip().lower().endswith(".pdf")]

def pdf_link(name, anchor):
    # The #fragment comes from the note, and this link goes back in after the
    # sanitizer, so it is URL-encoded too (= and & kept: #page=3 still works).
    frag = "#" + urllib.parse.quote(anchor[1:], safe="=&") if anchor else ""
    url = "file://" + urllib.parse.quote(os.path.join(ARCHIVE, name)) + frag
    label = SCAN_LABEL.get(name, name)
    return f'<a class="doc" href="{url}" target="_blank" title="{esc(name)}">{esc(label)}</a>'
def _dedent(block):
    """Strip the common indent a fence picks up when it is nested in a list item."""
    ls = [l for l in block.split("\n") if l.strip()]
    pad = min((len(l) - len(l.lstrip()) for l in ls), default=0)
    return "\n".join(l[pad:] if l.strip() else "" for l in block.split("\n"))

IMG_EXT = "png|jpg|jpeg|gif|webp|avif|svg"
FIGURES = os.path.join(VAULT, "Handwritten/figures")

def _imgdir(name):
    # Image embeds resolve against archive/ (verbatim originals) and figures/
    # (diagram crops taken out of those originals). Markdown note apps resolve wiki-embeds
    # by filename anywhere in the vault; mirror that here instead of assuming one dir.
    for d in (ARCHIVE, FIGURES):
        if os.path.exists(os.path.join(d, name)): return d
    return ARCHIVE

def img_embed(name):
    # Points straight at the vault original, same as pdf_link above. Lazy — these are
    # full-resolution captures far down the page.
    url = "file://" + urllib.parse.quote(os.path.join(_imgdir(name), name))
    return (f'<a class="srcimg" href="{url}" target="_blank" title="open original: {esc(name)}">'
            f'<img src="{url}" alt="{esc(name)}" loading="lazy"></a>')
def srcchip(name):
    url = "file://" + urllib.parse.quote(os.path.join(ARCHIVE, name))
    stem = name[:-4] if name.lower().endswith(".pdf") else name
    label = SCAN_LABEL.get(name, stem)
    return f'<a class="srcchip" href="{url}" target="_blank" title="source: {esc(stem)}">{esc(label)}</a>'

# Notes are written from captured web pages, and pandoc passes raw HTML through
# as is, so its output is filtered: formatting tags only, no event handlers or
# javascript: links. Anything else is shown as text, never run. Runs before the
# script's own trusted fragments (diagrams, source chips) are put back.
from html.parser import HTMLParser
_TAGS = set("p h1 h2 h3 h4 h5 h6 ul ol li a em strong i b u s del ins mark sup sub small kbd code pre "
            "blockquote hr br img span div table thead tbody tfoot tr th td col colgroup caption "
            "dl dt dd figure figcaption details summary input label".split())
_ATTRS = set("href src alt title id class colspan rowspan align style start type checked disabled width height".split())
_URL_OK = re.compile(r"^(?:https?:|mailto:|file:|#|/|\.|[^:/?#]*(?:[/?#]|$))", re.I)
class _Clean(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False); self.out = []
    def _tag(self, tag, attrs, close=""):
        keep = []
        for k, v in attrs:
            v = v or ""
            if k not in _ATTRS or (k in ("href", "src") and not _URL_OK.match(v.strip())):
                continue
            keep.append(f' {k}="{html.escape(v, quote=True)}"')
        return f"<{tag}{''.join(keep)}{close}>"
    def handle_starttag(self, tag, attrs):
        self.out.append(self._tag(tag, attrs) if tag in _TAGS else html.escape(self.get_starttag_text()))
    def handle_startendtag(self, tag, attrs):
        self.out.append(self._tag(tag, attrs, "/") if tag in _TAGS else html.escape(self.get_starttag_text()))
    def handle_endtag(self, tag):
        self.out.append(f"</{tag}>" if tag in _TAGS else html.escape(f"</{tag}>"))
    def handle_data(self, d): self.out.append(d.replace("<", "&lt;").replace(">", "&gt;"))
    def handle_entityref(self, n): self.out.append(f"&{n};")
    def handle_charref(self, n): self.out.append(f"&#{n};")
def _sanitize(h):
    p = _Clean(); p.feed(h); p.close(); return "".join(p.out)

def md_to_html(body, sources=()):
    store = {}
    def put(frag):
        k = f"ZZHWPLH{len(store)}ZZ"; store[k] = frag; return k
    # scan embeds -> scan links (for the bottom Sources list), held as tokens
    # mermaid fences -> <pre class="mermaid"> for client-side rendering (note apps render
    # the same fence natively, so the markdown stays the single source for both surfaces)
    body = re.sub(r"(?m)^[ \t]*```mermaid[ \t]*\n(.*?)\n[ \t]*```[ \t]*$",
                  lambda m: put(f'<pre class="mermaid">{esc(_dedent(m.group(1)))}</pre>'),
                  body, flags=re.S)
    body = re.sub(r"!\[\[([^\]#]+?\.pdf)(#[^\]]*)?\]\]", lambda m: put(pdf_link(m.group(1), m.group(2) or "")), body)
    # image embeds (web captures, photos) -> inline <img> linking to the original
    body = re.sub(r"!\[\[([^\]#]+?\.(?:" + IMG_EXT + r"))\]\]", lambda m: put(img_embed(m.group(1))), body, flags=re.I)
    # inline source attributions -> subtle superscript chips (don't disrupt reading)
    if sources:
        SRC = "(?:" + "|".join(re.escape(s) for s in sorted(set(sources), key=len, reverse=True)) + ")"
        wrap = re.compile(r'\*?\(\s*(?:from\s+)?((?:`?' + SRC + r'`?(?:\s*(?:,|&|and)\s*)?)+)\s*\)\*?')
        body = wrap.sub(lambda m: "".join(put(srcchip(s)) for s in re.findall(SRC, m.group(1))), body)
        body = re.sub(r'`(' + SRC + r')`', lambda m: put(srcchip(m.group(1))), body)
        body = re.sub(SRC, lambda m: put(srcchip(m.group(0))), body)
    body = re.sub(r"\[\[([^\]]+?)\]\]", lambda m: m.group(1), body)  # plain wikilinks -> text
    r = subprocess.run(["pandoc","--from","gfm","--to","html","--wrap=none"], input=body, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr)
    h = _sanitize(r.stdout)
    seen={}
    def fix(m):
        lvl,attrs,inner = m.groups()
        if "id=" in attrs: return m.group(0)
        s = re.sub("<[^>]+>","",inner).lower(); s=re.sub(r"[^a-z0-9\s-]","",s); s=re.sub(r"\s+","-",s).strip("-") or "sec"
        seen[s]=seen.get(s,-1)+1;  s = s if seen[s]==0 else f"{s}-{seen[s]}"
        return f"<h{lvl}{attrs} id=\"{s}\">{inner}</h{lvl}>"
    h = re.sub(r"<h([23])([^>]*)>(.*?)</h\1>", fix, h, flags=re.S)
    for k,v in store.items(): h = h.replace(k, v)   # restore tokens
    # pandoc wraps the placeholder in <p> (sometimes leaving it unclosed) — <pre> can't
    # live inside <p>, so strip the wrapper whether or not the closing tag is there
    h = re.sub(r'<p>\s*(<pre class="mermaid">.*?</pre>)\s*(?:</p>)?', r"\1", h, flags=re.S)
    # group consecutive scan links (bottom Sources section) into a styled row
    h = re.sub(r"(<p>(?:\s*<a class=\"doc\" href=\"file://[^\"]+\.pdf[^>]*>[^<]+</a>\s*)+</p>)",
               lambda m: '<div class="src">'+re.sub(r"</?p>","",m.group(1))+'</div>', h)
    return collapse_sections(h)

def _words(t):
    return {w for w in re.findall(r"[a-z0-9]+", t.lower()) if len(w) > 2}

def _shape(body):
    """Fallback preview: what's inside, when no sentence summarises it well."""
    bits = []
    n = len(re.findall(r"<li[ >]", body))
    if n: bits.append(f"{n} point" + ("s" if n != 1 else ""))
    sc = body.count('class="doc"')                    # scan links
    if sc: bits.append(f"{sc} scan" + ("s" if sc != 1 else ""))
    d = body.count('<pre class="mermaid">')
    if d: bits.append(f"{d} diagram" + ("s" if d != 1 else ""))
    if "<table" in body: bits.append("table")
    if "srcimg" in body: bits.append("image")
    return " \u00b7 ".join(bits)

def _takeaway(body, heading=""):
    """One-line gist for a collapsed section: its opening claim, else a summary of
    what the section holds. Never returns empty when the section has any content."""
    # whichever block opens the section wins — a paragraph buried under the first
    # bullet is not what the section is "about"
    raw, lead = "", ""
    m = re.search(r"<(p|li)\b[^>]*>(.*?)</\1>", body, re.S)
    if m:
        inner = m.group(2)
        raw = re.sub("<[^>]+>", "", inner)          # always keep the whole block…
        if m.group(1) == "li":                      # …but a bullet's bold lead-in is its claim
            st = re.search(r"<strong>(.*?)</strong>", inner, re.S)
            if st: lead = re.sub("<[^>]+>", "", st.group(1))
    clean = lambda t: re.sub(r"\s+", " ", html.unescape(t)).strip().rstrip(" .;:\u2014-")
    raw, lead = clean(raw), clean(lead)
    first = lead or re.split(r"(?<=[.;:])\s", raw)[0].rstrip(" .;:\u2014-")
    # a curt opener ("Retrieval", "Zoom out.") says nothing alone -> keep reading the line
    txt = first if len(first) >= 25 else raw
    def trunc(t): return esc(t[:110] + "\u2026") if len(t) > 110 else esc(t)
    tw, hw = _words(txt), _words(heading)
    restates = bool(tw) and len(tw - hw) / len(tw) < 0.4
    if len(txt) >= 15 and not restates:
        return trunc(txt)
    return esc(_shape(body)) or trunc(txt)      # shape, or the text after all

def collapse_sections(h):
    """Fold every heading that directly owns content behind its title + a one-line
    takeaway. Notes differ: some use ## as Parts with ### sections, others use ##
    as the sections themselves — so fold an h2 only when it has no h3 children,
    and always fold h3. The heading keeps its id, so TOC anchors still land."""
    tags = [(m.start(), m.end(), m.group(1), m.group(0))
            for m in re.finditer(r'<h([23])[^>]*\bid="[^"]+"[^>]*>.*?</h\1>', h, re.S)]
    if not tags: return h
    out, pos = [], 0
    for i, (st, en, lvl, tag) in enumerate(tags):
        out.append(h[pos:st])
        nxt = tags[i+1][0] if i+1 < len(tags) else len(h)
        body = h[en:nxt]
        nxt_lvl = tags[i+1][2] if i + 1 < len(tags) else None
        if lvl == "3" or (lvl == "2" and nxt_lvl != "3"):
            out.append('<details class="sec"><summary>' + tag + '</summary>' +
                       '<div class="secbody">' + body + '</div></details>')
        else:
            out.append(tag + body)
        pos = nxt
    out.append(h[pos:])
    return "".join(out)

def index_entries(body_html, page, label):
    """One search record per foldable section. details.sec blocks never nest, so
    splitting on them yields exactly one chunk per section."""
    out = []
    for chunk in body_html.split('<details class="sec">')[1:]:
        m = re.search(r'<h[23][^>]*\bid="([^"]+)"[^>]*>(.*?)</h[23]>', chunk, re.S)
        if not m: continue
        title = html.unescape(re.sub("<[^>]+>", "", m.group(2))).strip()
        # inline tags vanish (so "<b>faith</b>fulness" indexes as one word);
        # block tags become a space so bullets do not run together
        text = re.sub(r"</?(?:strong|em|b|i|code|mark|a|span|sup|sub|u|small)\b[^>]*>", "", chunk)
        text = html.unescape(re.sub("<[^>]+>", " ", text))
        text = re.sub(r"\s+", " ", text).strip()
        out.append({"p": page, "l": label, "i": m.group(1), "t": title, "x": text})
    return out

def toc_of(h):
    items=[]
    for m in re.finditer(r'<h([23])[^>]*\bid="([^"]+)"[^>]*>(.*?)</h\1>', h, re.S):
        lvl,idv,inner = m.group(1), m.group(2), html.unescape(re.sub("<[^>]+>","",m.group(3))).strip()
        items.append((lvl,idv,inner))
    if not items: return ""
    lis="".join(f'<li class="l{lvl}"><a href="#{esc(idv)}">{esc(txt)}</a></li>' for lvl,idv,txt in items)
    return (f'<div class="toc"><details open><summary class="eyebrow">On this page</summary>'
            f'<button id="toggle-all" class="expandall">Expand all</button>'
            f'<ul>{lis}</ul></details></div>')

# ---- pass 1: read + render each note, collect data ----
notes=[]
for i,fn in enumerate(NOTE_FILES):
    raw = open(os.path.join(NOTES_DIR,fn),encoding="utf-8").read()
    fm,body = fm_split(raw)
    title = fm_get(fm,"title") or label_of(fn)
    tags = fm_tags(fm); gaps = fm_get(fm,"capture_gaps")
    body_html = md_to_html(body, fm_sources(fm))
    # Every note opens with "# <title>" — correct in a markdown app, but the page template
    # already prints the title above, so drop the body's copy to avoid a double H1.
    body_html = re.sub(r'\A\s*<h1[^>]*>.*?</h1>\s*', "", body_html, count=1, flags=re.S)
    _hs = [(m.group(1), html.unescape(re.sub("<[^>]+>", "", m.group(2))).strip())
           for m in re.finditer(r'<h([23])[^>]*>(.*?)</h\1>', body_html, re.S)]
    heads = [t for _, t in _hs]          # every heading — what "what's new" diffs
    # content sections = the headings that actually fold (same rule as collapse_sections)
    secs = [t for i, (lv, t) in enumerate(_hs)
            if lv == "3" or (lv == "2" and (i + 1 >= len(_hs) or _hs[i + 1][0] != "3"))]
    low = body.lower()
    kwtf = {}
    for k in GLOSSARY:
        c = len(re.findall(r"\b"+re.escape(k.lower())+r"\b", low))
        if c: kwtf[k] = c
    kws = list(kwtf)
    nsrc = len(re.findall(r"!\[\[[^\]]+\.pdf", body))
    notes.append(dict(fn=fn, out=slug_of(fn), label=label_of(fn), title=title, tags=tags,
                      gaps=gaps, body=body_html, toc=toc_of(body_html), heads=heads,
                      secs=secs, kws=kws, kwtf=kwtf, nsrc=nsrc, color=PALETTE[i%len(PALETTE)],
                      idx=index_entries(body_html, slug_of(fn), label_of(fn))))

# Not shown as topics: the routing map (a settings note, tagged routing-map),
# and General until something is filed into it.
notes = [n for n in notes if "routing-map" not in n["tags"]
         and not ("general" in n["tags"] and not [s for s in n["secs"] if s != "Sources"])]

# ---- "what's new" diff: compare this build to the previous one, roll a feed ----
# Runs on every build (the PostToolUse hook rebuilds on any note edit), so new
# notes / sections / quiz questions / map concepts are recorded automatically.
REFS = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(REFS, "whatsnew_state.json")   # last build's snapshot
FEED_FILE  = os.path.join(REFS, "whatsnew.json")         # rolling change feed
QUIZ_BANK  = os.path.join(REFS, "quiz-bank.json")

def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh: return json.load(fh)
    except Exception: return default

_quiz_by_note = {}
for _it in _load_json(QUIZ_BANK, []):
    _nb = str(_it.get("note", "")).strip()
    if _nb: _quiz_by_note[_nb] = _quiz_by_note.get(_nb, 0) + 1

_base_to_label = {}
for _n in notes:
    _b = _n["fn"][:-len("_note.md")] if _n["fn"].endswith("_note.md") else _n["fn"][:-3]
    _base_to_label[_b] = _n["label"]

# v2 widened tracking from h2 to h2+h3; v3 un-double-escaped the stored titles.
# Either change would make every section look new, so a version mismatch triggers
# one silent re-baseline instead of a flood.
STATE_V = 3
cur_state = {"v": STATE_V,
             "notes": {n["out"]: {"label": n["label"], "sections": n["heads"]} for n in notes},
             "quiz_by_note": _quiz_by_note,
             "keywords": sorted({k for n in notes for k in n["kws"]})}

prev = _load_json(STATE_FILE, None)
wn_items = []
if prev:  # skip the very first run (no baseline => everything would look "new")
    _sections_comparable = prev.get("v") == STATE_V
    _pn = prev.get("notes", {})
    for slug, meta in cur_state["notes"].items():
        if slug not in _pn:
            wn_items.append("New note: " + meta["label"])
        elif _sections_comparable:
            for s in meta["sections"]:
                if s not in _pn[slug].get("sections", []):
                    wn_items.append(meta["label"] + " — new section: “" + s + "”")
    if not _sections_comparable:
        print("whatsnew: section index upgraded to v%d — re-baselined, sections not diffed this run" % STATE_V)
    _pq = prev.get("quiz_by_note", {})
    for base, cnt in cur_state["quiz_by_note"].items():
        d = cnt - _pq.get(base, 0)
        if d > 0:
            wn_items.append("+%d quiz question%s · %s" % (d, "s" if d > 1 else "", _base_to_label.get(base, base.replace("_", " "))))
    _pk = set(prev.get("keywords", []))
    _newkw = [k for k in cur_state["keywords"] if k not in _pk]
    if _newkw:
        wn_items.append("Map: +%d concept%s (%s%s)" % (len(_newkw), "s" if len(_newkw) > 1 else "", ", ".join(_newkw[:6]), "…" if len(_newkw) > 6 else ""))

# The notes-clipper watcher's per-capture report for the run that led to this
# build: source type, title, and where each capture went or why it didn't.
ROUTES_FILE = os.path.join(REFS, "routing-pending.json")
_routes = [r for r in _load_json(ROUTES_FILE, []) if isinstance(r, dict)]

_feed = _load_json(FEED_FILE, [])
if wn_items or _routes:
    _now = datetime.datetime.now()
    _entry = {"id": _now.strftime("%Y%m%d%H%M%S"), "date": _now.strftime("%Y-%m-%d %H:%M"), "items": wn_items}
    if _routes:
        _entry["routes"] = _routes
    _feed.append(_entry)
    _feed = _feed[-12:]
    with open(FEED_FILE, "w", encoding="utf-8") as fh: json.dump(_feed, fh, ensure_ascii=False, indent=1)
    print("whatsnew:", len(wn_items), "change(s),", len(_routes), "routed capture(s) recorded")
if os.path.exists(ROUTES_FILE):
    os.remove(ROUTES_FILE)
with open(STATE_FILE, "w", encoding="utf-8") as fh: json.dump(cur_state, fh, ensure_ascii=False, indent=1)

def _whatsnew_snippet(feed):
    data = js_json(feed, ensure_ascii=False)
    return ("""<style>
#wn-fab{position:fixed;right:var(--s-5);bottom:var(--s-5);z-index:60;display:none;align-items:center;gap:var(--s-2);min-height:40px;
  padding:0 var(--s-4);border:0;border-radius:999px;background:var(--surface);color:var(--ink);font:600 var(--fs-2)/1 var(--font-ui);
  box-shadow:var(--sh-2);cursor:pointer;transition:box-shadow .15s var(--ease),transform .1s var(--ease)}
#wn-fab:active{transform:scale(.97)}
@media (hover:hover){#wn-fab:hover{box-shadow:var(--sh-3)}}
#wn-fab .dot{width:7px;height:7px;border-radius:50%;background:var(--accent)}
#wn-ov{position:fixed;inset:0;z-index:70;background:rgba(22,21,19,.42);display:none;align-items:center;justify-content:center;padding:var(--gutter)}
#wn-modal{background:var(--surface);border-radius:var(--r-lg);box-shadow:var(--sh-3);max-width:520px;width:100%;max-height:82vh;overflow:auto;padding:var(--s-5)}
#wn-modal h2{margin:0 0 var(--s-1);font-size:var(--fs-5)}
#wn-modal .sub{color:var(--mut);font-size:var(--fs-2);line-height:1.5;margin:0 0 var(--s-3)}
#wn-modal .rec{padding:var(--s-3) 0;box-shadow:0 -1px 0 var(--line)}
#wn-modal .rd{margin-bottom:var(--s-2);font:600 11px/1.2 var(--font-ui);letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}
#wn-modal ul{margin:0;padding:0;list-style:none}
#wn-modal li{margin:var(--s-2) 0;font-size:var(--fs-3);line-height:1.5}
#wn-modal li a{color:inherit}
#wn-modal .dest{color:var(--mut)}
#wn-modal .row{display:flex;gap:var(--s-2);justify-content:flex-end;margin-top:var(--s-5)}
.wn-tag{display:inline-block;min-width:4.6em;margin-right:var(--s-2);font:600 10px/1.6 var(--font-ui);letter-spacing:.06em;
  text-align:center;border-radius:4px;padding:0 6px;vertical-align:1px}
.wn-cap{background:var(--sunk);color:var(--ink-2)}.wn-fail{background:var(--bad-soft);color:var(--bad)}
.wn-note{background:var(--accent-soft);color:var(--accent)}.wn-section{background:var(--warn-soft);color:var(--warn)}
.wn-quiz{background:var(--ok-soft);color:var(--ok)}.wn-map{background:var(--sunk);color:var(--ink-2)}
</style>
<button id="wn-fab"><span class="dot"></span>What’s new</button>
<div id="wn-ov"><div id="wn-modal">
<h2>What’s new</h2>
<div class="sub">What each capture was and where it went, then new notes, sections, quiz questions &amp; map concepts.</div>
<div id="wn-body"></div>
<div class="row"><button class="btn quiet" id="wn-dismiss">Close</button><button class="btn" id="wn-ok">Got it</button></div>
</div></div>
<script>
(function(){
var FEED=__DATA__;
if(!FEED.length)return;
var KEY='hw_whatsnew_seen';
var latest=FEED[FEED.length-1].id;
var seen='';try{seen=localStorage.getItem(KEY)||'';}catch(e){}
var unseen=FEED.filter(function(r){return r.id>seen;});
var fab=document.getElementById('wn-fab'),ov=document.getElementById('wn-ov'),body=document.getElementById('wn-body'),dot=fab.querySelector('.dot');
function tag(it){var c='wn-note',l='NOTE';if(/new section/i.test(it)){c='wn-section';l='SECTION';}else if(/quiz question/i.test(it)){c='wn-quiz';l='QUIZ';}else if(/^Map:/.test(it)){c='wn-map';l='MAP';}return '<span class="wn-tag '+c+'">'+l+'</span>';}
// Titles and headings can come from web pages, so everything is escaped.
function esc(s){return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
var KIND={web:'WEB',scan:'SCAN',screenshot:'SCREENSHOT',note:'LINK'};
function route(c){var ok=c.state==='done';var t=ok?(KIND[c.type]||'CAPTURE'):'NOT ROUTED';
  var title=String(c.link||'').indexOf('file://')===0?'<a href="'+esc(c.link)+'">'+esc(c.title)+'</a>':esc(c.title);
  var dest=ok?' → '+esc((c.notes||[]).join(', ').replace(/_/g,' ')):' — '+esc(c.why);
  // The faithfulness check (watcher/faithfulness.py) and the model that ran.
  var f=c.faith; if(ok&&f&&typeof f.score==='number'){dest+=' · faithfulness '+esc(f.score)+'/5';
    if((f.unsupported||[]).length)dest+=' · not in the source: '+f.unsupported.map(function(x){return '\u201c'+esc(x)+'\u201d';}).join('; ');}
  if(c.model)dest+=' · '+esc(c.model);
  return '<li><span class="wn-tag '+(ok?'wn-cap':'wn-fail')+'">'+t+'</span>'+title+'<span class="dest">'+dest+'</span></li>';}
function render(list){body.innerHTML=list.map(function(r){return '<div class="rec"><div class="rd">'+esc(r.date)+'</div><ul>'+(r.routes||[]).map(route).join('')+r.items.map(function(it){return '<li>'+tag(it)+esc(it)+'</li>';}).join('')+'</ul></div>';}).join('');}
function show(list){render(list.slice().reverse());ov.style.display='flex';}
function hide(){ov.style.display='none';}
fab.style.display='inline-flex';
document.getElementById('wn-ok').onclick=function(){try{localStorage.setItem(KEY,latest);}catch(e){}dot.style.display='none';hide();};
document.getElementById('wn-dismiss').onclick=hide;
ov.addEventListener('click',function(e){if(e.target===ov)hide();});
fab.onclick=function(){show(FEED);};
if(unseen.length){show(unseen);}else{dot.style.display='none';}
})();
</script>""").replace("__DATA__", data)

WN_SNIPPET = _whatsnew_snippet(_feed)

MERMAID_SNIPPET = ("""<script src="mermaid.min.js"></script>"""
  """<script>mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'base',"""
  """themeVariables:{fontFamily:'-apple-system,BlinkMacSystemFont,SF Pro Text,sans-serif',fontSize:'14px',"""
  """primaryColor:'#f3f0e9',primaryBorderColor:'#2f4fb3',primaryTextColor:'#1d1c1a',"""
  """lineColor:'#716d66',secondaryColor:'#efece5',tertiaryColor:'#fffdf9'},"""
  """flowchart:{useMaxWidth:true,htmlLabels:true,padding:10}});</script>""")

# Sections render collapsed, but mermaid measures 0x0 inside a closed <details> —
# so open everything, let mermaid finish, then collapse. Also keeps TOC anchors
# working by opening whichever section a #hash points into.
SECTION_JS = """<script>
(function(){
  var all=false, btn=document.getElementById('toggle-all');
  function ds(){ return [].slice.call(document.querySelectorAll('details.sec')); }
  function setAll(v){ ds().forEach(function(d){ d.open=v; }); all=v;
    if(btn) btn.textContent = v ? 'Collapse all' : 'Expand all'; }
  if(btn) btn.addEventListener('click', function(){ setAll(!all); });
  function openHash(){
    var id=decodeURIComponent(location.hash.slice(1)); if(!id) return;
    var el=document.getElementById(id); if(!el) return;
    var d=el.closest('details.sec'); if(d) d.open=true;
    el.scrollIntoView({block:'start'});
  }
  window.addEventListener('hashchange', openHash);
  document.querySelectorAll('.toc a[href^="#"]').forEach(function(a){
    a.addEventListener('click', function(){ setTimeout(openHash, 0); });
  });
  function start(){
    var list=ds(), done=function(){ list.forEach(function(d){ d.open=false; }); openHash(); };
    if(window.mermaid){ list.forEach(function(d){ d.open=true; });
      Promise.resolve(mermaid.run()).then(done).catch(done); }
    else { done(); }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
</script>"""

SEARCH_BOX = ('<div class="searchwrap">'
  '<input id="q" class="field searchbox" type="search" placeholder="Search all notes\u2026  /" autocomplete="off" spellcheck="false">'
  '<div id="qres" class="qres"></div></div>')

# Loaded on every page; the index itself is one shared file so it is fetched once.
SEARCH_JS = """<script src="handwritten-search-index.js"></script>
<script>
(function(){
  var IDX = window.SEARCH_INDEX || [];
  var box = document.getElementById('q'), res = document.getElementById('qres');
  var sel = -1, hits = [];
  function esc(s){ return s.replace(/[&<>"]/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
  function rx(q){ return new RegExp(q.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&'),'gi'); }
  function hl(t,q){ return esc(t).replace(rx(esc(q)), function(m){ return '<mark>'+m+'</mark>'; }); }
  function snip(text,q){
    var i = text.toLowerCase().indexOf(q.toLowerCase());
    if(i<0) return text.slice(0,150);
    var a = Math.max(0, i-60), b = Math.min(text.length, i+q.length+110);
    return (a>0?'\u2026':'') + text.slice(a,b) + (b<text.length?'\u2026':'');
  }
  function render(q){
    if(!hits.length){ res.innerHTML='<div class="qempty">No matches for \u201c'+esc(q)+'\u201d</div>'; res.classList.add('on'); return; }
    var h = hits.map(function(e,n){
      return '<a class="qr'+(n===sel?' sel':'')+'" href="'+esc(e.p)+'?q='+encodeURIComponent(q)+'#'+esc(e.i)+'">'
           + '<div class="qn">'+esc(e.l)+'</div>'
           + '<div class="qt">'+hl(e.t,q)+'</div>'
           + '<div class="qx">'+hl(snip(e.x,q),q)+'</div></a>'; }).join('');
    res.innerHTML = h + '<div class="qhint">'+hits.length+' section'+(hits.length>1?'s':'')+' \u00b7 \u2191\u2193 to move, \u21b5 to open</div>';
    res.classList.add('on');
  }
  function run(){
    var q = box.value.trim();
    sel = -1;
    if(q.length < 2){ res.classList.remove('on'); res.innerHTML=''; hits=[]; return; }
    var ql = q.toLowerCase();
    hits = IDX.map(function(e){
      var it = e.t.toLowerCase().indexOf(ql), ix = e.x.toLowerCase().indexOf(ql);
      if(it<0 && ix<0) return null;
      return {e:e, s: it>=0 ? 0 : 1};
    }).filter(Boolean).sort(function(a,b){ return a.s-b.s; }).slice(0,40).map(function(o){ return o.e; });
    render(q);
  }
  if(box){
    var t; box.addEventListener('input', function(){ clearTimeout(t); t=setTimeout(run,110); });
    box.addEventListener('keydown', function(ev){
      var links = res.querySelectorAll('.qr');
      if(ev.key==='Escape'){ box.value=''; res.classList.remove('on'); box.blur(); return; }
      if(!links.length) return;
      if(ev.key==='ArrowDown'||ev.key==='ArrowUp'){
        ev.preventDefault();
        sel = ev.key==='ArrowDown' ? Math.min(sel+1, links.length-1) : Math.max(sel-1, 0);
        links.forEach(function(a,i){ a.classList.toggle('sel', i===sel); });
        links[sel].scrollIntoView({block:'nearest'});
      } else if(ev.key==='Enter'){
        ev.preventDefault(); (links[sel<0?0:sel]).click();
      }
    });
    document.addEventListener('keydown', function(ev){
      if(ev.key==='/' && document.activeElement!==box && !/^(INPUT|TEXTAREA)$/.test(document.activeElement.tagName)){
        ev.preventDefault(); box.focus();
      }
    });
    document.addEventListener('click', function(ev){
      if(!ev.target.closest('.searchwrap')) res.classList.remove('on');
    });
  }

  // Arriving from a result: open every section that matches, highlight, jump.
  function markPage(q){
    if(!q) return;
    var re = rx(q.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\\\$&')), n = 0;
    document.querySelectorAll('details.sec').forEach(function(d){
      if(d.textContent.toLowerCase().indexOf(q.toLowerCase())>=0) d.open = true;
    });
    var main = document.querySelector('main') || document.body;
    var walk = document.createTreeWalker(main, NodeFilter.SHOW_TEXT, {
      acceptNode: function(node){
        if(!node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        var p = node.parentElement;
        while(p && p!==main){
          var t = p.tagName;
          if(t==='SCRIPT'||t==='STYLE'||t==='MARK'||t==='svg'||p.closest('svg')) return NodeFilter.FILTER_REJECT;
          p = p.parentElement;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var targets = []; while(walk.nextNode()) targets.push(walk.currentNode);
    targets.forEach(function(node){
      if(!re.test(node.nodeValue)) return;
      re.lastIndex = 0;
      var span = document.createElement('span');
      span.innerHTML = esc(node.nodeValue).replace(re, function(m){ n++; return '<mark>'+m+'</mark>'; });
      node.parentNode.replaceChild(span, node);
    });
    var b = document.createElement('div');
    b.className = 'qbanner';
    b.innerHTML = '<span>'+n+' match'+(n===1?'':'es')+' for \u201c'+esc(q)+'\u201d on this page</span><a href="#" id="qclear">clear</a>';
    main.insertBefore(b, main.firstChild);
    b.querySelector('#qclear').addEventListener('click', function(ev){
      ev.preventDefault(); location.href = location.pathname + location.hash; });
    if(location.hash){
      var el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
      if(el) el.scrollIntoView({block:'start'});
    }
  }
  var q = new URLSearchParams(location.search).get('q');
  if(q){
    if(box) box.value = q;
    if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', function(){ setTimeout(function(){ markPage(q); }, 60); });
    else setTimeout(function(){ markPage(q); }, 60);
  }
})();
</script>"""

# Click an embedded scan or a diagram to open it full-screen; click again (or
# scroll) to zoom past fit-to-window, drag to pan. Diagrams are cloned as SVG so
# they stay vector-sharp at any zoom.
LIGHTBOX_JS = """<script>
(function(){
  var lb,stage,cap,zl,orig,base=0,scale=1,zoomed=false;
  function build(){
    lb=document.createElement('div');lb.className='lb';
    lb.innerHTML='<div class="lbbar"><span class="cap"></span><span class="sp"></span>'
      +'<span class="zl"></span><a class="og" target="_blank">open original</a>'
      +'<button class="cl">Close &times;</button></div><div class="lbstage"></div>';
    document.body.appendChild(lb);
    stage=lb.querySelector('.lbstage');cap=lb.querySelector('.cap');
    zl=lb.querySelector('.zl');orig=lb.querySelector('.og');
    lb.querySelector('.cl').onclick=close;
    lb.addEventListener('click',function(e){ if(e.target===lb||e.target===stage) close(); });
    stage.addEventListener('wheel',function(e){
      if(!lb.classList.contains('on')) return;
      e.preventDefault(); setScale(scale*Math.exp(-e.deltaY*0.0016));
    },{passive:false});
    var down=false,sx,sy,sl,st;
    stage.addEventListener('mousedown',function(e){
      if(!zoomed) return; down=true;sx=e.clientX;sy=e.clientY;sl=stage.scrollLeft;st=stage.scrollTop;e.preventDefault();});
    addEventListener('mousemove',function(e){
      if(!down) return; stage.scrollLeft=sl-(e.clientX-sx); stage.scrollTop=st-(e.clientY-sy);});
    addEventListener('mouseup',function(){down=false;});
    addEventListener('keydown',function(e){
      if(!lb.classList.contains('on')) return;
      if(e.key==='Escape') close();
      else if(e.key==='+'||e.key==='=') setScale(scale*1.25);
      else if(e.key==='-'||e.key==='_') setScale(scale/1.25);
      else if(e.key==='0') fit();
    });
  }
  function el(){ return stage.firstElementChild; }
  function fit(){ zoomed=false;lb.classList.remove('zoomed');
    var n=el(); if(n) n.style.width=''; scale=1; label(); }
  function setScale(v){
    var n=el(); if(!n||!base) return;
    scale=Math.min(8,Math.max(1,v));
    if(scale<=1.001){ fit(); return; }
    zoomed=true;lb.classList.add('zoomed');
    n.style.width=Math.round(base*scale)+'px';
    label();
  }
  function label(){ zl.textContent=(zoomed?Math.round(scale*100):100)+'%'; }
  function open(node,caption,href){
    if(!lb) build();
    stage.innerHTML='';
    var n=node.cloneNode(true);
    n.removeAttribute('style');n.removeAttribute('class');
    n.addEventListener('click',function(e){ e.stopPropagation(); zoomed?fit():setScale(2); });
    stage.appendChild(n);
    cap.textContent=caption||'';
    if(href){orig.href=href;orig.style.display='';}else{orig.style.display='none';}
    lb.classList.add('on');document.body.style.overflow='hidden';
    // natural width is the 100% reference; SVGs report it via the bounding box
    requestAnimationFrame(function(){
      base=n.naturalWidth||n.getBoundingClientRect().width||600; fit();
    });
  }
  function close(){ if(!lb) return; lb.classList.remove('on');document.body.style.overflow='';
    setTimeout(function(){ if(!lb.classList.contains('on')) stage.innerHTML=''; },200); }
  document.addEventListener('click',function(e){
    var a=e.target.closest('a.srcimg');
    if(a){ e.preventDefault(); var i=a.querySelector('img');
      open(i,i.getAttribute('alt')||'',a.getAttribute('href')); return; }
    var sv=e.target.closest('.mermaid svg');
    if(sv){ var sec=e.target.closest('details.sec'),
            t=sec?(sec.querySelector('h2,h3')||{}).textContent:'';
      open(sv,(t||'Diagram').trim(),null); }
  });
})();
</script>"""


def tabbar(cur):
    tabs = "".join(f'<a class="tab{" active" if n["out"]==cur else ""}" href="{esc(n["out"])}"'
                   f'{" aria-current=\"page\"" if n["out"]==cur else ""}>{esc(n["label"])}</a>'
                   for n in notes)
    right = (f'<a class="tab{" active" if cur==MAP else ""}" href="{MAP}">Map</a>'
             f'<a class="tab" href="{QUIZ}">Quiz</a>' + SEARCH_BOX)
    return theme.header(INDEX, tabs, right)

# ---- shared search index (one file, loaded by every page) ----
SEARCH_INDEX = [e for n in notes for e in n["idx"]]
with open(os.path.join(OUT, "handwritten-search-index.js"), "w", encoding="utf-8") as fh:
    fh.write("window.SEARCH_INDEX=" + js_json(SEARCH_INDEX, ensure_ascii=False, separators=(",", ":")) + ";")
print("search index:", len(SEARCH_INDEX), "sections across", len(notes), "notes")

# ---- write per-note pages ----
for n in notes:
    tagshtml = '<div class="tags">'+''.join(f'<span class="tag">{esc(t)}</span>' for t in n["tags"])+'</div>' if n["tags"] else ""
    gapshtml = ""   # capture_gaps stays in frontmatter as the record, not rendered
    mermaidjs = MERMAID_SNIPPET if 'class="mermaid"' in n["body"] else ""
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(n['title'])}</title>{theme.FAVICON}<style>{CSS}</style></head><body>
{tabbar(n['out'])}
<div class="layout">{n['toc']}<main><h1>{esc(n['title'])}</h1>{tagshtml}{gapshtml}{n['body']}</main></div>{WN_SNIPPET}{mermaidjs}{SECTION_JS}{SEARCH_JS}{LIGHTBOX_JS}</body></html>"""
    open(os.path.join(OUT,n["out"]),"w",encoding="utf-8").write(doc)
    print("wrote", n["out"], f"({n['nsrc']} sources, {len(n['kws'])} keywords)")

# ---- index hub ----
cards="".join(
 f'<a class="cardlink" href="{esc(n["out"])}"><h3>{esc(n["title"])}</h3><p>{esc(" · ".join(n["secs"][:6]))}</p>'
 f'<div class="c">{len(n["secs"])} sections' + (f' · {n["nsrc"]} scans' if n["nsrc"] else '') + '</div></a>' for n in notes)
idx = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{theme.NAME}</title>{theme.FAVICON}<style>{CSS}</style></head><body>
{theme.header(INDEX, "", f'<a class="tab" href="{MAP}">Map</a><a class="tab" href="{QUIZ}">Quiz</a>' + SEARCH_BOX)}
<div class="wrap"><h1>{theme.NAME}</h1>
<p class="lede">{len(notes)} topic notes · each cites the saved original it came from.</p>
<div class="actions"><a class="btn" href="{QUIZ}">Quiz yourself</a><a class="btn quiet" href="{MAP}">Open the knowledge map</a></div>
<div class="grid">{cards}</div></div>{WN_SNIPPET}{SEARCH_JS}</body></html>"""
open(os.path.join(OUT,INDEX),"w",encoding="utf-8").write(idx)
print("wrote", INDEX)

# ---- help: how to install and use, linked from the ? in every page's header ----
HELP_SECTIONS = [
 ("install", "Install the browser extension", """
<p>The extension is the side panel you clip pages with. It saves each capture into
<code>~/Downloads/notes-inbox/</code>, where the watcher picks it up and files it.</p>
<ol>
<li>Open <code>chrome://extensions</code> in Chrome and switch on <b>Developer mode</b> (top right).</li>
<li>Click <b>Load unpacked</b> and choose the <code>extension</code> folder inside your Notes-Clipper download.</li>
<li>Pin <b>Notes Clipper</b> to the toolbar. Clicking it opens the side panel.</li>
<li>In <code>chrome://settings/downloads</code>, keep the location as your Downloads folder and leave
<b>Ask where to save each file</b> off.</li>
</ol>
<p>To clip: select text on a page and click <b>Add selection from page</b> (or right-click it), add images with
<b>Add image</b> or <kbd>⌘</kbd><kbd>V</kbd>, or use <b>Add whole page</b> for long articles and videos. Then click
<b>Save to notes</b>. Within a few minutes the capture is filed and these pages are rebuilt.</p>
<p>The watcher that does the filing is installed once from Terminal; the README's Setup walks through it.</p>
"""),
 ("scans", "Scan handwritten pages", """
<p>Paper notes come in the same way: the AI transcribes each page word for word, and nothing is filed until
you've checked the transcript.</p>
<ol>
<li>Scan the page with your phone (Files or Notes → <b>Scan Documents</b>). PDF, JPEG, PNG and HEIC all work.</li>
<li>Put the file in <code>Handwritten/inbox/</code> inside your notes folder, by iCloud Drive, AirDrop or any
other way. It's picked up within about 15 minutes.</li>
<li>A review page opens with the scan beside its transcript. Words the AI wasn't sure of are listed above
the text, marked <code>word[?]</code>, or <code>[illegible?]</code> where it couldn't read them; <b>Find</b>
jumps to each one. Fix anything in the box.</li>
<li>Click <b>Download corrections</b>. That download is your approval: the next run files the page into your
topic notes and keeps the original scan alongside the transcript.</li>
</ol>
<p>Crossed-out text is never read as part of the note. With Codex as the agent, only the first page of a
multi-page PDF is read, so scan pages separately or use Claude.</p>
"""),
 ("model", "Choose or change the AI model", """
<p>One AI agent does the filing, scan transcription and the faithfulness check. It runs on your own plan
(Claude Pro or Max, or ChatGPT), not on API credits.</p>
<p>Choose the agent and pin a model by running the installer again with the setting you want. It remembers
it from then on:</p>
<pre><code>CLAUDE_MODEL=claude-opus-5-5 bash &lt;repo&gt;/watcher/install.sh</code></pre>
<pre><code>NOTES_AGENT=codex CODEX_MODEL=&lt;model&gt; bash &lt;repo&gt;/watcher/install.sh</code></pre>
<p>The first keeps Claude Code and pins Opus 5.5; the second switches to OpenAI's Codex CLI (sign in once with
<code>codex login</code>). Leave the model out to use the agent's own default. Every setting lives in
<code>~/.config/notes-clipper/watcher.env</code>, and What's new shows which model filed each capture.</p>
<p>Before switching for good, compare on the same captures, without changing your setup:</p>
<pre><code>EVAL_MODEL=claude-sonnet-5-5 bash &lt;repo&gt;/evals/run.sh</code></pre>
<p>Claude can only read and write your notes folder; Codex can also read other files on your Mac, though it
can't send them anywhere. The README compares the two.</p>
"""),
 ("map", "How the knowledge map is made", """
<p>You don't build the map by hand: it is redrawn after every filing run, from your topic notes. Open it with
<b>Map</b> in the header.</p>
<ul>
<li><b>Notes</b> are the colored circles. Click one to open it.</li>
<li><b>Concepts</b> are the terms the map tracks. When a capture is filed, the AI proposes up to five specific
terms from it. A term is added only if it appears in your notes, isn't on the map yet, and isn't in most
notes at once (a word everywhere connects everything, so it shows nothing).</li>
<li><b>Size and lines</b> show weight: a term repeated in one note pulls harder than one mentioned everywhere.
Click the <i>i</i> on the map for the full key, and any concept for the notes it appears in.</li>
</ul>
<p>To add terms of your own, list them in <code>glossary-extra.json</code> (a JSON list of words) in your
build folder, <code>~/.config/notes-clipper/renderer</code> unless you changed <code>NOTES_REFS</code>. They appear
after the next filing run.</p>
"""),
 ("quiz", "How the quiz is made", """
<p>The quiz also builds itself. Each filed capture can add two to four multiple-choice questions on what it
added to your notes, each one answerable from the note and citing its source. A check drops any that are
malformed or point at a note that doesn't exist.</p>
<ol>
<li>Open <b>Quiz</b> in the header.</li>
<li>Pick a topic and a difficulty (recall, apply, analyze), then <b>Start a round</b>: ten questions at a time.</li>
<li>Answer with the mouse or <kbd>1</kbd>–<kbd>4</kbd>. Each answer shows the right option and where it came from.</li>
<li><b>Save for review</b> keeps a question for later; <b>Review saved</b> quizzes you on just those.</li>
</ol>
<p>The questions live in <code>quiz-bank.json</code> in the same build folder. You can edit or delete any of
them there; the quiz page is rebuilt after the next filing run.</p>
"""),
]
HELP_TOC = ('<div class="toc"><details open><summary class="eyebrow">On this page</summary><ul>'
            + "".join(f'<li class="l2"><a href="#{i}">{esc(t)}</a></li>' for i, t, _ in HELP_SECTIONS) + '</ul></details></div>')
HELP_BODY = "".join(f'<h2 id="{i}">{esc(t)}</h2>{body}' for i, t, body in HELP_SECTIONS)
helpdoc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>How to use {theme.NAME}</title>{theme.FAVICON}<style>{CSS}</style></head><body>
{theme.header(INDEX, "", f'<a class="tab" href="{MAP}">Map</a><a class="tab" href="{QUIZ}">Quiz</a>' + SEARCH_BOX).replace('class="helpbtn"', 'class="helpbtn" aria-current="page"')}
<div class="layout">{HELP_TOC}<main><h1>How to use {theme.NAME}</h1>
<p class="lede">Clip what's worth keeping; an AI files it into these topic notes, keeps every original, and builds the map and quiz from them.</p>
{HELP_BODY}</main></div>{SEARCH_JS}</body></html>"""
open(os.path.join(OUT, theme.HELP), "w", encoding="utf-8").write(helpdoc)
print("wrote", theme.HELP)

# ---- knowledge map ----
# ---- keyword graph -------------------------------------------------------
# Edges carry tf-idf, not mere presence: a note that says "agent" 74 times is
# pulled far harder than one that mentions it in passing. idf demotes words that
# appear in every note (trust, roadmap) — they connect everything, so they
# distinguish nothing. Concept size = total importance, not how many notes list it.
_tf = {k: {n["out"]: n["kwtf"][k] for n in notes if k in n["kwtf"]} for k in
       {k for n in notes for k in n["kwtf"]}}
_df = {k: len(v) for k, v in _tf.items()}
_NN = len(notes) or 1
_idf = {k: math.log(1 + _NN/_df[k]) for k in _tf}
_w = {k: {u: _tf[k][u]*_idf[k] for u in _tf[k]} for k in _tf}
_wmax = max((v for d in _w.values() for v in d.values()), default=1) or 1
_imp = {k: sum(_w[k].values()) for k in _w}
_imax = max(_imp.values(), default=1) or 1

gnodes=[{"id":"note:"+n["out"],"label":n["label"],"type":"note","url":n["out"],
         "color":n["color"],"r":17} for n in notes]
for k in _tf:
    rel = _imp[k]/_imax
    gnodes.append({"id":"kw:"+k,"label":k,"type":"kw","deg":_df[k],"df":_df[k],
                   "imp":round(rel,4),"r":round(4+16*math.sqrt(rel),2)})
glinks=[{"s":"note:"+u,"t":"kw:"+k,"w":round(_w[k][u]/_wmax,4)} for k in _w for u in _w[k]]

# concept<->concept: cosine over the tf-idf note-vectors. Concepts living in a
# single note have a degenerate 1-D vector (every such pair scores 1.0 and forms
# a fake clique), so they are excluded from this projection — they still appear
# as leaves hanging off their note.
_norm = {k: math.sqrt(sum(v*v for v in _w[k].values())) or 1e-9 for k in _w}
def _cos(a, b):
    sh = set(_w[a]) & set(_w[b])
    return sum(_w[a][u]*_w[b][u] for u in sh)/(_norm[a]*_norm[b]) if sh else 0.0
KK_MINSIM, KK_TOPK = 0.55, 3
_elig = [k for k in _w if _df[k] >= 2]
_pairs = {}
for a in _elig:
    for sc, b in sorted(((_cos(a,b), b) for b in _elig if b != a and set(_w[a]) & set(_w[b])),
                        reverse=True)[:KK_TOPK]:
        if sc >= KK_MINSIM: _pairs[tuple(sorted((a,b)))] = round(sc,4)
for (a,b),sc in _pairs.items():
    glinks.append({"s":"kw:"+a,"t":"kw:"+b,"w":sc,"kk":1})

GRAPH=js_json({"nodes":gnodes,"links":glinks})

MAPJS = r"""
const idx={}; GRAPH.nodes.forEach((n,i)=>idx[n.id]=i);
const cv=document.getElementById('cv'), cx=cv.getContext('2d'); let W=0,H=0,DPR=1;
function resize(){DPR=devicePixelRatio||1;W=cv.clientWidth;H=cv.clientHeight;cv.width=W*DPR;cv.height=H*DPR;cx.setTransform(DPR,0,0,DPR,0,0);}
addEventListener('resize',resize); resize();
const N=GRAPH.nodes.map(n=>({...n, x:W/2+(Math.random()*2-1)*Math.min(W,H)*0.38, y:H/2+(Math.random()*2-1)*Math.min(W,H)*0.38, vx:0,vy:0, a:1, r:n.r||(n.type==='note'?17:8)}));
const L=GRAPH.links.map(l=>({s:idx[l.s],t:idx[l.t], w:l.w||1, kk:l.kk||0, a:0}));
const adj=N.map(()=>new Set()); L.forEach(l=>{adj[l.s].add(l.t);adj[l.t].add(l.s);});
let hover=-1, sel=-1, drag=-1, moved=false, q='';
let alpha=1; const ALPHA_MIN=0.005, ALPHA_DECAY=0.98; function reheat(a){alpha=Math.max(alpha,a);}
let panX=0,panY=0,panning=false,px0=0,py0=0,panX0=0,panY0=0;
let spread=1; const SPREAD_MIN=0.4, SPREAD_MAX=4;
function zoomBy(f){spread=Math.min(SPREAD_MAX,Math.max(SPREAD_MIN,spread*f));reheat(0.6);}
function resetView(){spread=1;panX=0;panY=0;reheat(0.6);}
const VMAX=9;  // px/frame ceiling — stops nodes flinging when the sim reheats
function step(){if(alpha<ALPHA_MIN)return;const kRep=2600*spread*spread,kSp=0.022,rest=72*spread,kG=0.016/spread,damp=0.82;
 for(let i=0;i<N.length;i++)for(let j=i+1;j<N.length;j++){let dx=N[i].x-N[j].x,dy=N[i].y-N[j].y,d2=dx*dx+dy*dy+.01,d=Math.sqrt(d2),
   kk=(N[i].type==='note'&&N[j].type==='note')?kRep*14:kRep,f=kk/d2,fx=f*dx/d,fy=f*dy/d;N[i].vx+=fx;N[i].vy+=fy;N[j].vx-=fx;N[j].vy-=fy;}
 for(const l of L){let a=N[l.s],b=N[l.t],dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)+.01,
   st=(0.006+0.055*l.w)*spread,rl=(150-95*l.w)*spread,f=st*(d-rl),fx=f*dx/d,fy=f*dy/d;a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;}
 for(let i=0;i<N.length;i++){let n=N[i];n.vx+=(W/2-n.x)*kG;n.vy+=(H/2-n.y)*kG;if(i===drag)continue;n.vx*=damp;n.vy*=damp;let dx=n.vx*alpha,dy=n.vy*alpha,m=Math.hypot(dx,dy);if(m>VMAX){dx=dx/m*VMAX;dy=dy/m*VMAX;}n.x+=dx;n.y+=dy;n.x=Math.max(n.r,Math.min(W-n.r,n.x));n.y=Math.max(n.r,Math.min(H-n.r,n.y));}
 alpha*=ALPHA_DECAY;}
function draw(){cx.setTransform(DPR,0,0,DPR,0,0);cx.clearRect(0,0,W,H);cx.translate(panX,panY);const a=hover>=0?hover:sel;
 for(const l of L){const A=N[l.s],B=N[l.t],inc=a>=0&&(l.s===a||l.t===a);l.a+=((inc?1:0)-l.a)*0.16;
  const base=a<0?(0.05+0.30*l.w):0.05, op=base+(0.55-base)*l.a;
  cx.beginPath();cx.moveTo(A.x,A.y);cx.lineTo(B.x,B.y);
  cx.strokeStyle=l.kk?'rgba(16,185,129,'+(op*0.9).toFixed(3)+')':((l.a>0.02?'rgba(47,79,179,':'rgba(150,143,130,')+op.toFixed(3)+')');
  cx.lineWidth=0.4+2.4*l.w+0.7*l.a;cx.stroke();}
 const anyMatch=q&&N.some(n=>n.label.toLowerCase().includes(q));
 N.forEach((n,i)=>{const match=q&&n.label.toLowerCase().includes(q);
  const dim=(a>=0&&i!==a&&!adj[a].has(i))||(anyMatch&&!match);
  n.a+=((dim?0.14:1)-n.a)*0.16;
  cx.globalAlpha=n.a;
  if(match){cx.beginPath();cx.arc(n.x,n.y,n.r+7,0,7);cx.fillStyle='rgba(16,185,129,.22)';cx.fill();}
  cx.beginPath();cx.arc(n.x,n.y,match?n.r+2:n.r,0,7);cx.fillStyle=match?'#10b981':(n.type==='note'?n.color:((n.df||1)>1?'#c98a1b':'#aba69c'));cx.fill();
  if(match){cx.lineWidth=2;cx.strokeStyle='#047857';cx.stroke();}
  if(i===hover||i===sel){cx.lineWidth=2.5;cx.strokeStyle='#111';cx.stroke();}
  if(n.type==='note'||n.imp>0.13||i===hover||i===a||match){cx.globalAlpha=Math.max(0.3,n.a);cx.fillStyle='#1d1c1a';cx.font=(n.type==='note'?'600 14px Charter,"Iowan Old Style",Georgia,serif':'12px -apple-system,BlinkMacSystemFont,sans-serif');cx.textAlign='center';cx.fillText(n.label,n.x,n.y-n.r-5);}});
 cx.globalAlpha=1;}
function loop(){step();draw();requestAnimationFrame(loop);} for(let i=0;i<220;i++)step(); alpha=0.12; loop();
function pick(wx,wy){let b=-1,bd=1e9;N.forEach((n,i)=>{let d=Math.hypot(n.x-wx,n.y-wy);if(d<n.r+6&&d<bd){bd=d;b=i;}});return b;}
function rel(e){const r=cv.getBoundingClientRect();return [e.clientX-r.left,e.clientY-r.top];}
function toWorld(sx,sy){return [sx-panX,sy-panY];}
cv.addEventListener('mousemove',e=>{const[sx,sy]=rel(e);if(panning){panX=panX0+(sx-px0);panY=panY0+(sy-py0);moved=true;cv.style.cursor='grabbing';return;}const[wx,wy]=toWorld(sx,sy);if(drag>=0){const d=N[drag];d.x+=(wx-d.x)*0.25;d.y+=(wy-d.y)*0.25;d.vx=0;d.vy=0;moved=true;cv.style.cursor='grabbing';return;}hover=pick(wx,wy);cv.style.cursor=hover>=0?'pointer':'grab';});
cv.addEventListener('mousedown',e=>{const[sx,sy]=rel(e);const[wx,wy]=toWorld(sx,sy);drag=pick(wx,wy);moved=false;if(drag>=0){reheat(0.10);}else{panning=true;px0=sx;py0=sy;panX0=panX;panY0=panY;cv.style.cursor='grabbing';}});
addEventListener('mouseup',()=>{if(drag>=0)reheat(0.05);drag=-1;panning=false;});
cv.addEventListener('click',e=>{if(moved){moved=false;return;}const[sx,sy]=rel(e);const[wx,wy]=toWorld(sx,sy);const i=pick(wx,wy);if(i<0){sel=-1;card();return;}const n=N[i];if(n.type==='note')location.href=n.url;else{sel=i;card(i);}});
cv.addEventListener('wheel',e=>{e.preventDefault();zoomBy(Math.exp(-e.deltaY*0.0015));},{passive:false});
cv.addEventListener('dblclick',e=>{e.preventDefault();zoomBy(1.6);});
addEventListener('keydown',e=>{if(e.target&&(e.target.id==='q'||e.target.id==='mapq'||e.target.tagName==='INPUT'))return;if(e.key==='0'){resetView();}else if(e.key==='+'||e.key==='='){zoomBy(1.3);}else if(e.key==='-'||e.key==='_'){zoomBy(1/1.3);}});
function info(){document.getElementById('info').innerHTML='<span>Click a concept for its summary · click a note (colored) to open it · scroll / +\u2212 / double-click to spread out · drag background to pan · drag a node to move it · press 0 to reset.</span>';}
info();
const CARD=document.getElementById('card');
function cesc(t){return String(t).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));}
// concepts link only to notes, so "appears with" = concepts sharing a note
function coOccur(i){const cnt={};
  [...adj[i]].filter(j=>N[j].type==='note').forEach(j=>[...adj[j]].forEach(k=>{if(k!==i&&N[k].type!=='note')cnt[k]=(cnt[k]||0)+1;}));
  return Object.keys(cnt).map(k=>({i:+k,c:cnt[k]})).sort((a,b)=>b.c-a.c||N[a.i].label.localeCompare(N[b.i].label)).slice(0,12);}
function card(i){
  if(i==null||i<0){CARD.classList.remove('on');return;}
  const n=N[i], ns=[...adj[i]].map(j=>N[j]).filter(m=>m.type==='note'), co=coOccur(i);
  let h='<button class="cardx" title="Close">\u00d7</button>'
      +'<div class="ck">Concept</div><h3>'+cesc(n.label)+'</h3>'
      +'<div class="cmeta">appears in '+ns.length+' of '+N.filter(m=>m.type==='note').length+' notes</div>'
      +'<div class="csec">In these notes</div>'
      + ns.map(m=>'<a class="cn" href="'+cesc(m.url)+'">'+cesc(m.label)+'</a>').join('');
  if(co.length) h+='<div class="csec">Often appears with</div>'
      + co.map(o=>'<button class="chip" data-i="'+o.i+'">'+cesc(N[o.i].label)+(o.c>1?' \u00b7 '+o.c:'')+'</button>').join('');
  CARD.innerHTML=h; CARD.classList.add('on');
  CARD.querySelector('.cardx').onclick=()=>{sel=-1;card();};
  CARD.querySelectorAll('.chip').forEach(b=>b.onclick=()=>{const j=+b.dataset.i;sel=j;card(j);});
}
document.getElementById('mapq').addEventListener('input',e=>{q=e.target.value.trim().toLowerCase();reheat(0.02);});
const IB=document.getElementById('ib'),IP=document.getElementById('ip');
function toggleInfo(on){IP.classList.toggle('on',on);IB.classList.toggle('on',on);}
IB.onclick=e=>{e.stopPropagation();toggleInfo(!IP.classList.contains('on'));};
document.getElementById('ipx').onclick=()=>toggleInfo(false);
IP.onclick=e=>e.stopPropagation();
document.addEventListener('click',()=>toggleInfo(false));
addEventListener('keydown',e=>{if(e.key==='Escape')toggleInfo(false);});
document.getElementById('zin').onclick=()=>zoomBy(1.3);
document.getElementById('zout').onclick=()=>zoomBy(1/1.3);
document.getElementById('zreset').onclick=()=>resetView();
"""

mapdoc = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
 '<title>Knowledge map — '+theme.NAME+'</title>'+theme.FAVICON+'<style>'+CSS+
 'html,body{height:100%}body{display:flex;flex-direction:column}'
 '#cv{flex:1;display:block;width:100%}'
 '.maphead{max-width:var(--w-page);width:100%;margin:0 auto;padding:var(--s-4) var(--gutter);display:flex;gap:var(--s-3);align-items:center;flex-wrap:wrap}'
 '.maphead h1{margin:0 var(--s-2) 0 0;font-size:var(--fs-5)}'
 '#mapq{flex:0 1 240px}'
 '.ibtn,.zoom button{width:40px;height:40px;border:0;border-radius:var(--r-md);background:var(--surface);box-shadow:var(--sh-1);color:var(--ink-2);'
 'font:600 var(--fs-3)/1 var(--font-ui);cursor:pointer;flex:none;transition:color .15s var(--ease),box-shadow .15s var(--ease)}'
 '.ibtn{font-family:var(--font-read);font-style:italic}'
 '.ibtn.on{color:var(--accent);box-shadow:0 0 0 2px var(--accent)}'
 '@media (hover:hover){.ibtn:hover,.zoom button:hover{color:var(--accent);box-shadow:var(--sh-2)}}'
 '.zoom{display:flex;gap:var(--s-1)}'
 '.legend{display:flex;align-items:center;gap:var(--s-3);font-size:var(--fs-1);color:var(--mut);margin-left:auto}'
 '.legend .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:0}'
 '.mapstage{position:relative;flex:1;display:flex;min-height:0;box-shadow:0 -1px 0 var(--line)}'
 '.ipop,.mapcard{position:absolute;top:var(--s-4);z-index:55;background:rgba(255,253,249,.92);backdrop-filter:blur(14px) saturate(140%);'
 '-webkit-backdrop-filter:blur(14px) saturate(140%);border-radius:var(--r-lg);box-shadow:var(--sh-3);padding:var(--s-4) var(--s-5) var(--s-5)}'
 '.ipop{left:var(--gutter);width:340px;font-size:var(--fs-2);line-height:1.55;display:none}'
 '.ipop.on{display:block}'
 '.ipop h5{margin:0 0 var(--s-2);font:600 11px/1.2 var(--font-ui);letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}'
 '.ipop .row{display:flex;gap:var(--s-3);align-items:flex-start;margin:var(--s-2) 0}'
 '.ipop .sw{flex:none;margin-top:6px}'
 '.ipop .ln{display:block;width:26px;height:0;border-top-style:solid}'
 '.ipop .dt{display:block;border-radius:50%}'
 '.ipop .hr{height:1px;background:var(--line);margin:var(--s-3) 0}'
 '.ipop .x,.mapcard .cardx{position:absolute;right:var(--s-2);top:var(--s-2);width:32px;height:32px;border:0;background:none;'
 'border-radius:var(--r-sm);font:400 20px/1 var(--font-ui);color:var(--mut);cursor:pointer}'
 '@media (hover:hover){.ipop .x:hover,.mapcard .cardx:hover{background:var(--hover);color:var(--ink)}}'
 '.mapcard{right:var(--gutter);width:300px;max-height:calc(100% - 32px);overflow:auto;opacity:0;transform:translateY(-4px) scale(.98);'
 'pointer-events:none;transition:opacity .2s var(--ease),transform .2s var(--ease)}'
 '.mapcard.on{opacity:1;transform:none;pointer-events:auto}'
 '.mapcard h3{margin:var(--s-1) 0 var(--s-1);font-size:var(--fs-5);line-height:1.25;padding-right:var(--s-5)}'
 '.mapcard .cmeta{color:var(--mut);font-size:var(--fs-2);margin-bottom:var(--s-3)}'
 '.mapcard .ck,.mapcard .csec{font:600 11px/1.2 var(--font-ui);letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}'
 '.mapcard .csec{margin:var(--s-4) 0 var(--s-2)}'
 '.mapcard a.cn{display:block;padding:var(--s-2) var(--s-3);margin:var(--s-1) 0;border-radius:var(--r-sm);background:var(--accent-soft);'
 'color:var(--accent);text-decoration:none;font:600 var(--fs-2)/1.3 var(--font-ui)}'
 '.mapcard .chip{display:inline-flex;margin:0 var(--s-1) var(--s-1) 0;padding:6px 10px;border:0;border-radius:999px;background:var(--sunk);'
 'font:500 var(--fs-1)/1 var(--font-ui);color:var(--ink-2);cursor:pointer}'
 '@media (hover:hover){.mapcard a.cn:hover{background:rgba(47,79,179,.15)}.mapcard .chip:hover{color:var(--accent);background:var(--accent-soft)}}'
 '.infobar{max-width:var(--w-page);width:100%;margin:0 auto;padding:var(--s-3) calc(var(--gutter) + 150px) var(--s-3) var(--gutter);font-size:var(--fs-2);color:var(--mut);min-height:20px}'
 '</style></head><body>'
 + tabbar(MAP).replace('class="bar"','class="bar"') +
 '<div class="maphead"><h1>Knowledge map</h1><input id="mapq" class="field" placeholder="Find a concept…">'
 '<button class="ibtn" id="ib" title="What am I looking at?">i</button>'
 '<span class="zoom"><button id="zout" title="Zoom out">−</button><button id="zreset" title="Reset view">⟳</button><button id="zin" title="Zoom in">+</button></span>'
 '<span class="legend"><span><span class="dot" style="background:#2f4fb3"></span>note</span>'
 '<span><span class="dot" style="background:#c98a1b"></span>shared concept</span>'
 '<span><span class="dot" style="background:#aba69c"></span>concept</span></span></div>'
 '<div class="mapstage"><canvas id="cv"></canvas><aside id="card" class="mapcard"></aside>'
 '<div class="ipop" id="ip"><button class="x" id="ipx">&times;</button>'
 '<h5>Circles &mdash; things</h5>'
 '<div class="row"><span class="sw"><span class="dt" style="width:15px;height:15px;background:#2f4fb3"></span></span>'
 '<div><b>Note</b> &mdash; one of your topic notes. Click to open it.</div></div>'
 '<div class="row"><span class="sw"><span class="dt" style="width:12px;height:12px;background:#c98a1b"></span></span>'
 '<div><b>Concept</b> in several notes. <b>Size</b> = how much the vault is really about it, not how many notes mention it.</div></div>'
 '<div class="row"><span class="sw"><span class="dt" style="width:8px;height:8px;background:#aba69c"></span></span>'
 '<div><b>Concept</b> in a single note &mdash; the specific ones (OAuth, SAML, DORA).</div></div>'
 '<div class="hr"></div><h5>Lines &mdash; relationships</h5>'
 '<div class="row"><span class="sw"><span class="ln" style="border-top-width:3px;border-color:#8b93a5"></span></span>'
 '<div><b>note &rarr; concept</b><br>&ldquo;this note talks about this idea.&rdquo; <b>Thicker = the note is more about it</b>: '
 'weight is <code>times mentioned</code> &times; <code>how rare the word is</code>.</div></div>'
 '<div class="row"><span class="sw"><span class="ln" style="border-top-width:2px;border-color:#10b981"></span></span>'
 '<div><b>concept &harr; concept</b><br>&ldquo;these two ideas travel together&rdquo; &mdash; they show up in the same notes '
 'in the same proportions. Each concept keeps its 3 strongest partners.</div></div>'
 '<div class="hr"></div>'
 '<div style="color:var(--mut)">A word in <i>every</i> note (trust, roadmap) separates nothing, so it is pushed down; '
 'a word concentrated in one note pulls hard. Click any concept for its summary card.</div></div>'
 '</div>'
 '<div class="infobar" id="info"></div>'
 '<script>const GRAPH='+GRAPH+';'+MAPJS+'</script>'+WN_SNIPPET+SEARCH_JS+'</body></html>')
open(os.path.join(OUT,MAP),"w",encoding="utf-8").write(mapdoc)
print("wrote", MAP, f"({len(gnodes)} nodes, {len(glinks)} links)")
