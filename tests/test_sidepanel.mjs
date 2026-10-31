// Extension tests: load extension/sidepanel.js into a sandbox with a small fake
// Chrome (storage, tabs, downloads, badge) and fake DOM elements, then drive it
// the way the panel is used. The watcher routes whatever markdown lands in the
// inbox, so a wrong frontmatter line here becomes a wrong note there, and a
// lost or duplicated save is a lost or duplicated capture.
import { test } from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const file = process.env.SIDEPANEL_UNDER_TEST || fileURLToPath(new URL("../extension/sidepanel.js", import.meta.url)); // override to test a mutated copy
const src = fs.readFileSync(file, "utf8");
const PAGE = "https://example.com/post";
const KEY = "capture:" + PAGE;
const tick = () => new Promise((r) => setTimeout(r, 0));

// A fresh panel on PAGE. `onDownload(opts, store)` runs as each download
// starts; `failDownloads` makes Chrome reject them. `frames` is the text each
// frame of the page yields to Summarize, the page itself first; an Error the
// page throws; or a function of the injection target returning a promise of
// either (to hold the copy mid-way, or answer only for the page itself).
// `fastTimeout` runs the panel's page timeouts (5 s, 3 s for frames) at once.
// `siteAccess` false is Chrome's Site access "On click": the panel may not read
// the page until a permission request, which `grant` answers.
// `others` are captures stored for other pages (url → capture); `openTabs` are
// other tabs open besides PAGE's.
async function panel({ stored = null, onDownload = () => {}, failDownloads = false, frames = [], fastTimeout = false,
                       siteAccess = true, grant = true, others = {}, openTabs = [] } = {}) {
  const elements = {};
  const element = () => ({ listeners: {}, addEventListener(t, f) { this.listeners[t] = f; }, disabled: false, hidden: false,
    value: "", textContent: "", className: "", style: {}, children: [], title: "",
    classList: { set: new Set(), add(c) { this.set.add(c); }, remove(c) { this.set.delete(c); }, contains(c) { return this.set.has(c); } },
    appendChild(c) { this.children.push(c); }, append(...c) { this.children.push(...c); }, replaceChildren(...c) { this.children = c; }, click() {} });
  const store = stored ? { [KEY]: structuredClone(stored) } : {};
  for (const [url, cap] of Object.entries(others)) store["capture:" + url] = structuredClone({ url, ...cap });
  const downloads = [];
  const chrome = {
    runtime: { lastError: undefined },
    tabs: {
      open: [{ id: 1, url: PAGE, title: "A post", windowId: 1 }, ...openTabs], created: [], activated: [],
      query: async function (q) { return q?.active ? this.open.slice(0, 1) : this.open; },
      create: async function ({ url }) { this.created.push(url); },
      update: async function (id) { this.activated.push(id); },
      onActivated: { addListener() {} }, onUpdated: { addListener() {} },
    },
    windows: { update: async () => {} },
    storage: {
      local: {
        get: async (k) => (k == null ? structuredClone(store) : k in store ? { [k]: structuredClone(store[k]) } : {}),
        set: async (o) => { for (const [k, v] of Object.entries(o)) store[k] = structuredClone(v); },
        remove: async (k) => { delete store[k]; },
      },
      onChanged: { addListener() {} },
    },
    action: { badge: null, setBadgeText({ text }) { this.badge = text; } },
    permissions: {
      requests: 0, injected: 0,
      contains: async () => siteAccess,
      request: async function () { this.requests++; siteAccess = grant; return grant; },
      onAdded: { addListener() {} }, onRemoved: { addListener() {} },
    },
    scripting: {
      executeScript: async ({ target }) => {
        chrome.permissions.injected++;
        // Chrome holds an injection on a site the extension may not read.
        if (!siteAccess) return new Promise(() => {});
        const f = typeof frames === "function" ? await frames(target) : frames;
        if (f instanceof Error) throw f;
        return (target.allFrames ? f : f.slice(0, 1)).map((result) => ({ result }));
      },
    },
    downloads: {
      download(opts, cb) {
        downloads.push(opts);
        setTimeout(() => {
          if (failDownloads) { chrome.runtime.lastError = { message: "disk full" }; cb(undefined); chrome.runtime.lastError = undefined; return; }
          onDownload(opts, store);
          cb(downloads.length);
        }, 0);
      },
      search: (_q, cb) => cb([{ state: "complete" }]),
      onChanged: { addListener() {}, removeListener() {} },
    },
  };
  const sandbox = {
    document: { getElementById: (id) => (elements[id] ??= element()), addEventListener() {}, activeElement: null, createElement: element },
    chrome, crypto, Blob, URL, fetch, clearTimeout,
    setTimeout: fastTimeout ? (f, ms) => setTimeout(f, ms === 5000 || ms === 3000 ? 0 : ms) : setTimeout, console, encodeURIComponent, structuredClone,
  };
  vm.createContext(sandbox);
  vm.runInContext(src, sandbox);
  await tick(); await tick();  // let the panel read the active tab
  const save = () => elements.save.listeners.click();
  const summarize = () => elements.summarize.listeners.click();
  return { ...sandbox, store, downloads, elements, chrome, save, summarize };
}

const { buildMarkdown, slugify, videoIdOf } = await panel();
const capture = (over = {}) => ({ title: "A page", url: "https://www.example.com/post?id=7", clips: [], note: "", ...over });
const frontmatter = (md) => md.split("\n---\n")[0].replace(/^---\n/, "").split("\n");
const clip = (id, text = "a line") => ({ id, text, videoTime: null, added: 1 });

// ---- frontmatter: what the router reads to decide how to file a capture ----

test("frontmatter carries the title, the source URL, and the site without www", () => {
  const fm = frontmatter(buildMarkdown(capture({ clips: [{ text: "x" }] })));
  assert.ok(fm.includes('title: "A page"'));
  assert.ok(fm.includes('source: "https://www.example.com/post?id=7"'));
  assert.ok(fm.includes("site: example.com"));
  assert.ok(fm.some((l) => /^captured: \d{4}-\d\d-\d\d \d\d:\d\d$/.test(l)));
});

test("G13: quotes and backslashes in a title survive as one valid YAML string", () => {
  const fm = frontmatter(buildMarkdown(capture({ title: 'He said "hi" in C:\\new', clips: [{ text: "x" }] })));
  assert.ok(fm.includes('title: "He said \\"hi\\" in C:\\\\new"'), fm.find((l) => l.startsWith("title:")));
});

test("summarize mode is only set while the whole-page clip is still there", () => {
  // Removing the page clip cancels summarize: there's nothing left to summarize.
  const page = { kind: "page", text: "full text" };
  assert.ok(frontmatter(buildMarkdown(capture({ mode: "summarize", clips: [page] }))).includes("mode: summarize"));
  assert.ok(!buildMarkdown(capture({ mode: "summarize", clips: [{ text: "hand-picked" }] })).includes("mode: summarize"));
});

test("a video capture records its id so the watcher can fetch captions", () => {
  const md = buildMarkdown(capture({ mode: "summarize", videoId: "abc123", clips: [{ kind: "page", text: "[video]" }] }));
  assert.ok(frontmatter(md).includes("video_id: abc123"));
});

test("image clips are listed in the frontmatter and embedded by filename", () => {
  const md = buildMarkdown(capture({ clips: [{ image: { name: "" }, file: "stem-img1.png" }] }));
  assert.ok(frontmatter(md).includes("  - stem-img1.png"));
  assert.ok(md.includes("![[stem-img1.png]]"));
});

// ---- body: the verbatim record that gets archived ----

test("every line of a text clip is quoted, so the archive keeps it verbatim", () => {
  const md = buildMarkdown(capture({ clips: [{ text: "line one\nline two" }] }));
  assert.ok(md.includes("> line one\n> line two"));
});

test("a clip from a video links to its moment, Shorts included", () => {
  const md = buildMarkdown(capture({ url: "https://www.youtube.com/watch?v=abc123", clips: [{ text: "x", videoTime: 75 }] }));
  assert.ok(md.includes("## Clip 1 — [1:15](https://youtu.be/abc123?t=75)"));
  const short = buildMarkdown(capture({ url: "https://www.youtube.com/shorts/xyz789", clips: [{ text: "x", videoTime: 5 }] }));
  assert.ok(short.includes("[0:05](https://youtu.be/xyz789?t=5)"));
});

test("'My note' appears only when you wrote one", () => {
  assert.ok(buildMarkdown(capture({ clips: [{ text: "x" }], note: "why it matters" })).includes("## My note\n\nwhy it matters"));
  assert.ok(!buildMarkdown(capture({ clips: [{ text: "x" }], note: "   " })).includes("## My note"));
});

// ---- filenames and video detection ----

test("slugs keep Korean titles readable and never come out empty", () => {
  assert.equal(slugify("AI 에이전트 콜드 스타트"), "ai-에이전트-콜드-스타트");
  assert.equal(slugify("Hello, World!"), "hello-world");
  assert.equal(slugify("!!!"), "capture");
  assert.ok(slugify("x".repeat(80)).length <= 50);
});

test("G14: slugs drop accents but keep letters, in any script", () => {
  assert.equal(slugify("Ünïcödé café"), "unicode-cafe");
  assert.equal(slugify("日本語のタイトル"), "日本語のタイトル");
});

test("G11: every YouTube URL form is recognized as a video, look-alikes aren't", () => {
  for (const u of ["https://www.youtube.com/watch?v=abc123&t=30s", "https://m.youtube.com/watch?v=abc123",
    "https://youtu.be/abc123?si=xyz", "https://www.youtube.com/shorts/abc123", "https://www.youtube.com/live/abc123",
    "https://www.youtube.com/embed/abc123", "https://music.youtube.com/watch?v=abc123"]) {
    assert.equal(videoIdOf(u), "abc123", u);
  }
  assert.equal(videoIdOf("https://notyoutube.com.evil.io/watch?v=abc123"), null);
  assert.equal(videoIdOf("https://www.youtube.com/@channel"), null);
});

// ---- saving: what reaches the inbox, and what's left in the panel ----

test("saving writes the markdown to notes-inbox as a Blob, not a size-capped data: URL (G10)", async () => {
  const p = await panel({ stored: { title: "A post", url: PAGE, clips: [clip("c1")], note: "" } });
  await p.save();
  const md = p.downloads.find((d) => d.filename.endsWith(".md"));
  assert.match(md.filename, /^notes-inbox\/\d{4}-\d\d-\d\d-a-post-\d{6}\.md$/);
  assert.ok(md.url.startsWith("blob:"), md.url.slice(0, 30));
});

test("after a save the page's clips are cleared and the badge empties", async () => {
  const p = await panel({ stored: { title: "A post", url: PAGE, clips: [clip("c1"), clip("c2")], note: "why" } });
  await p.save();
  await tick();  // the badge updates just after the save settles
  assert.equal(p.store[KEY], undefined);
  assert.equal(p.chrome.action.badge, "");
});

test("G9: a double-click on Save writes the capture once", async () => {
  const p = await panel({ stored: { title: "A post", url: PAGE, clips: [clip("c1")], note: "" } });
  await Promise.all([p.save(), p.save()]);
  assert.equal(p.downloads.filter((d) => d.filename.endsWith(".md")).length, 1);
});

test("G8: a clip added while a save is writing files is kept for the next save", async () => {
  const lateClip = clip("late", "added from the right-click menu mid-save");
  const p = await panel({
    stored: { title: "A post", url: PAGE, clips: [clip("c1"), clip("c2")], note: "" },
    onDownload: (opts, store) => { if (opts.filename.endsWith(".md")) store[KEY].clips.push(lateClip); },
  });
  await p.save();
  await tick();  // the badge updates just after the save settles
  assert.deepEqual(p.store[KEY]?.clips.map((c) => c.id), ["late"]);
  assert.equal(p.chrome.action.badge, "1");
});

test("a failed save keeps every clip and re-enables Save", async () => {
  const p = await panel({ stored: { title: "A post", url: PAGE, clips: [clip("c1")], note: "" }, failDownloads: true });
  await p.save();
  assert.deepEqual(p.store[KEY].clips.map((c) => c.id), ["c1"]);
  assert.equal(p.elements.save.disabled, false);
});

// ---- Summarize whole page: it looked dead when its only feedback landed
// below the fold, so every outcome must show under the button and leave it
// clickable again ----

const words = (n) => Array.from({ length: n }, (_, i) => "word" + i).join(" ");

test("Summarize reads the article from an embedded frame, not just the short top frame", async () => {
  const p = await panel({ frames: [words(20), words(300)] });
  await p.summarize();
  const c = p.store[KEY];
  assert.equal(c.mode, "summarize");
  assert.equal(c.clips.filter((x) => x.kind === "page").length, 1);
  assert.equal(c.clips[0].text.split(" ").length, 300);
  assert.match(p.elements["summarize-hint"].textContent, /Page text added \(300 words\)\. Nothing is summarized yet/);
  assert.equal(p.elements.summarize.disabled, false);
});

test("Summarize on a page with too little text says so under the button and saves nothing", async () => {
  const p = await panel({ frames: [words(30)] });
  await p.summarize();
  assert.equal(p.store[KEY], undefined);
  assert.match(p.elements["summarize-hint"].textContent, /too little text/);
  assert.match(p.elements["summarize-hint"].className, /err/);
  assert.equal(p.elements.summarize.disabled, false);
});

test("Summarize on a page Chrome won't let it read reports the error and stays clickable", async () => {
  const p = await panel({ frames: new Error("Cannot access a chrome:// URL") });
  await p.summarize();
  assert.match(p.elements["summarize-hint"].textContent, /Can’t read this page: Cannot access/);
  assert.equal(p.elements.summarize.disabled, false);
});

test("Save waits while the page text is being copied, so it can't send the capture without it", async () => {
  let release;
  const p = await panel({ stored: { title: "A post", url: PAGE, clips: [clip("c1")], note: "" },
    frames: () => new Promise((r) => { release = () => r([words(300)]); }) });
  const pending = p.summarize();
  await tick();
  assert.equal(p.elements.save.disabled, true);
  await p.save();                       // a click that gets through anyway does nothing
  assert.equal(p.downloads.length, 0);
  release(); await pending;
  assert.equal(p.elements.save.disabled, false);
  await p.save();
  assert.equal(p.downloads.filter((d) => d.filename.endsWith(".md")).length, 1);
});

test("after saving a whole page, the panel says the summary is written later, in the background", async () => {
  const p = await panel({ frames: [words(300)] });
  await p.summarize();
  await p.save();
  assert.match(p.elements.status.textContent, /Saved\. The summary isn’t written yet: Claude adds it to your notes in the background/);
});

test("a page that never answers ends in a message after 5 s, not a stuck Copying… with Save disabled", { timeout: 3000 }, async () => {
  const p = await panel({ stored: { title: "A post", url: PAGE, clips: [clip("c1")], note: "" }, frames: () => new Promise(() => {}), fastTimeout: true });
  await p.summarize();
  assert.match(p.elements["summarize-hint"].textContent, /didn’t answer within 5 seconds/);
  assert.equal(p.elements.save.disabled, false);
  assert.equal(p.elements.summarize.disabled, false);
});

test("a frame that never answers doesn't hold up an article in the page itself (svpg.com, Sep 28)", { timeout: 3000 }, async () => {
  const p = await panel({ frames: (target) => (target.allFrames ? new Promise(() => {}) : Promise.resolve([words(1195)])), fastTimeout: true });
  await p.summarize();
  assert.match(p.elements["summarize-hint"].textContent, /Page text added \(1195 words\)/);
});

test("frames that never answer are skipped: the page's own short text is judged, with no error", { timeout: 3000 }, async () => {
  const p = await panel({ stored: { title: "A post", url: PAGE, clips: [clip("c1")], note: "" },
    frames: (target) => (target.allFrames ? new Promise(() => {}) : Promise.resolve([words(20)])), fastTimeout: true });
  await p.summarize();
  assert.match(p.elements["summarize-hint"].textContent, /too little text/);
  assert.equal(p.elements.save.disabled, false);
});

// ---- Site access "On click" (Sep 28): Chrome holds the page read until access
// is granted, silently, so the button hung. The click must ask for access. ----

test("with Site access withheld, the click asks Chrome for access before anything else, then reads the page", async () => {
  const p = await panel({ siteAccess: false, frames: [words(300)] });
  const pending = p.summarize();
  assert.equal(p.chrome.permissions.requests, 1, "asked synchronously in the click, so Chrome shows its prompt");
  await pending;
  assert.match(p.elements["summarize-hint"].textContent, /Page text added \(300 words\)/);
});

test("if access is refused, it says why and never starts a page read that would hang", async () => {
  const p = await panel({ stored: { title: "A post", url: PAGE, clips: [clip("c1")], note: "" }, siteAccess: false, grant: false, frames: [words(300)] });
  await p.summarize();
  assert.match(p.elements["summarize-hint"].textContent, /isn’t allowed to read this site/);
  assert.equal(p.chrome.permissions.injected, 0);
  assert.equal(p.elements.save.disabled, false);
});

test("Add selection asks for access the same way", async () => {
  const p = await panel({ siteAccess: false, grant: false });
  await p.elements["add-selection"].listeners.click();
  assert.equal(p.chrome.permissions.requests, 1);
  assert.match(p.elements.status.textContent, /isn’t allowed to read this site/);
});

test("with access already granted, no prompt appears", async () => {
  const p = await panel({ frames: [words(300)] });
  await p.summarize();
  assert.equal(p.chrome.permissions.requests, 0);
});

// ---- clips left on other pages (G15): they used to be invisible, holding
// image data indefinitely ----

const rows = (p) => p.elements["elsewhere-list"].children;
const rowTitle = (r) => r.children[0].children[0].textContent;
const OTHER = "https://news.example.org/issue-12";

test("other pages with unsaved clips are listed, newest first; the current page and empty ones are not", async () => {
  const p = await panel({
    stored: { title: "A post", url: PAGE, clips: [clip("c1")], note: "" },
    others: {
      [OTHER]: { title: "Issue 12", clips: [{ ...clip("o1"), added: 5 }] },
      "https://blog.example.com/b": { title: "Newer post", clips: [{ ...clip("o2"), added: 9 }, { ...clip("o3"), added: 1 }] },
      "https://empty.example.com/": { title: "Emptied", clips: [] },
    },
  });
  assert.equal(p.elements.elsewhere.hidden, false);
  assert.equal(p.elements["elsewhere-count"].textContent, "2");
  assert.deepEqual(rows(p).map(rowTitle), ["Newer post", "Issue 12"]);
  assert.equal(rows(p)[0].children[0].children[1].textContent, "2 clips · blog.example.com");
});

test("with nothing left elsewhere, the section stays hidden", async () => {
  const p = await panel({ stored: { title: "A post", url: PAGE, clips: [clip("c1")], note: "" } });
  assert.equal(p.elements.elsewhere.hidden, true);
});

test("Clear asks once, then removes only that page's clips", async () => {
  const p = await panel({ stored: { title: "A post", url: PAGE, clips: [clip("c1")], note: "" }, others: { [OTHER]: { title: "Issue 12", clips: [clip("o1")] } } });
  const clear = rows(p)[0].children[2];
  await clear.listeners.click();
  assert.ok(p.store["capture:" + OTHER], "one click only asks");
  assert.equal(clear.textContent, "Clear clips?");
  await clear.listeners.click();
  assert.equal(p.store["capture:" + OTHER], undefined);
  assert.ok(p.store[KEY], "the current page's clips are untouched");
  await tick();
  assert.equal(p.elements.elsewhere.hidden, true);
});

test("Open switches to the page's tab if it's open, else opens it", async () => {
  const p = await panel({ others: { [OTHER]: { title: "Issue 12", clips: [clip("o1")] }, "https://b.example.com/x": { title: "B", clips: [clip("o2")] } },
    openTabs: [{ id: 7, url: OTHER + "#section-2", windowId: 1 }] });
  const byTitle = (t) => rows(p).find((r) => rowTitle(r) === t);
  await byTitle("Issue 12").children[1].listeners.click();
  assert.deepEqual(p.chrome.tabs.activated, [7]);
  await byTitle("B").children[1].listeners.click();
  assert.deepEqual(p.chrome.tabs.created, ["https://b.example.com/x"]);
});
