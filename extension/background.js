// Service worker: opens the side panel on toolbar click and adds a
// right-click "Add selection" shortcut so clips can be collected
// without the panel having focus.

chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "notes-clipper-add",
    title: "Add selection to Notes Clipper",
    contexts: ["selection"],
  });
});

// Runs inside the page: grab the selection verbatim (preserves line breaks,
// unlike info.selectionText) plus YouTube playback position if present.
function grabSelection() {
  const video = document.querySelector("video");
  return {
    text: window.getSelection().toString(),
    videoTime: video && !isNaN(video.currentTime) ? Math.floor(video.currentTime) : null,
    url: location.href,
    title: document.title,
  };
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "notes-clipper-add" || !tab?.id) return;
  let grabbed = null;
  try {
    const [result] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: grabSelection,
    });
    grabbed = result?.result;
  } catch (e) {
    // Restricted page (chrome://, Web Store); fall back to the flattened text.
  }
  const text = (grabbed?.text || info.selectionText || "").trim();
  if (!text) return;

  const pageUrl = (grabbed?.url || info.pageUrl || tab.url || "").split("#")[0];
  const key = "capture:" + pageUrl;
  const stored = await chrome.storage.local.get(key);
  const capture = stored[key] || { title: grabbed?.title || tab.title || "", url: pageUrl, clips: [], note: "" };
  // The id lets a save in progress tell this clip apart from the ones it wrote.
  capture.clips.push({ id: crypto.randomUUID(), text, videoTime: grabbed?.videoTime ?? null, added: Date.now() });
  await chrome.storage.local.set({ [key]: capture });
  chrome.action.setBadgeText({ tabId: tab.id, text: String(capture.clips.length) });
});
