#!/usr/bin/env python3
"""Build the editable low-confidence REVIEW page for a batch.
Reads:  <review>/staging/<base>.md  (verbatim transcripts)
        <review>/lowconf.json        [{base,title,topic,low:[{reads_as,context,why}]}]
        <review>/assets/<base>.jpg   (rasterized scans; sips -s format jpeg -Z 1500 in.pdf --out ..)
Writes: <review>/review.html  → user edits, clicks Download corrections (handwritten-corrections.json),
        then Claude applies each file's transcript back onto staging/<base>.md.
Usage:  python3 build_review.py /path/to/Handwritten/_review"""
import json, os, sys, html, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import theme, config

REVIEW = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
STAGING = os.path.join(REVIEW, "staging")
DATA = json.load(open(os.path.join(REVIEW, "lowconf.json"), encoding="utf-8"))
esc = lambda s: html.escape(s or "", quote=True)

TOPIC_ORDER = config.load(os.path.dirname(os.path.abspath(__file__))).get("review_topic_order", [])   # listed first
def keyf(d):
    t = d.get("topic","zzz")
    return (TOPIC_ORDER.index(t) if t in TOPIC_ORDER else 99, d["base"])

cards_by_topic, total_low, missing = {}, 0, []
for d in sorted(DATA, key=keyf):
    base, topic, low = d["base"], d.get("topic","other"), d.get("low",[])
    p = os.path.join(STAGING, base + ".md")
    transcript = open(p, encoding="utf-8").read() if os.path.exists(p) else (missing.append(base) or "[MISSING TRANSCRIPT]")
    total_low += len(low)
    img = "assets/" + urllib.parse.quote(base) + ".jpg"
    if low:
        items = "".join(
            f'<li><button class="jump" data-base="{esc(base)}" data-term="{esc(r["reads_as"])}">Find</button>'
            f'<code>{esc(r["reads_as"])}</code> <span class="why why-{esc(r.get("why","ambiguous"))}">{esc(r.get("why",""))}</span>'
            f'<div class="ctx">{esc(r.get("context",""))}</div></li>' for r in low)
        low_html = f'<div class="low"><div class="low-h">{len(low)} {"word" if len(low) == 1 else "words"} to check against the scan</div><ul>{items}</ul></div>'
    else:
        low_html = '<div class="low ok">Nothing flagged on this page</div>'
    card = f'''<div class="card"><div class="card-h"><span class="fn">{esc(base)}.pdf</span><span class="topic">{esc(topic)}</span></div>
  <div class="title">{esc(d.get("title",""))}</div><div class="cols">
    <div class="imgcol"><a href="{img}" target="_blank"><img loading="lazy" src="{img}" alt="{esc(base)}"></a></div>
    <div class="txtcol">{low_html}<label class="eyebrow" for="ta-{esc(base)}">Transcript — edit anything; this is what gets saved</label>
      <textarea id="ta-{esc(base)}" data-base="{esc(base)}" spellcheck="false">{esc(transcript)}</textarea></div></div></div>'''
    cards_by_topic.setdefault(topic, []).append(card)

order = [t for t in TOPIC_ORDER if t in cards_by_topic] + [t for t in cards_by_topic if t not in TOPIC_ORDER]
sections = "".join(f'<h2 id="sec-{esc(t)}">{esc(t)} <span class="n">({len(cards_by_topic[t])})</span></h2>' + "".join(cards_by_topic[t]) for t in order)
nav = " ".join(f'<a href="#sec-{esc(t)}">{esc(t)} ({len(cards_by_topic[t])})</a>' for t in order)

DOC = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scanned pages — review</title>{theme.FAVICON}<style>{theme.BASE}
.bar .grow{{flex:1}}
main{{max-width:var(--w-page);margin:0 auto;padding:var(--s-6) var(--gutter) var(--s-8)}}
.intro h1{{font-size:var(--fs-7);line-height:1.15;margin:0 0 var(--s-2)}}
.intro p{{color:var(--mut);margin:0 0 var(--s-4);max-width:var(--w-read)}}
.jumps{{display:flex;flex-wrap:wrap;gap:var(--s-2);margin:0 0 var(--s-5)}}
.jumps a{{font:500 var(--fs-2)/1 var(--font-ui);color:var(--ink-2);text-decoration:none;background:var(--surface);box-shadow:var(--sh-1);border-radius:999px;padding:var(--s-2) var(--s-3)}}
h2{{font-size:var(--fs-6);margin:var(--s-6) 0 var(--s-3)}}h2 .n{{color:var(--mut);font:400 var(--fs-3) var(--font-ui)}}
.card{{background:var(--surface);border-radius:var(--r-lg);box-shadow:var(--sh-1);padding:var(--s-5);margin:0 0 var(--s-4)}}
.card-h{{display:flex;justify-content:space-between;align-items:center;gap:var(--s-3)}}
.fn{{font:600 var(--fs-3)/1.3 var(--font-ui)}}.title{{color:var(--mut);font-size:var(--fs-2);margin:var(--s-1) 0 var(--s-4)}}
.cols{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:var(--s-5)}}
.imgcol img{{display:block;width:100%;border-radius:var(--r-md);box-shadow:0 0 0 1px var(--line);background:#fff}}
.low{{background:var(--warn-soft);color:var(--warn);border-radius:var(--r-md);padding:var(--s-3) var(--s-4);margin:0 0 var(--s-4)}}
.low.ok{{background:var(--ok-soft);color:var(--ok)}}
.low-h{{font-weight:600;font-size:var(--fs-2)}}.low ul{{margin:var(--s-2) 0 0;padding:0;list-style:none}}
.low li{{margin:var(--s-2) 0;font-size:var(--fs-2);color:var(--ink)}}
.low code{{font:var(--fs-2)/1.3 var(--font-mono);background:var(--surface);border-radius:4px;padding:1px 5px}}
.low .ctx{{color:var(--mut);font-size:var(--fs-1);margin:var(--s-1) 0 0}}
.why{{display:inline-block;font:600 10px/1.6 var(--font-ui);letter-spacing:.04em;border-radius:4px;padding:0 6px;margin-left:var(--s-1);background:var(--sunk);color:var(--ink-2)}}
.why-illegible{{background:var(--bad-soft);color:var(--bad)}}
button.jump{{min-height:28px;margin-right:var(--s-2);padding:0 var(--s-2);border:0;border-radius:var(--r-sm);background:var(--surface);box-shadow:var(--sh-1);
  font:600 var(--fs-1)/1 var(--font-ui);color:var(--accent);cursor:pointer}}
label.eyebrow{{display:block;margin:0 0 var(--s-2)}}
textarea{{width:100%;min-height:260px;resize:vertical;border:0;border-radius:var(--r-md);box-shadow:var(--sh-1);background:var(--surface);
  color:var(--ink);padding:var(--s-3);font:var(--fs-2)/1.6 var(--font-mono)}}
textarea:focus{{outline:none;box-shadow:0 0 0 2px var(--accent)}}
.saved{{position:fixed;right:var(--s-5);bottom:var(--s-5);display:none;background:var(--surface);color:var(--ok);box-shadow:var(--sh-2);
  border-radius:999px;padding:var(--s-3) var(--s-4);font:600 var(--fs-2)/1 var(--font-ui)}}
@media (max-width:860px){{.cols{{grid-template-columns:minmax(0,1fr)}}}}
</style></head><body>
<header class="bar"><div class="bar-in"><span class="home">Scanned pages</span><span class="grow"></span>
<button class="btn" onclick="dl()">Download corrections</button></div></header>
<main><div class="intro"><h1>Review the transcripts</h1>
<p>{len(DATA)} {"page" if len(DATA) == 1 else "pages"} · {total_low} {"word" if total_low == 1 else "words"} the transcriber wasn't sure of. Check each against the scan, fix anything in the box, then download your corrections: the next run applies them and files the pages.</p>
<nav class="jumps">{nav}</nav></div>{sections}</main><div class="saved" id="saved">Saved to Downloads</div>
<script>
document.querySelectorAll('button.jump').forEach(b=>b.onclick=()=>{{const ta=document.getElementById('ta-'+b.dataset.base);if(!ta)return;const i=ta.value.indexOf(b.dataset.term.split(' ')[0]);ta.focus();if(i>=0)ta.setSelectionRange(i,i+b.dataset.term.length);ta.scrollIntoView({{behavior:'smooth',block:'center'}});}});
function dl(){{const files=[...document.querySelectorAll('textarea')].map(ta=>({{file:ta.dataset.base+'.pdf',base:ta.dataset.base,transcript:ta.value}}));const b=new Blob([JSON.stringify({{files}},null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='handwritten-corrections.json';a.click();const s=document.getElementById('saved');s.style.display='block';setTimeout(()=>s.style.display='none',2500);}}
</script></body></html>'''
open(os.path.join(REVIEW, "review.html"), "w", encoding="utf-8").write(DOC)
print("wrote", os.path.join(REVIEW, "review.html"), "| pages:", len(DATA), "| low-conf:", total_low, "| missing:", missing or "none")
