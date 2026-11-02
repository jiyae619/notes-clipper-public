#!/usr/bin/env python3
"""Render quiz-bank.json into a self-contained MCQ flashcard app.
10 questions/round, instant right/wrong + explanation w/ source, save-to-review (localStorage).
Output: $NOTES_OUT/handwritten-quiz.html . Re-run after editing quiz-bank.json."""
import os, json, html, glob, sys
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import pages, theme

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

CSS = theme.BASE + """
.wrap{max-width:var(--w-read);margin:0 auto;padding:var(--s-7) var(--gutter) var(--s-8)}
.card{background:var(--surface);border-radius:var(--r-lg);box-shadow:var(--sh-1);padding:var(--s-6)}
h1{font-size:var(--fs-7);line-height:1.15;margin:0 0 var(--s-2)}
.lead{color:var(--mut);font-size:var(--fs-3);margin:0 0 var(--s-5)}
.stat{display:grid;grid-template-columns:repeat(3,1fr);gap:var(--s-4);margin:0 0 var(--s-5);padding:var(--s-4) 0;
  box-shadow:0 -1px 0 var(--line),0 1px 0 var(--line)}
.stat div{font-size:var(--fs-2);color:var(--mut)}
.stat b{display:block;font:600 var(--fs-6)/1.2 var(--font-read);color:var(--ink);font-variant-numeric:tabular-nums}
label.fld{display:block;margin:var(--s-4) 0 var(--s-2)}
select.field{width:100%;appearance:none;-webkit-appearance:none;padding-right:var(--s-6);
  background:var(--surface) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 6'%3E%3Cpath d='M1 1l4 4 4-4' fill='none' stroke='%23716d66' stroke-width='1.4'/%3E%3C/svg%3E") right 14px center/10px 6px no-repeat}
.row{display:flex;gap:var(--s-3);flex-wrap:wrap;margin-top:var(--s-5)}
.tip{color:var(--mut);font-size:var(--fs-2);margin:var(--s-5) 0 0}
.prog{height:4px;background:var(--sunk);border-radius:999px;overflow:hidden;margin-bottom:var(--s-5)}
.prog>i{display:block;height:100%;background:var(--accent);border-radius:999px;transition:width .25s var(--ease)}
.qmeta{display:flex;align-items:center;flex-wrap:wrap;gap:var(--s-2);font-size:var(--fs-1);color:var(--mut);margin-bottom:var(--s-3)}
.chip{font:600 var(--fs-1)/1 var(--font-ui);color:var(--accent);background:var(--accent-soft);border-radius:999px;padding:5px 10px}
.qmeta .sp{margin-left:auto;font-variant-numeric:tabular-nums}
.tag.lv-apply{color:var(--accent);background:var(--accent-soft)}
.tag.lv-analyze{color:#7a3fa0;background:#f2eaf7}
.q{font:600 var(--fs-5)/1.4 var(--font-read);margin:0 0 var(--s-4);text-wrap:pretty}
.opt{display:flex;align-items:center;gap:var(--s-3);width:100%;min-height:52px;text-align:left;margin:0 0 var(--s-2);
  padding:var(--s-3) var(--s-4);border:0;border-radius:var(--r-md);background:var(--surface);box-shadow:var(--sh-1);
  font:var(--fs-3)/1.45 var(--font-ui);color:var(--ink);cursor:pointer;
  transition:box-shadow .15s var(--ease),background-color .15s var(--ease),transform .1s var(--ease)}
.opt:active:not(:disabled){transform:scale(.99)}
.opt:disabled{cursor:default}
.opt .k{flex:none;width:24px;height:24px;display:grid;place-items:center;border-radius:var(--r-sm);background:var(--sunk);
  color:var(--ink-2);font:600 var(--fs-1)/1 var(--font-ui)}
.opt .mark{margin-left:auto;font-weight:600}
@media (hover:hover){.opt:hover:not(:disabled){box-shadow:0 0 0 1.5px var(--accent)}}
.opt.correct{background:var(--ok-soft);box-shadow:0 0 0 1.5px var(--ok)}
.opt.correct .k{background:var(--ok);color:#fff}.opt.correct .mark{color:var(--ok)}
.opt.wrong{background:var(--bad-soft);box-shadow:0 0 0 1.5px var(--bad)}
.opt.wrong .k{background:var(--bad);color:#fff}.opt.wrong .mark{color:var(--bad)}
.exp{border-radius:var(--r-md);padding:var(--s-4);margin-top:var(--s-4);font-size:var(--fs-3);line-height:1.55}
.exp.ok{background:var(--ok-soft)}.exp.bad{background:var(--bad-soft)}
.exp .verdict{font-weight:600;margin-bottom:var(--s-1)}
.exp.ok .verdict{color:var(--ok)}.exp.bad .verdict{color:var(--bad)}
.src{margin-top:var(--s-3);font-size:var(--fs-2);color:var(--mut)}
.src a{font-weight:600;text-decoration:none}
.footer{display:flex;align-items:center;gap:var(--s-3);margin-top:var(--s-5)}
.savebtn{margin-left:auto;min-height:40px;padding:0 var(--s-4);border:0;border-radius:var(--r-md);background:var(--surface);
  box-shadow:var(--sh-1);font:500 var(--fs-2)/1 var(--font-ui);color:var(--ink-2);cursor:pointer;transition:box-shadow .15s var(--ease)}
.savebtn.on{color:var(--warn);background:var(--warn-soft);box-shadow:none}
.missed .savebtn{min-height:32px;margin-left:var(--s-2)}
.result{text-align:center;padding:var(--s-2) 0 var(--s-4)}
.big{font:600 56px/1 var(--font-read);letter-spacing:-.02em;font-variant-numeric:tabular-nums;margin:var(--s-2) 0}
.missed-h{font-size:var(--fs-5);margin:var(--s-5) 0 var(--s-3)}
.missed{padding:var(--s-3) var(--s-4);margin:0 0 var(--s-2);background:var(--surface);border-radius:var(--r-md);box-shadow:inset 3px 0 0 var(--bad),var(--sh-1)}
.missed .m-q{font-weight:600;font-size:var(--fs-3)}
.missed .m-a{font-size:var(--fs-2);color:var(--ok);margin-top:var(--s-1)}
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
    <h1>Quiz</h1>
    <p class="lead">Multiple choice from your notes, ten per round. Each answer shows where it came from; save any question to see it again.</p>
    <div class="stat"><div><b>${BANK.length}</b>questions</div><div><b>${saved.size}</b>saved</div><div><b>${NOTES.length}</b>topics</div></div>
    <label class="fld eyebrow" for="topic">Topic</label>
    <select id="topic" class="field">${opts}</select>
    <label class="fld eyebrow" for="level">Difficulty</label>
    <select id="level" class="field"><option value="__all">All levels</option><option value="recall">Recall — recognise a fact</option><option value="apply">Apply — use it in a scenario</option><option value="analyze">Analyze — diagnose / compare</option></select>
    <div class="row">
      <button class="btn" id="start">Start a round</button>
      <button class="btn quiet" id="review" ${saved.size?'':'disabled'}>Review saved (${saved.size})</button>
      <button class="btn quiet" id="reset" ${saved.size?'':'disabled'}>Clear saved</button>
    </div>
    <p class="tip">Press <kbd>1</kbd>–<kbd>4</kbd> to answer and <kbd>↵</kbd> for the next question.</p>
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
      <div class="src"><a href="${esc(slug(q.note))}">${esc(nice(q.note))}</a> · ${esc(q.topic)} · <b>source:</b> ${esc(q.src)}</div>
    </div>
    <div class="footer">
      <button class="btn" id="next">${last?'See results':'Next →'}</button>
      <button class="savebtn ${isSaved?'on':''}" id="save">${isSaved?'Saved for review':'Save for review'}</button>
    </div>`;
  document.getElementById('next').onclick=next;
  document.getElementById('save').onclick=()=>toggleSave(q.id);
}

function toggleSave(id){
  if(saved.has(id))saved.delete(id); else saved.add(id);
  setSaved(saved);
  const b=document.getElementById('save'); if(!b)return;
  const on=saved.has(id); b.classList.toggle('on',on); b.textContent=on?'Saved for review':'Save for review';
}

function next(){ keyEnabled=false; S.idx++; if(S.idx<S.items.length) renderQ(); else end(); }

function end(){
  keyEnabled=false;
  const n=S.items.length, sc=S.score, pctv=Math.round(sc/n*100);
  const missed=S.items.filter(it=>it.chosen!==it.q.a);
  const missHTML=missed.length?('<h3 class="missed-h">Review these '+missed.length+'</h3>'+
    missed.map(it=>`<div class="missed"><div class="m-q">${esc(it.q.q)}</div>
      <div class="m-a">✓ ${esc(it.q.opts[it.q.a])}</div>
      <div class="src"><a href="${esc(slug(it.q.note))}">${esc(nice(it.q.note))}</a> · source: ${esc(it.q.src)}
      &nbsp;<button class="savebtn ${saved.has(it.q.id)?'on':''}" data-sv="${esc(it.q.id)}">${saved.has(it.q.id)?'Saved':'Save'}</button></div></div>`).join(''))
    :'<p class="lead">Every answer right: nothing to review.</p>';
  app.innerHTML=`<div class="card">
    <div class="result">
      <div class="eyebrow">${S.review?'Saved questions':'This round'}</div>
      <div class="big">${sc} / ${n}</div>
      <p class="lead">${pctv}% right</p>
    </div>
    ${missHTML}
    <div class="row">
      <button class="btn" id="again">New round</button>
      <button class="btn quiet" id="rev" ${saved.size?'':'disabled'}>Review saved (${saved.size})</button>
      <button class="btn quiet" id="h">Home</button>
    </div>
  </div>`;
  [...document.querySelectorAll('[data-sv]')].forEach(b=>b.onclick=()=>{toggleSaveInline(b);});
  document.getElementById('again').onclick=()=>startRound(BANK);
  document.getElementById('rev').onclick=()=>{const p=BANK.filter(q=>saved.has(q.id));if(p.length)startRound(p,true);};
  document.getElementById('h').onclick=home;
}
function toggleSaveInline(b){const id=b.dataset.sv;if(saved.has(id))saved.delete(id);else saved.add(id);setSaved(saved);
  const on=saved.has(id);b.classList.toggle('on',on);b.textContent=on?'Saved':'Save';}

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
 '<title>Quiz — '+theme.NAME+'</title>'+theme.FAVICON+'<style>'+CSS+'</style></head><body>'
 + theme.header("handwritten-notes-index.html", "", '<a class="tab" href="handwritten-knowledge-map.html">Map</a>'
                '<a class="tab active" href="handwritten-quiz.html" aria-current="page">Quiz</a>') +
 '<div class="wrap"><div id="app"></div></div>'
 '<script>const BANK='+js_json(bank, ensure_ascii=False)+';const PAGES='+js_json(PAGES, ensure_ascii=False)+';'+APP+'</script></body></html>')

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT,"w",encoding="utf-8").write(doc)
print("wrote", OUT)
print("bank:", len(bank), "questions across", len(counts), "notes ->", ", ".join(f"{nice if False else k}={v}" for k,v in counts.items()))
