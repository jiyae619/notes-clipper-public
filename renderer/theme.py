"""One look for every page the renderer writes: notes, index, map, quiz, the
What's new panel and the scan review page all build from these tokens and
components, so spacing, type and color can't drift apart page by page.

Direction: a quiet notebook. Reading text and headings are set in a bookish
serif (Charter / Iowan Old Style ship with macOS, so pages stay fully offline);
interface chrome uses the native UI face. Warm paper, one ink-blue accent,
hairlines and soft layered shadows instead of heavy borders.
"""
import urllib.parse

# The tab icon: the note emoji, as an inline SVG so there's no asset to ship.
FAVICON = ('<link rel="icon" href="data:image/svg+xml,' + urllib.parse.quote(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    '<text y=".9em" font-size="90">\U0001F4DD</text></svg>') + '">')

TOKENS = """
:root{
  --paper:#f6f4ef; --surface:#fffdf9; --sunk:#efece5; --hover:rgba(47,79,179,.06);
  --ink:#1d1c1a; --ink-2:#4a4741; --mut:#716d66; --line:rgba(29,28,26,.11); --line-2:rgba(29,28,26,.18);
  --accent:#2f4fb3; --accent-ink:#fff; --accent-soft:rgba(47,79,179,.09);
  --ok:#2d7a4f; --ok-soft:#e8f3ec; --bad:#b1412f; --bad-soft:#f8ebe7;
  --warn:#8a5a0a; --warn-soft:#faf0d8; --mark:#f6e2a0;
  --font-read:Charter,"Iowan Old Style","Source Serif Pro",Georgia,serif;
  --font-ui:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",sans-serif;
  --font-mono:ui-monospace,"SF Mono",Menlo,monospace;
  /* major-third scale from 16 */
  --fs-1:12px; --fs-2:13px; --fs-3:15px; --fs-4:17px; --fs-5:21px; --fs-6:26px; --fs-7:33px;
  --s-1:4px; --s-2:8px; --s-3:12px; --s-4:16px; --s-5:24px; --s-6:32px; --s-7:48px; --s-8:64px;
  --r-sm:6px; --r-md:10px; --r-lg:14px;
  --w-page:1120px; --w-read:720px; --gutter:24px;
  --sh-1:0 0 0 1px var(--line),0 1px 2px rgba(29,28,26,.04);
  --sh-2:0 0 0 1px var(--line),0 2px 6px rgba(29,28,26,.05),0 12px 28px rgba(29,28,26,.07);
  --sh-3:0 0 0 1px var(--line),0 24px 64px rgba(29,28,26,.22);
  --ease:cubic-bezier(.2,0,0,1);
}
"""

BASE = TOKENS + """
*{box-sizing:border-box}
html{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}
body{margin:0;color:var(--ink);font:var(--fs-3)/1.6 var(--font-ui);
  background:radial-gradient(1100px 520px at 12% -8%,rgba(47,79,179,.06),transparent 62%),
             radial-gradient(900px 480px at 100% 0%,rgba(201,146,40,.05),transparent 60%),var(--paper);
  background-attachment:fixed}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:.18em}
h1,h2,h3{font-family:var(--font-read);font-weight:600;text-wrap:balance;letter-spacing:-.01em}
p,li{text-wrap:pretty}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:var(--r-sm)}
.num{font-variant-numeric:tabular-nums}

/* header: full-bleed band, contents aligned to the page column */
.bar{position:sticky;top:0;z-index:20;background:rgba(246,244,239,.86);
  backdrop-filter:saturate(140%) blur(12px);-webkit-backdrop-filter:saturate(140%) blur(12px);
  box-shadow:0 1px 0 var(--line)}
.bar-in{max-width:var(--w-page);margin:0 auto;padding:0 var(--gutter);min-height:56px;
  display:flex;align-items:center;gap:var(--s-1);flex-wrap:wrap}
.home{font:600 var(--fs-5)/1 var(--font-read);color:var(--ink);text-decoration:none;
  margin-right:var(--s-4);letter-spacing:-.01em;padding:var(--s-2) 0}
.tab{position:relative;font:500 var(--fs-2)/1 var(--font-ui);color:var(--mut);text-decoration:none;
  padding:var(--s-3) var(--s-2);white-space:nowrap;transition:color .15s var(--ease)}
.tab::after{content:"";position:absolute;left:var(--s-2);right:var(--s-2);bottom:4px;height:2px;
  border-radius:2px;background:var(--accent);transform:scaleX(0);transition:transform .2s var(--ease)}
.tab.active{color:var(--ink)}
.tab.active::after{transform:scaleX(1)}
.tabsep{width:1px;height:20px;background:var(--line-2);margin:0 var(--s-2) 0 auto}
@media (hover:hover){.tab:hover{color:var(--ink)}}

.helpbtn{position:relative;flex:none;width:30px;height:30px;margin-left:var(--s-3);display:grid;place-items:center;border-radius:50%;
  background:var(--surface);box-shadow:var(--sh-1);color:var(--ink-2);font:600 var(--fs-3)/1 var(--font-read);text-decoration:none;
  transition:color .15s var(--ease),box-shadow .15s var(--ease)}
.helpbtn::after{content:"";position:absolute;inset:-5px}
.helpbtn[aria-current]{color:var(--accent);box-shadow:0 0 0 1.5px var(--accent)}
@media (hover:hover){.helpbtn:hover{color:var(--accent);box-shadow:var(--sh-2)}}

/* buttons: one family */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:var(--s-2);min-height:40px;
  padding:0 var(--s-4);border:0;border-radius:var(--r-md);font:600 var(--fs-3)/1 var(--font-ui);
  text-decoration:none;cursor:pointer;background:var(--accent);color:var(--accent-ink);
  transition:background-color .15s var(--ease),box-shadow .15s var(--ease),transform .1s var(--ease)}
.btn.quiet{background:var(--surface);color:var(--ink);box-shadow:var(--sh-1)}
.btn:active:not(:disabled){transform:scale(.97)}
.btn:disabled{background:var(--sunk);color:var(--mut);box-shadow:none;cursor:not-allowed}
@media (hover:hover){.btn:hover:not(:disabled){background:#28449c}
  .btn.quiet:hover:not(:disabled){background:var(--surface);box-shadow:var(--sh-2)}}

/* surfaces */
.panel{background:var(--surface);border-radius:var(--r-lg);box-shadow:var(--sh-1)}
.tag{display:inline-flex;align-items:center;font:500 var(--fs-1)/1 var(--font-ui);color:var(--ink-2);
  background:var(--sunk);border-radius:999px;padding:5px 10px}
.eyebrow{font:600 11px/1.2 var(--font-ui);letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}
.field{font:var(--fs-3)/1.2 var(--font-ui);color:var(--ink);background:var(--surface);border:0;
  border-radius:var(--r-md);box-shadow:var(--sh-1);padding:0 var(--s-3);min-height:40px}
.field:focus{outline:none;box-shadow:0 0 0 2px var(--accent)}
kbd{font:500 11px/1 var(--font-mono);color:var(--ink-2);background:var(--surface);box-shadow:var(--sh-1);
  border-radius:4px;padding:3px 5px}
mark{background:var(--mark);color:inherit;border-radius:3px;padding:0 2px}

@media (prefers-reduced-motion:reduce){*,*::before,*::after{transition-duration:.01ms!important;animation-duration:.01ms!important}}
@media (max-width:640px){:root{--gutter:16px}}
"""


NAME = "Notes-Clipper"
HELP = "handwritten-help.html"


def header(brand_href, items_html="", right_html="", help_href=HELP):
    """The shared top bar: the name on the left, then `items_html` (note tabs),
    then a divider and `right_html` (Map, Quiz, search) pushed right, and the
    help button last, in the same corner on every page."""
    sep = '<span class="tabsep"></span>' if items_html and right_html else ""
    push = "" if sep else '<span style="margin-left:auto"></span>'
    helpbtn = (f'<a class="helpbtn" href="{help_href}" title="How to use {NAME}" '
               f'aria-label="How to use {NAME}">?</a>') if help_href else ""
    return (f'<header class="bar"><nav class="bar-in"><a class="home" href="{brand_href}">{NAME}</a>'
            f'{items_html}{sep}{push}{right_html}{helpbtn}</nav></header>')
