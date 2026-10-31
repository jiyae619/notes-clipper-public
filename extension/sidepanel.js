// Side panel: collects clips for the active page — text (selection or paste)
// and images (upload or ⌘V paste). Nothing is written until "Save to notes" —
// then one markdown file (clips + source link + note), plus one file per image
// clip beside it, is downloaded to ~/Downloads/notes-inbox/, where the launchd
// watcher picks the batch up and routes it into your notes.
//
// A clip is a text clip ({text, videoTime}) or an image clip ({image}); the
// context-menu path in background.js only ever produces text clips.

const el = (id) => document.getElementById(id);

let currentUrl = null;   // canonical key for the active page (no #fragment)
let currentTitle = "";
let saveTimer = null;
let saving = false;      // true while Save writes files: a second save waits
let reading = false;     // true while "Add whole page" copies the text: Save waits for it

// Every clip gets an id, so a save can later remove exactly the clips it wrote.
const newClipId = () => crypto.randomUUID();

function storageKey(url) {
  return "capture:" + url;
}

async function getCapture(url) {
  const key = storageKey(url);
  const stored = await chrome.storage.local.get(key);
  return stored[key] || { title: currentTitle, url, clips: [], note: "" };
}

async function setCapture(url, capture) {
  await chrome.storage.local.set({ [storageKey(url)]: capture });
}

// ---------- active tab tracking ----------

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab || null;
}

// Chrome lets you limit an extension's Site access ("On click", or only some
// sites). On a site it isn't allowed, scripting.executeScript doesn't fail:
// Chrome holds the call until access is granted, and nothing in this panel
// shows that, so Add whole page hung until its timeout and looked dead (Sep 28:
// Site access was "On click"). So the panel knows whether it may read the
// current site, and a click that needs to asks Chrome first.
let siteAllowed = true;
async function refreshSiteAccess() {
  siteAllowed = !currentUrl || (await chrome.permissions.contains({ origins: [new URL(currentUrl).origin + "/*"] }));
}
chrome.permissions.onAdded.addListener(refreshSiteAccess);
chrome.permissions.onRemoved.addListener(refreshSiteAccess);
// Call first thing in a click, before any await: Chrome only shows its Allow
// prompt for a request made while handling the click. Asks for every site,
// which the manifest declares, so it's one prompt, not one per site.
function askSiteAccess() {
  if (siteAllowed) return Promise.resolve(true);
  return chrome.permissions.request({ origins: ["<all_urls>"] }).then((ok) => (siteAllowed = ok), () => false);
}
const NO_SITE_ACCESS = "Notes Clipper isn’t allowed to read this site. Click again and choose Allow, or set Site access to “On all sites” in chrome://extensions → Notes Clipper → Details.";

async function refreshFromActiveTab() {
  const tab = await getActiveTab();
  if (!tab || !tab.url || !/^https?:/.test(tab.url)) {
    currentUrl = null;
    siteAllowed = true;
    el("page-title").textContent = "This page can’t be clipped";
    el("page-url").textContent = "Open an article, video, or newsletter tab.";
    render({ clips: [], note: "" });
    renderElsewhere();
    return;
  }
  currentUrl = tab.url.split("#")[0];
  await refreshSiteAccess();
  currentTitle = tab.title || currentUrl;
  el("page-title").textContent = currentTitle;
  el("page-url").textContent = currentUrl;
  render(await getCapture(currentUrl));
  renderElsewhere();
}

chrome.tabs.onActivated.addListener(refreshFromActiveTab);
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (tab.active && (changeInfo.url || changeInfo.title || changeInfo.status === "complete")) {
    refreshFromActiveTab();
  }
});

// Live-update when the context menu (background.js) adds a clip.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== "local") return;
  if (currentUrl && changes[storageKey(currentUrl)]) {
    const updated = changes[storageKey(currentUrl)].newValue;
    if (updated) render(updated);
  }
  if (Object.keys(changes).some((k) => k.startsWith("capture:") && k !== storageKey(currentUrl))) renderElsewhere();
});

// ---------- clips left on other pages ----------
// Clips wait in storage per page until you save them, so ones left on a page
// you moved on from were invisible, image data included, indefinitely (G15).
// They're listed here, newest first, to open or clear.

async function renderElsewhere() {
  const all = await chrome.storage.local.get(null);
  const pages = Object.entries(all)
    .filter(([k, v]) => k.startsWith("capture:") && k !== storageKey(currentUrl) && v?.clips?.length)
    .map(([k, v]) => ({ key: k, url: v.url || k.slice("capture:".length), title: v.title, clips: v.clips }))
    .sort((a, b) => lastAdded(b) - lastAdded(a));
  el("elsewhere").hidden = pages.length === 0;
  el("elsewhere-count").textContent = String(pages.length);
  el("elsewhere-list").replaceChildren(...pages.map(elsewhereRow));
}

const lastAdded = (page) => Math.max(0, ...page.clips.map((c) => c.added || 0));

function elsewhereRow(page) {
  const row = document.createElement("div");
  row.className = "elsewhere-row";
  const info = document.createElement("div");
  info.className = "elsewhere-info";
  const title = document.createElement("div");
  title.className = "elsewhere-title";
  title.textContent = page.title || page.url;
  title.title = page.url;
  const meta = document.createElement("div");
  meta.className = "elsewhere-meta";
  let host = page.url;
  try { host = new URL(page.url).hostname.replace(/^www\./, ""); } catch {}
  meta.textContent = `${page.clips.length} clip${page.clips.length === 1 ? "" : "s"} · ${host}`;
  info.append(title, meta);

  const open = document.createElement("button");
  open.className = "ghost";
  open.textContent = "Open";
  open.addEventListener("click", () => openPage(page.url));

  // Clearing clips you can't see is easy to regret: the first click asks, and
  // the question goes away after a few seconds.
  const clear = document.createElement("button");
  clear.className = "ghost";
  clear.textContent = "Clear";
  let armed = null;
  clear.addEventListener("click", async () => {
    if (!armed) {
      clear.textContent = "Clear clips?";
      clear.classList.add("danger");
      armed = setTimeout(() => { armed = null; clear.textContent = "Clear"; clear.classList.remove("danger"); }, 3000);
      return;
    }
    clearTimeout(armed);
    await chrome.storage.local.remove(page.key);
    renderElsewhere();
  });

  row.append(info, open, clear);
  return row;
}

// Switch to the page's tab if it's open, else open it in a new tab.
async function openPage(url) {
  const tabs = await chrome.tabs.query({});
  const tab = tabs.find((t) => (t.url || "").split("#")[0] === url);
  if (tab) {
    await chrome.tabs.update(tab.id, { active: true });
    if (tab.windowId != null) chrome.windows?.update(tab.windowId, { focused: true });
  } else {
    await chrome.tabs.create({ url });
  }
}

// ---------- rendering ----------

function fmtTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = String(seconds % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function render(capture) {
  const list = el("clip-list");
  list.textContent = "";
  capture.clips.forEach((clip, i) => {
    const card = document.createElement("div");
    card.className = clip.kind === "page" ? "clip clip-page" : "clip";

    const label = document.createElement("span");
    if (clip.image) {
      const img = document.createElement("img");
      img.className = "clip-img";
      img.src = clip.image.dataUrl;
      img.alt = clip.image.name || "pasted image";
      img.title = clip.image.name || "pasted image";
      card.appendChild(img);
      label.textContent = `Clip ${i + 1} · image`;
    } else {
      const text = document.createElement("div");
      text.className = "clip-text";
      // A page grab can be 200k chars — never put that in the DOM.
      // A page grab is shown as a three-line preview, so its line breaks would
      // only waste those lines.
      text.textContent = clip.kind === "page" ? clip.text.slice(0, 400).replace(/\s+/g, " ") : clip.text;
      card.appendChild(text);
      if (clip.kind === "page") {
        const words = clip.text.split(/\s+/).length;
        label.textContent = capture.videoId
          ? "Whole video · transcript fetched after save"
          : `Whole page · ${words} words · to be summarized`;
      } else {
        label.textContent = clip.videoTime != null ? `Clip ${i + 1} · at ${fmtTime(clip.videoTime)}` : `Clip ${i + 1}`;
      }
    }

    const meta = document.createElement("div");
    meta.className = "clip-meta";
    const remove = document.createElement("button");
    remove.className = "remove";
    remove.textContent = "Remove";
    remove.addEventListener("click", async () => {
      const cap = await getCapture(currentUrl);
      cap.clips.splice(i, 1);
      await setCapture(currentUrl, cap);
      render(cap);
    });
    meta.append(label, remove);
    card.appendChild(meta);
    list.appendChild(card);
  });

  el("clip-count").textContent = String(capture.clips.length);
  el("empty-hint").style.display = capture.clips.length ? "none" : "block";
  el("save").disabled = capture.clips.length === 0 || !currentUrl || saving || reading;
  updateBadge(capture.clips.length);
  if (document.activeElement !== el("my-note")) {
    el("my-note").value = capture.note || "";
  }
}

// One place sets the toolbar badge, so adding, removing, clearing and saving
// all show the same count as the panel.
async function updateBadge(n) {
  const tab = await getActiveTab();
  if (tab?.id) chrome.action.setBadgeText({ tabId: tab.id, text: n ? String(n) : "" });
}

// ---------- adding clips ----------

// Runs inside the page (must be self-contained).
function grabSelection() {
  const video = document.querySelector("video");
  return {
    text: window.getSelection().toString(),
    videoTime: video && !isNaN(video.currentTime) ? Math.floor(video.currentTime) : null,
  };
}

async function addClip(text, videoTime) {
  text = (text || "").trim();
  if (!text || !currentUrl) return false;
  const capture = await getCapture(currentUrl);
  capture.title = currentTitle;
  capture.clips.push({ id: newClipId(), text, videoTime: videoTime ?? null, added: Date.now() });
  await setCapture(currentUrl, capture);
  render(capture);
  return true;
}

el("add-selection").addEventListener("click", async () => {
  const allowed = askSiteAccess();
  const tab = await getActiveTab();
  if (!tab?.id || !currentUrl) return;
  if (!(await allowed)) { setStatus(NO_SITE_ACCESS, "err"); return; }
  try {
    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: grabSelection,
    });
    const grabbed = result?.result;
    if (!grabbed?.text?.trim()) {
      setStatus("Nothing selected — highlight text on the page first.", "err");
      return;
    }
    await addClip(grabbed.text, grabbed.videoTime);
    setStatus("Clip added.");
  } catch (e) {
    setStatus("Can’t read this page (restricted). Use “Paste text instead”.", "err");
  }
});

el("add-paste").addEventListener("click", async () => {
  const added = await addClip(el("paste-area").value, null);
  if (added) {
    el("paste-area").value = "";
    setStatus("Pasted text added.");
  }
});

// ---------- adding image clips ----------

const IMAGE_EXT = {
  "image/png": "png",
  "image/jpeg": "jpg",
  "image/gif": "gif",
  "image/webp": "webp",
  "image/avif": "avif",
  "image/svg+xml": "svg",
};

// Held as data URLs in storage until save, so keep a single image sane in size
// (unlimitedStorage lifts the quota, but a 20 MB paste helps nobody downstream).
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

function extFor(image) {
  return (
    IMAGE_EXT[image.mime] ||
    image.name?.match(/\.([a-z0-9]+)$/i)?.[1].toLowerCase() ||
    "png"
  );
}

function readAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(reader.error || new Error("could not read file"));
    reader.readAsDataURL(file);
  });
}

// fromPaste: clipboard images arrive named "image.png", which is noise in the
// saved markdown — only a real upload's filename is worth recording.
async function addImageFiles(fileList, fromPaste) {
  if (!currentUrl) {
    setStatus("Open an article, video, or newsletter tab first.", "err");
    return;
  }
  const images = [...fileList].filter((f) => f.type.startsWith("image/"));
  if (!images.length) {
    setStatus("That wasn’t an image.", "err");
    return;
  }

  const capture = await getCapture(currentUrl);
  capture.title = currentTitle;
  let added = 0;
  let skipped = 0;
  for (const file of images) {
    if (file.size > MAX_IMAGE_BYTES) { skipped++; continue; }
    capture.clips.push({
      id: newClipId(),
      image: {
        dataUrl: await readAsDataUrl(file),
        mime: file.type,
        name: fromPaste ? "" : file.name || "",
      },
      added: Date.now(),
    });
    added++;
  }

  if (added) {
    await setCapture(currentUrl, capture);
    render(capture);
  }
  const imgs = (n) => `${n} image${n === 1 ? "" : "s"}`;
  if (skipped) {
    setStatus(`${imgs(added)} added — ${skipped} skipped (over 10 MB).`, added ? "" : "err");
  } else {
    setStatus(`${imgs(added)} added.`);
  }
}

el("add-image").addEventListener("click", () => el("image-file").click());

el("image-file").addEventListener("change", async (e) => {
  await addImageFiles(e.target.files, false);
  e.target.value = "";  // so the same file can be picked again
});

// ⌘V anywhere in the panel. Text pastes fall through to the textareas untouched.
document.addEventListener("paste", (e) => {
  const files = [...(e.clipboardData?.items || [])]
    .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
    .map((item) => item.getAsFile())
    .filter(Boolean);
  if (!files.length) return;
  e.preventDefault();
  addImageFiles(files, true);
});

el("clear-all").addEventListener("click", async () => {
  if (!currentUrl) return;
  await chrome.storage.local.remove(storageKey(currentUrl));
  render({ clips: [], note: "" });
  setStatus("Cleared.");
});

el("my-note").addEventListener("input", () => {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    if (!currentUrl) return;
    const capture = await getCapture(currentUrl);
    capture.note = el("my-note").value;
    await setCapture(currentUrl, capture);
  }, 300);
});

// ---------- summarize mode ----------
// A "summarize" capture is the opposite of a clip capture: instead of the exact
// words you chose, it takes the whole page. The pipeline still archives it
// verbatim — same as any clip — and additionally prepends a short skim
// summary on top of the full text. Used for newsletters and videos, where
// hand-picking quotes isn't practical.
//
// Deliberately dumb here: the panel only grabs text. Transcript fetching needs
// yt-dlp, so a video capture just records the id and lets the watcher do it.

function extractReadableText() {
  const drop = "script,style,noscript,nav,footer,header,aside,form,iframe,svg,button";
  const root =
    document.querySelector("article") ||
    document.querySelector("main") ||
    document.querySelector('[role="main"]') ||
    document.body;
  const clone = root.cloneNode(true);
  clone.querySelectorAll(drop).forEach((n) => n.remove());

  // innerText is *rendered* text, and a detached node isn't rendered — so on a
  // bare clone it silently degrades to textContent: every block boundary is
  // lost ("...at the identity layerWhat's the privilege...") and the source's
  // own indentation is left behind as whitespace-only lines. Park the clone
  // off-screen so it lays out for real, then read it. Not display:none or
  // visibility:hidden — those count as "not rendered" too and put us straight
  // back on textContent.
  const host = document.createElement("div");
  host.style.cssText = "position:absolute;left:-99999px;top:0;width:800px";
  host.appendChild(clone);
  document.body.appendChild(host);
  try {
    return host.innerText.replace(/\n{3,}/g, "\n\n").trim().slice(0, 200000);
  } finally {
    host.remove();
  }
}

// The one YouTube id parser, shared by summarize and timestamp links: watch,
// mobile and music hosts, youtu.be short links, and /shorts/, /live/ and
// /embed/ paths. Anything else, including look-alike hosts, is not a video.
function videoIdOf(pageUrl) {
  try {
    const u = new URL(pageUrl);
    const host = u.hostname.replace(/^(www|m|music)\./, "");
    if (host === "youtu.be") return u.pathname.split("/")[1] || null;
    if (host !== "youtube.com") return null;
    if (u.pathname === "/watch") return u.searchParams.get("v");
    return u.pathname.match(/^\/(?:shorts|live|embed)\/([\w-]+)/)?.[1] || null;
  } catch (e) { /* not parseable */ }
  return null;
}

// Summarize's feedback shows right under its button as well as in the footer,
// and every way the click can end says so: it used to look dead when the page
// took seconds to read, or when its result landed below the fold.
const summarizeHint = el("summarize-hint").textContent;
let summarizeTimer = null;
function sayUnderSummarize(msg, cls) {
  const h = el("summarize-hint");
  h.textContent = msg;
  h.className = "hint-inline " + (cls || "");
  setStatus(msg, cls);
  clearTimeout(summarizeTimer);
  if (cls) summarizeTimer = setTimeout(() => { h.textContent = summarizeHint; h.className = "hint-inline"; }, 8000);
}

el("summarize").addEventListener("click", async () => {
  const allowed = askSiteAccess();
  if (!currentUrl) {
    sayUnderSummarize("Open an article, video or newsletter tab first.", "err");
    return;
  }
  const tab = await getActiveTab();
  if (!tab?.id) {
    sayUnderSummarize("Couldn’t find this page’s tab. Click on the page, then try again.", "err");
    return;
  }
  if (!(await allowed)) {
    sayUnderSummarize(NO_SITE_ACCESS, "err");
    return;
  }
  const vid = videoIdOf(currentUrl);
  // Save waits too: saving mid-copy would send the capture without the page.
  reading = true;
  el("summarize").disabled = el("save").disabled = true;
  sayUnderSummarize(vid ? "Adding the video…" : "Copying the page text…");
  try {
    let text = "";
    if (!vid) {
      // The page itself first: that's where almost every article is, and it
      // answers in milliseconds. Asking every frame at once made Chrome wait
      // for all of them, and on svpg.com one form frame never answered, so a
      // 1,195-word article in the page timed out (Sep 28). Only a page with
      // almost no text of its own (a newsletter reader showing the issue in a
      // frame) is worth the frames, and they get 3 s: whichever don't answer
      // are skipped. injectImmediately: don't wait for the page to finish
      // loading its ads.
      const read = (allFrames, ms) => Promise.race([
        chrome.scripting.executeScript({ target: { tabId: tab.id, allFrames }, func: extractReadableText, injectImmediately: true }),
        new Promise((resolve) => setTimeout(() => resolve(null), ms)),
      ]);
      const longest = (results) => results.map((r) => (r?.result || "").trim()).sort((a, b) => b.length - a.length)[0] || "";
      const page = await read(false, 5000);
      if (!page) throw new Error("the page didn’t answer within 5 seconds. Reload it and try again, or select the text and use Add selection");
      text = longest(page);
      if (text.split(/\s+/).length < 80) text = longest([...page, ...((await read(true, 3000)) || [])]);
      if (text.split(/\s+/).length < 80) {
        sayUnderSummarize("This page has too little text to summarize. Select the parts you want and use Add selection instead.", "err");
        return;
      }
    }
    const capture = await getCapture(currentUrl);
    capture.mode = "summarize";
    if (vid) capture.videoId = vid;
    // Replace any prior page grab; clips you picked by hand are kept.
    capture.clips = capture.clips.filter((c) => c.kind !== "page");
    capture.clips.push(
      vid
        ? { id: newClipId(), kind: "page", text: "[video — the watcher fetches the transcript with yt-dlp]" }
        : { id: newClipId(), kind: "page", text }
    );
    await setCapture(currentUrl, capture);
    render(capture);
    // Nothing is summarized yet, and the message must not suggest otherwise:
    // the summary is written by the watcher, after Save.
    sayUnderSummarize(vid
      ? "✓ Video added. Nothing is summarized yet: click Save to notes, then the transcript is fetched and summarized in the background."
      : `✓ Page text added (${text.split(/\s+/).length} words). Nothing is summarized yet: click Save to notes to send it.`, "ok");
  } catch (e) {
    sayUnderSummarize("Can’t read this page: " + (e?.message || e), "err");
  } finally {
    reading = false;
    el("summarize").disabled = false;
    if (currentUrl) render(await getCapture(currentUrl));  // re-enables Save
  }
});

// ---------- save: compose markdown + download ----------

function ytTimestampLink(pageUrl, seconds) {
  const id = videoIdOf(pageUrl);
  return id ? `https://youtu.be/${id}?t=${seconds}` : null;
}

function buildMarkdown(capture) {
  const now = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const stamp = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`;
  const hostname = new URL(capture.url).hostname.replace(/^www\./, "");

  const lines = [
    "---",
    "type: web-capture",
    // A JSON string is a valid YAML double-quoted string, with quotes and
    // backslashes escaped, so the title survives exactly as written.
    `title: ${JSON.stringify(capture.title)}`,
    `source: "${capture.url}"`,
    `site: ${hostname}`,
    `captured: ${stamp}`,
  ];

  // The routing agent branches on this: "summarize" adds a skim summary on
  // top of the verbatim full-page text (which is still archived as-is).
  // Gated on the page clip still being present: removing it cancels summarize
  // mode, since without the page clip there's nothing to add a summary to.
  if (capture.clips.some((c) => c.kind === "page")) {
    if (capture.mode === "summarize") lines.push("mode: summarize");
    if (capture.videoId) lines.push(`video_id: ${capture.videoId}`);
  }

  // Named up front so the routing agent knows which sibling files belong to
  // this capture without parsing the body.
  const imageFiles = capture.clips.filter((c) => c.image).map((c) => c.file);
  if (imageFiles.length) {
    lines.push("images:");
    imageFiles.forEach((f) => lines.push(`  - ${f}`));
  }

  lines.push(
    "---",
    "",
    `# ${capture.title}`,
    "",
    `Source: [${hostname}](${capture.url})`,
    "",
  );

  capture.clips.forEach((clip, i) => {
    if (clip.kind === "page") {
      lines.push("## Full page text", "", clip.text, "");
      return;
    }
    if (clip.image) {
      // ![[...]] embeds resolve by filename, so this links up once the routing
      // agent copies the file into Handwritten/archive/.
      lines.push(`## Clip ${i + 1} — image`, "", `![[${clip.file}]]`, "");
      if (clip.image.name) lines.push(`*from ${clip.image.name}*`, "");
      return;
    }
    let heading = `## Clip ${i + 1}`;
    if (clip.videoTime != null) {
      const link = ytTimestampLink(capture.url, clip.videoTime);
      const t = fmtTime(clip.videoTime);
      heading += link ? ` — [${t}](${link})` : ` — at ${t}`;
    }
    lines.push(heading, "");
    clip.text.split("\n").forEach((l) => lines.push("> " + l));
    lines.push("");
  });

  if (capture.note?.trim()) {
    lines.push("## My note", "", capture.note.trim(), "");
  }

  return lines.join("\n");
}

// Filename-safe, but keeps letters in any script: accents are dropped
// (café -> cafe), Korean and Japanese are kept, the rest becomes "-".
function slugify(title) {
  return (
    title
      .normalize("NFKD").replace(/[\u0300-\u036f]/g, "").normalize("NFC")
      .toLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 50) || "capture"
  );
}

// chrome.downloads.download() resolves when a download *starts*. The watcher
// routes any *.md it finds, so every image a capture references must be fully
// on disk before its markdown lands — wait for "complete" rather than hoping.
function downloadAndWait(options, timeoutMs = 15000) {
  return new Promise((resolve, reject) => {
    chrome.downloads.download(options, (id) => {
      if (chrome.runtime.lastError || id == null) {
        reject(new Error(chrome.runtime.lastError?.message || "download rejected"));
        return;
      }
      let timer = null;
      const finish = (err) => {
        clearTimeout(timer);
        chrome.downloads.onChanged.removeListener(onChanged);
        err ? reject(err) : resolve(id);
      };
      const onChanged = (delta) => {
        if (delta.id !== id) return;
        if (delta.state?.current === "complete") finish(null);
        else if (delta.state?.current === "interrupted") finish(new Error(delta.error?.current || "interrupted"));
      };
      timer = setTimeout(() => finish(new Error("download timed out")), timeoutMs);
      chrome.downloads.onChanged.addListener(onChanged);
      // A local data:/blob: download can finish before the listener attaches.
      chrome.downloads.search({ id }, (items) => {
        const item = items?.[0];
        if (item?.state === "complete") finish(null);
        else if (item?.state === "interrupted") finish(new Error(item.error || "interrupted"));
      });
    });
  });
}

el("save").addEventListener("click", async () => {
  // Lock before the first await: a double-click otherwise starts two saves of
  // the same clips, and the watcher would route both.
  if (saving || reading || !currentUrl) return;
  saving = true;
  el("save").disabled = true;
  const url = currentUrl;
  const blobUrls = [];
  try {
    const capture = await getCapture(url);
    if (!capture.clips.length) return;
    capture.note = el("my-note").value;

    const now = new Date();
    const pad = (n) => String(n).padStart(2, "0");
    // Seconds are load-bearing: image files share this stem, and two saves of the
    // same page within one minute would otherwise collide — uniquify would rename
    // the images apart from the markdown that references them.
    const stem = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}-${slugify(capture.title)}-${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`;

    let imageCount = 0;
    capture.clips.forEach((clip) => {
      if (clip.image) clip.file = `${stem}-img${++imageCount}.${extFor(clip.image)}`;
    });

    // Images first, markdown last — the watcher routes any *.md it finds, so the
    // files it references must already be waiting beside it. If an image fails,
    // the .md is never written: nothing routes and the clips stay put.
    for (const clip of capture.clips) {
      if (!clip.image) continue;
      const blobUrl = URL.createObjectURL(await (await fetch(clip.image.dataUrl)).blob());
      blobUrls.push(blobUrl);
      await downloadAndWait({
        url: blobUrl,
        filename: "notes-inbox/" + clip.file,
        saveAs: false,
        conflictAction: "uniquify",
      });
    }

    // A Blob, like the images. A data: URL is capped at 2 MB, and a long page in
    // Korean (3 bytes a character, 9 once URL-encoded) comes close to that.
    const mdUrl = URL.createObjectURL(new Blob([buildMarkdown(capture)], { type: "text/markdown;charset=utf-8" }));
    blobUrls.push(mdUrl);
    await downloadAndWait({
      url: mdUrl,
      filename: "notes-inbox/" + stem + ".md",
      saveAs: false,
      conflictAction: "uniquify",
    });

    // Remove only what was saved. A clip added while the files were being
    // written (say, from the right-click menu) isn't in them, so it stays.
    const saved = new Set(capture.clips.map((c) => c.id));
    const latest = await getCapture(url);
    const rest = latest.clips.filter((c) => c.id && !saved.has(c.id));
    if (rest.length) {
      await setCapture(url, { ...latest, clips: rest, note: latest.note === capture.note ? "" : latest.note });
    } else {
      await chrome.storage.local.remove(storageKey(url));
    }
    const images = imageCount ? ` (${imageCount} image${imageCount > 1 ? "s" : ""})` : "";
    const n = capture.clips.length;
    // Saving is instant; the summary and filing happen later, in the watcher.
    // Say so plainly, and keep it on screen: this is the one message that
    // tells you it's safe to close the panel.
    const later = "Claude adds it to your notes in the background, usually within a few minutes. You can close this panel.";
    const summarized = capture.mode === "summarize" && capture.clips.some((c) => c.kind === "page");
    setStatus(summarized
      ? `✓ Saved. The summary isn’t written yet: ${later}`
      : `✓ Saved ${n} clip${n === 1 ? "" : "s"}${images}. ${later}`, "ok", { keep: true });
  } catch (e) {
    setStatus("Save failed: " + (e?.message || e), "err");  // storage untouched: the clips survive
  } finally {
    saving = false;
    blobUrls.forEach(URL.revokeObjectURL);
    if (url === currentUrl) render(await getCapture(url));  // re-enables Save
  }
});

// ---------- misc ----------

let statusTimer = null;
function setStatus(msg, cls, { keep = false } = {}) {
  const s = el("status");
  s.textContent = msg;
  s.className = "status " + (cls || "");
  clearTimeout(statusTimer);
  if (!keep) statusTimer = setTimeout(() => { s.textContent = ""; s.className = "status"; }, 6000);
}

refreshFromActiveTab();
