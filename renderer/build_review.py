#!/usr/bin/env python3
"""Build the editable low-confidence REVIEW page for a batch.
Reads:  <review>/staging/<base>.md  (verbatim transcripts)
        <review>/lowconf.json        [{base,title,topic,low:[{reads_as,context,why}]}]
        <review>/assets/<base>.jpg   (rasterized scans; sips -s format jpeg -Z 1500 in.pdf --out ..)
Writes: <review>/review.html  → user edits, clicks Download corrections (handwritten-corrections.json),
        then Claude applies each file's transcript back onto staging/<base>.md.
Usage:  python3 build_review.py /path/to/Handwritten/_review"""
import json, os, sys, html, urllib.parse

REVIEW = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
STAGING = os.path.join(REVIEW, "staging")
DATA = json.load(open(os.path.join(REVIEW, "lowconf.json"), encoding="utf-8"))
esc = lambda s: html.escape(s or "", quote=True)

TOPIC_ORDER = []   # topics listed here come first on the review page
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
            f'<li><button class="jump" data-base="{esc(base)}" data-term="{esc(r["reads_as"])}">🔍</button>'
            f'<code>{esc(r["reads_as"])}</code> <span class="why why-{esc(r.get("why","ambiguous"))}">{esc(r.get("why",""))}</span>'
            f'<div class="ctx">{esc(r.get("context",""))}</div></li>' for r in low)
        low_html = f'<div class="low"><div class="low-h">⚠️ {len(low)} low-confidence to verify</div><ul>{items}</ul></div>'
    else:
        low_html = '<div class="low ok">✓ no low-confidence flags</div>'
    card = f'''<div class="card"><div class="card-h"><span class="fn">{esc(base)}.pdf</span><span class="topic">{esc(topic)}</span></div>
  <div class="title">{esc(d.get("title",""))}</div><div class="cols">
    <div class="imgcol"><a href="{img}" target="_blank"><img loading="lazy" src="{img}" alt="{esc(base)}"></a></div>
    <div class="txtcol">{low_html}<label>Transcript (edit anything — this is what gets saved):</label>
      <textarea id="ta-{esc(base)}" data-base="{esc(base)}" spellcheck="false">{esc(transcript)}</textarea></div></div></div>'''
    cards_by_topic.setdefault(topic, []).append(card)

order = [t for t in TOPIC_ORDER if t in cards_by_topic] + [t for t in cards_by_topic if t not in TOPIC_ORDER]
sections = "".join(f'<h2 id="sec-{esc(t)}">{esc(t)} <span class="n">({len(cards_by_topic[t])})</span></h2>' + "".join(cards_by_topic[t]) for t in order)
nav = " ".join(f'<a href="#sec-{esc(t)}">{esc(t)} ({len(cards_by_topic[t])})</a>' for t in order)

DOC = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Handwritten — review & edit</title><style>
:root{{--bg:#0f1115;--card:#1a1d24;--mut:#8b93a7;--acc:#7c9cff;--line:#2a2e38;--txt:#e6e9f0}}*{{box-sizing:border-box}}
body{{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--txt)}}
header{{position:sticky;top:0;z-index:10;background:#0f1115ee;backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:12px 20px}}
header h1{{font-size:16px;margin:0 0 6px}}header .meta{{color:var(--mut);font-size:13px}}
nav{{margin-top:8px;font-size:13px}}nav a{{color:var(--acc);text-decoration:none;margin-right:12px}}
button.dl{{background:var(--acc);color:#0b1020;border:0;border-radius:8px;padding:8px 14px;font-weight:600;cursor:pointer;float:right}}
main{{max-width:1100px;margin:0 auto;padding:20px}}h2{{margin:28px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--line)}}h2 .n{{color:var(--mut);font-weight:400;font-size:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin:14px 0}}.card-h{{display:flex;justify-content:space-between;align-items:center}}
.fn{{font-weight:600}}.topic{{color:var(--mut);font-size:12px;border:1px solid var(--line);border-radius:20px;padding:2px 10px}}.title{{color:var(--mut);font-size:13px;margin:4px 0 10px}}
.cols{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:16px}}@media(max-width:820px){{.cols{{grid-template-columns:1fr}}}}
.imgcol img{{width:100%;border-radius:8px;border:1px solid var(--line);background:#fff}}
.low{{background:#221a13;border:1px solid #4a3a22;border-radius:8px;padding:8px 10px;margin-bottom:10px}}.low.ok{{background:#13241a;border-color:#244a32;color:#8fe0a8}}
.low-h{{font-weight:600;font-size:13px;margin-bottom:4px}}.low ul{{margin:0;padding-left:0;list-style:none}}.low li{{margin:5px 0;font-size:13px}}
.low code{{background:#0f1115;border:1px solid var(--line);border-radius:4px;padding:1px 5px;color:#ffd479}}.low .ctx{{color:var(--mut);font-size:12px;margin:2px 0 0 24px}}
.why{{font-size:11px;border-radius:10px;padding:0 7px;margin-left:6px}}.why-illegible{{background:#5a2230;color:#ffb3c1}}.why-ambiguous{{background:#3a3320;color:#ffd479}}.why-cut-off{{background:#23314a;color:#9cc0ff}}.why-covered{{background:#3a234a;color:#d6a3ff}}
button.jump{{background:none;border:0;cursor:pointer;font-size:13px;padding:0 4px 0 0}}label{{display:block;font-size:12px;color:var(--mut);margin:0 0 4px}}
textarea{{width:100%;min-height:240px;background:#0f1115;color:var(--txt);border:1px solid var(--line);border-radius:8px;padding:10px;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;resize:vertical}}
.saved{{position:fixed;bottom:20px;right:20px;background:#13241a;border:1px solid #244a32;color:#8fe0a8;padding:10px 16px;border-radius:8px;display:none}}
</style></head><body>
<header><button class="dl" onclick="dl()">⬇ Download corrections</button><h1>Scanned pages — review & edit</h1>
<div class="meta">{len(DATA)} pages · {total_low} low-confidence spans. Check each ⚠️ against the scan, fix it in the box, then <b>Download corrections</b> and tell Claude to "apply corrections".</div>
<nav>{nav}</nav></header><main>{sections}</main><div class="saved" id="saved">✓ Saved to Downloads</div>
<script>
document.querySelectorAll('button.jump').forEach(b=>b.onclick=()=>{{const ta=document.getElementById('ta-'+b.dataset.base);if(!ta)return;const i=ta.value.indexOf(b.dataset.term.split(' ')[0]);ta.focus();if(i>=0)ta.setSelectionRange(i,i+b.dataset.term.length);ta.scrollIntoView({{behavior:'smooth',block:'center'}});}});
function dl(){{const files=[...document.querySelectorAll('textarea')].map(ta=>({{file:ta.dataset.base+'.pdf',base:ta.dataset.base,transcript:ta.value}}));const b=new Blob([JSON.stringify({{files}},null,2)],{{type:'application/json'}});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='handwritten-corrections.json';a.click();const s=document.getElementById('saved');s.style.display='block';setTimeout(()=>s.style.display='none',2500);}}
</script></body></html>'''
open(os.path.join(REVIEW, "review.html"), "w", encoding="utf-8").write(DOC)
print("wrote", os.path.join(REVIEW, "review.html"), "| pages:", len(DATA), "| low-conf:", total_low, "| missing:", missing or "none")
