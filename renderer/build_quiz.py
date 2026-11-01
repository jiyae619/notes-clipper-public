#!/usr/bin/env python3
"""Render quiz-bank.json into a self-contained MCQ flashcard app.
10 questions/round, instant right/wrong + explanation w/ source, ⭐ save-to-review (localStorage).
Output: $NOTES_OUT/handwritten-quiz.html . Re-run after editing quiz-bank.json."""
import os, json, html, glob, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import pages

def js_json(obj, **kw):
    """JSON for embedding inside <script>: '<' is escaped, so text from a capture
    (a quiz question, a title, a keyword) can never close the tag and start its own."""
    return json.dumps(obj, **kw).replace("<", "\\u003c")

HERE = os.path.dirname(os.path.abspath(__file__))
BANK = os.path.join(HERE, "quiz-bank.json")
OUT  = os.path.join(os.path.expanduser(os.environ.get("NOTES_OUT", "~/Documents/Notes Pages")), "handwritten-quiz.html")

bank = json.load(open(BANK, encoding="utf-8"))

# ---- validate ----
Q_TYPES={"recall","scenario","compare","negative","order"}   # question style (optional; default recall)
Q_LEVELS={"recall","apply","analyze"}                         # cognitive level (optional; default recall)
seen=set(); errs=[]
for i,q in enumerate(bank):
    for k in ("id","note","topic","src","q","opts","a","explain"):
        if k not in q: errs.append(f"#{i} missing '{k}'")
    if len(q.get("opts",[]))!=4: errs.append(f"{q.get('id','#%d'%i)}: needs exactly 4 opts")
    if not isinstance(q.get("a"),int) or not 0<=q.get("a",-1)<=3: errs.append(f"{q.get('id')}: 'a' must be 0-3")
    if "type" in q and q["type"] not in Q_TYPES: errs.append(f"{q.get('id')}: bad type '{q['type']}'")
    if "level" in q and q["level"] not in Q_LEVELS: errs.append(f"{q.get('id')}: bad level '{q['level']}'")
    if q.get("id") in seen: errs.append(f"duplicate id {q.get('id')}")
    seen.add(q.get("id"))
if errs:
    raise SystemExit("quiz-bank.json errors:\n  " + "\n  ".join(errs))

# ---- display-only: show handwritten scans as "Notebook scan N" ----
# Same labelling rule as build_html.py: archive PDFs
# sorted case-insensitively, minus the downloaded reference docs. The bank keeps
# the real filenames so every question stays traceable to its scan.
ARCHIVE = os.path.join(os.path.expanduser(os.environ.get("NOTES_VAULT", "~/Documents/Notes")), "Handwritten/archive")
# The page each note's questions link to: the same rule build_html.py writes pages by.
_NOTES_DIR = os.path.join(os.path.dirname(ARCHIVE), "notes")
PAGES = {pages.stem_of(f): p for f, p in pages.page_names(
    [os.path.basename(x) for x in glob.glob(os.path.join(_NOTES_DIR, "*.md"))], HERE).items()}
# Filenames of PDFs in archive/ that are published documents, not your scans,
# shown under their own names. Keep in step with build_html.py.
_OFFICIAL_DOCS = set()
try:
    _pdfs = sorted(f for f in os.listdir(ARCHIVE) if f.lower().endswith(".pdf"))
except OSError:
    _pdfs = []
_private = sorted((f for f in _pdfs if f not in _OFFICIAL_DOCS), key=str.lower)
SCAN_LABEL = {f: f"Notebook scan {i}" for i, f in enumerate(_private, 1)}
def _label(s):
    for f in sorted(SCAN_LABEL, key=len, reverse=True):   # "Agi safety 2.pdf" before "Agi safety.pdf"
        s = s.replace(f, SCAN_LABEL[f])
    return s
bank = [dict(q, src=_label(q["src"]), explain=_label(q["explain"]),
             opts=[_label(o) for o in q["opts"]]) for q in bank]

counts={}
for q in bank: counts[q["note"]]=counts.get(q["note"],0)+1

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1f2430;--mut:#6b7280;--acc:#3b5bdb;--line:#e5e7eb;
--ok:#0ca678;--okbg:#ecfdf5;--okbd:#6ee7b7;--bad:#e03131;--badbg:#fff5f5;--badbd:#ffc9c9;--gold:#f59e0b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--acc)}
.bar{position:sticky;top:0;z-index:5;background:#ffffffee;backdrop-filter:blur(8px);border-bottom:1px solid var(--line);padding:10px 18px;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.bar .home{font-weight:700;text-decoration:none;color:var(--ink)}
.bar .sp{margin-left:auto;font-size:13px;color:var(--mut)}
.wrap{max-width:720px;margin:0 auto;padding:26px 20px 90px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:22px 22px;box-shadow:0 1px 2px rgba(0,0,0,.03)}
h1{font-size:26px;letter-spacing:-.02em;margin:.1em 0 .3em}
.lead{color:var(--mut);font-size:14.5px;margin:.2em 0 1.2em}
label.fld{display:block;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);margin:0 0 5px}
select{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:10px;font-size:15px;background:#fff}
.btn{display:inline-block;border:0;background:var(--acc);color:#fff;font-weight:600;font-size:15px;padding:11px 18px;border-radius:11px;cursor:pointer;text-decoration:none}
.btn:hover{filter:brightness(1.05)}.btn:disabled{background:#c3c9d4;cursor:not-allowed}
.btn.ghost{background:#fff;color:var(--ink);border:1px solid var(--line)}
.btn.ghost:hover{border-color:var(--acc);color:var(--acc)}
.row{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
.stat{display:flex;gap:20px;margin:16px 0 4px;font-size:14px;color:var(--mut)}
.stat b{color:var(--ink);font-size:19px;display:block}
.prog{height:6px;background:#eef0f3;border-radius:6px;overflow:hidden;margin-bottom:16px}
.prog>i{display:block;height:100%;background:var(--acc);transition:width .25s}
.qmeta{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--mut);margin-bottom:6px}
.chip{background:#eef1fb;color:var(--acc);border-radius:20px;padding:2px 10px;font-weight:600}
.tag{font-size:11px;font-weight:700;border-radius:20px;padding:2px 9px}
.tag.ty{background:#f1f5f9;color:#475569}
.tag.lv-recall{background:#eef0f3;color:#6b7280}
.tag.lv-apply{background:#e7f0ff;color:#1d4ed8}
.tag.lv-analyze{background:#f3e8ff;color:#7e22ce}
.q{font-size:19px;font-weight:600;line-height:1.4;margin:6px 0 16px}
.opt{display:block;width:100%;text-align:left;background:#fff;border:1.5px solid var(--line);border-radius:12px;padding:13px 15px;margin:9px 0;font-size:15px;cursor:pointer;transition:.12s;position:relative}
.opt:hover:not(:disabled){border-color:var(--acc);background:#f8f9ff}
.opt:disabled{cursor:default}
.opt .k{display:inline-block;width:22px;height:22px;line-height:22px;text-align:center;border-radius:6px;background:#eef0f3;color:#6b7280;font-size:12px;font-weight:700;margin-right:10px}
.opt.correct{border-color:var(--okbd);background:var(--okbg)}
.opt.correct .k{background:var(--ok);color:#fff}
.opt.wrong{border-color:var(--badbd);background:var(--badbg)}
.opt.wrong .k{background:var(--bad);color:#fff}
.opt .mark{position:absolute;right:14px;top:50%;transform:translateY(-50%);font-weight:700}
.opt.correct .mark{color:var(--ok)}.opt.wrong .mark{color:var(--bad)}
.exp{border-radius:12px;padding:13px 15px;margin-top:14px;font-size:14.5px;border:1px solid}
.exp.ok{background:var(--okbg);border-color:var(--okbd)}
.exp.bad{background:var(--badbg);border-color:var(--badbd)}
.exp .verdict{font-weight:700;margin-bottom:4px}
.exp.ok .verdict{color:var(--ok)}.exp.bad .verdict{color:var(--bad)}
.src{margin-top:10px;font-size:12.5px;color:var(--mut)}
.src a{text-decoration:none;font-weight:600}
.footer{display:flex;align-items:center;gap:10px;margin-top:16px}
.savebtn{margin-left:auto;background:#fff;border:1px solid var(--line);border-radius:10px;padding:8px 12px;font-size:13px;cursor:pointer;color:var(--mut)}
.savebtn.on{background:#fffbeb;border-color:var(--gold);color:#92600a}
.missed{border-left:3px solid var(--badbd);padding:8px 12px;margin:10px 0;background:#fff;border-radius:0 8px 8px 0}
.missed .m-q{font-weight:600;font-size:14.5px}
.missed .m-a{font-size:13.5px;color:var(--ok);margin-top:3px}
.big{font-size:40px;font-weight:800;letter-spacing:-.02em}
kbd{background:#eef0f3;border:1px solid var(--line);border-radius:5px;padding:0 6px;font:12px ui-monospace,Menlo,monospace}
"""

APP = r"""
const SAVED_KEY='hw_quiz_saved';
const getSaved=()=>{try{return new Set(JSON.parse(localStorage.getItem(SAVED_KEY)||'[]'))}catch(e){return new Set()}};
const setSaved=s=>localStorage.setItem(SAVED_KEY,JSON.stringify([...s]));
let saved=getSaved();
const app=document.getElementById('app');
const byId=id=>BANK.find(q=>q.id===id);
const NOTES=[...new Set(BANK.map(q=>q.note))];
const NICE={};   // display names for note stems, e.g. {PM_UX:'PM / UX'}
const nice=n=>NICE[n]||n.replace(/_/g,' ');
// Each note's page, as build_html.py names it (pages.py); the index if it's gone.
const slug=n=>PAGES[n]||'handwritten-notes-index.html';
// Every value from the bank came from a capture: escape it wherever it goes into HTML.
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const shuffle=a=>{a=a.slice();for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]];}return a;};
const cnt=()=>{const c={};BANK.forEach(q=>c[q.note]=(c[q.note]||0)+1);return c;};
let S=null, keyEnabled=false;

function home(){
  saved=getSaved(); keyEnabled=false;
  const c=cnt();
  const opts=['<option value="__all">All topics ('+BANK.length+')</option>']
    .concat(NOTES.map(n=>'<option value="'+esc(n)+'">'+esc(nice(n))+' ('+c[n]+')</option>')).join('');
  app.innerHTML=`<div class="card">
    <h1>📝 Flashcard quiz</h1>
    <p class="lead">Multiple choice from your notes. 10 per round · instant feedback with the source · ⭐ save any question to review next time.</p>
    <div class="stat"><div><b>${BANK.length}</b>questions</div><div><b>${saved.size}</b>⭐ saved</div><div><b>${NOTES.length}</b>topics</div></div>
    <label class="fld" for="topic">Focus a topic</label>
    <select id="topic">${opts}</select>
    <label class="fld" for="level" style="margin-top:12px">Difficulty</label>
    <select id="level"><option value="__all">All levels</option><option value="recall">Recall — recognise a fact</option><option value="apply">Apply — use it in a scenario</option><option value="analyze">Analyze — diagnose / compare</option></select>
    <div class="row">
      <button class="btn" id="start">Start round (10)</button>
      <button class="btn ghost" id="review" ${saved.size?'':'disabled'}>Review saved (${saved.size})</button>
    </div>
    <div class="row"><button class="btn ghost" id="reset" ${saved.size?'':'disabled'} style="font-size:13px;padding:7px 12px">Clear saved</button></div>
    <p class="lead" style="margin-top:18px">Tip: press <kbd>1</kbd>–<kbd>4</kbd> to answer, <kbd>↵</kbd> for next.</p>
  </div>`;
  document.getElementById('start').onclick=()=>{
    const t=document.getElementById('topic').value;
    const lv=document.getElementById('level').value;
    let pool=t==='__all'?BANK:BANK.filter(q=>q.note===t);
    if(lv!=='__all')pool=pool.filter(q=>(q.level||'recall')===lv);
    if(!pool.length){alert('No questions match that topic + difficulty yet — try a different combination.');return;}
    startRound(pool);
  };
  document.getElementById('review').onclick=()=>{const p=BANK.filter(q=>saved.has(q.id));if(p.length)startRound(p,true);};
  document.getElementById('reset').onclick=()=>{if(confirm('Clear all saved questions?')){saved=new Set();setSaved(saved);home();}};
}

function startRound(pool,isReview){
  const picked=shuffle(pool).slice(0,10).map(q=>({q,order:shuffle([0,1,2,3]),chosen:null}));
  S={items:picked,idx:0,score:0,review:!!isReview};
  renderQ();
}

function renderQ(){
  keyEnabled=true;
  const it=S.items[S.idx], q=it.q, n=S.items.length;
  const pct=Math.round(S.idx/n*100);
  const lv=q.level||'recall', ty=q.type||'recall';
  const badges=(ty!=='recall'?`<span class="tag ty">${esc(ty)}</span>`:'')+`<span class="tag lv-${esc(lv)}">${esc(lv)}</span>`;
  const optHTML=it.order.map((oi,pos)=>{
    return `<button class="opt" data-pos="${pos}" ${it.chosen!=null?'disabled':''}>
      <span class="k">${pos+1}</span>${esc(q.opts[oi])}<span class="mark"></span></button>`;
  }).join('');
  app.innerHTML=`<div class="card">
    <div class="prog"><i style="width:${pct}%"></i></div>
    <div class="qmeta"><span class="chip">${esc(nice(q.note))}</span><span>${esc(q.topic)}</span>${badges}<span class="sp" style="margin-left:auto">${S.idx+1} / ${n}</span></div>
    <div class="q">${esc(q.q)}</div>
    <div id="opts">${optHTML}</div>
    <div id="after"></div>
  </div>`;
  [...document.querySelectorAll('.opt')].forEach(b=>b.onclick=()=>answer(+b.dataset.pos));
}

function answer(pos){
  const it=S.items[S.idx]; if(it.chosen!=null) return;
  const q=it.q, chosenOrig=it.order[pos], correct=chosenOrig===q.a;
  it.chosen=chosenOrig; if(correct)S.score++;
  const btns=[...document.querySelectorAll('.opt')];
  btns.forEach(b=>{b.disabled=true;const oi=it.order[+b.dataset.pos];
    if(oi===q.a){b.classList.add('correct');b.querySelector('.mark').textContent='✓';}
    else if(+b.dataset.pos===pos){b.classList.add('wrong');b.querySelector('.mark').textContent='✗';}});
  const isSaved=saved.has(q.id);
  const last=S.idx===S.items.length-1;
  document.getElementById('after').innerHTML=`
    <div class="exp ${correct?'ok':'bad'}">
      <div class="verdict">${correct?'✓ Correct':'✗ Not quite'}</div>
      <div>${esc(q.explain)}</div>
      <div class="src">📄 <a href="${esc(slug(q.note))}">${esc(nice(q.note))}</a> · ${esc(q.topic)} · <b>source:</b> ${esc(q.src)}</div>
    </div>
    <div class="footer">
      <button class="btn" id="next">${last?'See results':'Next →'}</button>
      <button class="savebtn ${isSaved?'on':''}" id="save">${isSaved?'★ Saved':'☆ Save to review'}</button>
    </div>`;
  document.getElementById('next').onclick=next;
  document.getElementById('save').onclick=()=>toggleSave(q.id);
}

function toggleSave(id){
  if(saved.has(id))saved.delete(id); else saved.add(id);
  setSaved(saved);
  const b=document.getElementById('save'); if(!b)return;
  const on=saved.has(id); b.classList.toggle('on',on); b.textContent=on?'★ Saved':'☆ Save to review';
}

function next(){ keyEnabled=false; S.idx++; if(S.idx<S.items.length) renderQ(); else end(); }

function end(){
  keyEnabled=false;
  const n=S.items.length, sc=S.score, pctv=Math.round(sc/n*100);
  const missed=S.items.filter(it=>it.chosen!==it.q.a);
  const emoji=pctv>=80?'🏆':pctv>=50?'👍':'📚';
  const missHTML=missed.length?('<h3 style="margin-top:22px;font-size:16px">Review these '+missed.length+'</h3>'+
    missed.map(it=>`<div class="missed"><div class="m-q">${esc(it.q.q)}</div>
      <div class="m-a">✓ ${esc(it.q.opts[it.q.a])}</div>
      <div class="src">📄 <a href="${esc(slug(it.q.note))}">${esc(nice(it.q.note))}</a> · source: ${esc(it.q.src)}
      &nbsp;<button class="savebtn ${saved.has(it.q.id)?'on':''}" data-sv="${esc(it.q.id)}">${saved.has(it.q.id)?'★ Saved':'☆ Save'}</button></div></div>`).join(''))
    :'<p class="lead" style="margin-top:18px">Clean sweep — nothing to review. 🎯</p>';
  app.innerHTML=`<div class="card">
    <div style="text-align:center">
      <div style="font-size:44px">${emoji}</div>
      <div class="big">${sc} / ${n}</div>
      <p class="lead">${pctv}% this round${S.review?' · (saved-review mode)':''}</p>
    </div>
    ${missHTML}
    <div class="row" style="margin-top:20px">
      <button class="btn" id="again">New round (10)</button>
      <button class="btn ghost" id="rev" ${saved.size?'':'disabled'}>Review saved (${saved.size})</button>
      <button class="btn ghost" id="h">Home</button>
    </div>
  </div>`;
  [...document.querySelectorAll('[data-sv]')].forEach(b=>b.onclick=()=>{toggleSaveInline(b);});
  document.getElementById('again').onclick=()=>startRound(BANK);
  document.getElementById('rev').onclick=()=>{const p=BANK.filter(q=>saved.has(q.id));if(p.length)startRound(p,true);};
  document.getElementById('h').onclick=home;
}
function toggleSaveInline(b){const id=b.dataset.sv;if(saved.has(id))saved.delete(id);else saved.add(id);setSaved(saved);
  const on=saved.has(id);b.classList.toggle('on',on);b.textContent=on?'★ Saved':'☆ Save';}

document.addEventListener('keydown',e=>{
  if(!keyEnabled&&!(S&&S.items&&S.idx<S.items.length))return;
  const it=S&&S.items[S.idx];
  if(it&&it.chosen==null&&['1','2','3','4'].includes(e.key)){const b=document.querySelector('.opt[data-pos="'+(+e.key-1)+'"]');if(b){e.preventDefault();b.click();}}
  else if(it&&it.chosen!=null&&(e.key==='Enter'||e.key==='ArrowRight')){const nx=document.getElementById('next');if(nx){e.preventDefault();nx.click();}}
  else if(it&&it.chosen!=null&&(e.key==='s'||e.key==='S')){const sv=document.getElementById('save');if(sv)sv.click();}
});
home();
"""

doc = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
 '<meta name="viewport" content="width=device-width,initial-scale=1">'
 '<title>Flashcard quiz — notes</title><link rel="icon" href="data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%20100%20100%22%3E%3Ctext%20y%3D%22.9em%22%20font-size%3D%2292%22%3E%F0%9F%93%9D%3C/text%3E%3C/svg%3E"><style>'+CSS+'</style></head><body>'
 '<header class="bar"><a class="home" href="handwritten-notes-index.html">📓 Notes</a>'
 '<a class="home" href="handwritten-knowledge-map.html" style="font-weight:500">🕸 Map</a>'
 '<span style="font-weight:700">📝 Quiz</span>'
 '<span class="sp">grounded in your notes</span></header>'
 '<div class="wrap"><div id="app"></div></div>'
 '<script>const BANK='+js_json(bank, ensure_ascii=False)+';const PAGES='+js_json(PAGES, ensure_ascii=False)+';'+APP+'</script></body></html>')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT,"w",encoding="utf-8").write(doc)
print("wrote", OUT)
print("bank:", len(bank), "questions across", len(counts), "notes ->", ", ".join(f"{nice if False else k}={v}" for k,v in counts.items()))
