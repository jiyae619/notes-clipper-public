# Notes Clipper

Save something worth keeping, such as a passage from an article, a YouTube video
or a handwritten page, and a few minutes later it's filed into your notes by
topic, with the original kept word for word. Claude does the filing in the
background on your Mac.

Every run also rebuilds a small site from your notes that opens in any browser,
with no server:

- **Notes pages**: one tab per topic, with a table of contents, search, and a
  "🔔 What's new" pop-up saying what the last run added and where.
- **Knowledge map**: a graph of your topics and the concepts they share.
- **Flashcard quiz**: multiple-choice questions written from your own captures,
  each citing the note and source it came from.

The map and quiz start empty and grow with every capture.

## Requirements

| What | Why | How to get it |
|---|---|---|
| A Mac | The background watcher uses macOS's launchd, Keychain and folder permissions. On Windows or Linux only the Chrome extension works. | |
| Google Chrome | The clipping side panel is a Chrome extension. | [google.com/chrome](https://www.google.com/chrome/) |
| Claude Code, signed in to a Claude Pro or Max plan | Claude reads each capture and files it. It runs on **your** Claude account, so routing uses your plan's usage. | [claude.com/claude-code](https://claude.com/claude-code) |
| Xcode Command Line Tools | Builds the small launcher app macOS grants folder access to. | `xcode-select --install` |
| Python 3 and pandoc | Build the notes pages. | `brew install python pandoc` ([Homebrew](https://brew.sh)) |
| yt-dlp (optional) | Fetches YouTube captions for video captures. | `brew install yt-dlp` |
| Node (optional) | Only to run the tests. | `brew install node` |

Your notes are plain markdown files in a folder you choose. Any editor works.
If you use a markdown app that keeps notes in a folder (Obsidian, for example),
you can point Notes Clipper at that folder, but no such app is needed.

## What you fill in yourself

Nothing in this repo names a user, an email address or a machine. These are the
only places your own details go, and setup walks you through each:

| Where | What | When |
|---|---|---|
| `claude setup-token` | Signs in to **your** Claude account in the browser and prints a token. | Setup, step 3 |
| Keychain entry `notes-clipper-claude-token` | Stores that token under your macOS user name (`$USER` fills it in). No file holds it. | Setup, step 3 |
| `NOTES_VAULT` | The folder your notes live in. | Setup, step 4 (optional) |
| `Routing_map_note.md` | The topics you study. | Setup, step 5 |

No email address is needed anywhere.

## Setup

About ten minutes. Do the steps in order. `<repo>` below means the folder you
cloned into.

**1. Get the code.**

```bash
git clone https://github.com/jiyae619/notes-clipper-public.git notes-clipper
```

**2. Load the Chrome extension.**

1. Open `chrome://extensions` and switch on **Developer mode** (top right).
2. Click **Load unpacked** and choose `<repo>/extension`.
3. Pin **Notes Clipper** to the toolbar. Clicking it opens the side panel.
4. In `chrome://settings/downloads`, keep the download location as your
   `Downloads` folder and keep **Ask where to save each file** off. The
   extension saves captures into `~/Downloads/notes-inbox/`.

**3. Give the watcher its own Claude sign-in.** The CLI's normal sign-in can
lapse when you don't use it, so the watcher uses a long-lived token kept in your
login Keychain. In Terminal:

```bash
claude setup-token
```

```bash
security add-generic-password -U -a "$USER" -s notes-clipper-claude-token -w
```

The first signs in through your browser and prints a token. The second asks you
to paste it.

**4. Install the watcher.** Run this yourself. It starts a background agent that
edits your notes without asking each time.

```bash
bash <repo>/watcher/install.sh
```

Your notes go in `~/Documents/Notes` unless you name another folder. To use an
existing notes folder, name it the first time; later re-installs remember it:

```bash
NOTES_VAULT="$HOME/Documents/My notes" bash <repo>/watcher/install.sh
```

The first install creates a `Handwritten/` folder inside your notes folder (see
[Your notes folder](#your-notes-folder)), sets up the page builder and starts the
watcher. It never overwrites a file that already exists, so re-running it is safe.

When macOS asks whether **Notes Clipper Runner** may access your Downloads and
Documents folders, click **Allow**. Without that, every run is blocked. If your
notes folder is somewhere else, macOS asks about that folder instead.

**5. Tell it your topics.** Open `Handwritten/notes/Routing_map_note.md` in your
notes folder and add a row per topic, for example:

```
| Personal_finance_note.md | Budgeting, saving, investing, taxes |
```

The first capture that fits a topic creates that topic's note. Anything that
fits no row goes into `General_note.md`, marked so you can decide where it
belongs.

**6. Try it.** Open any article, select a paragraph, click **Add selection from
page**, then **Save to notes**. Within a few minutes your notes index opens in
the browser. If it doesn't, see [Troubleshooting](#troubleshooting).

## Daily use

**Capturing**, in the Chrome side panel:

- **Add selection from page**, or right-click → *Add selection to Notes
  Clipper*. Add as many as you like; they're kept per page until you save.
- **🖼 Add image**, or click into the panel and press ⌘V to paste a screenshot.
  Claude reads images too, so a diagram is summarized like text.
- **Add whole page** for long newsletters and videos. You get a short summary on
  top, with the full text kept below it. On YouTube it fetches the captions.
- **Paste text instead** for anything the panel can't reach, like a newsletter
  in a mail app.
- **Save to notes** sends it off. The panel also lists other pages that still
  hold unsaved clips.

**Handwritten pages:** scan a page with your phone (Files or Notes → Scan
Documents) and get the file into `Handwritten/inbox/` in your notes folder, by
iCloud Drive, AirDrop or any other way. Claude transcribes it, then waits for
you:

1. A review page opens, with words Claude was unsure of highlighted next to the
   scan. Fix anything that's wrong.
2. Click **Download corrections**. That download is your approval: the next run
   files the page like any other capture.

PDF, JPEG, PNG and HEIC are accepted. Nothing from a scan is filed until you
approve it.

**Reading:** open `handwritten-notes-index.html` in your pages folder
(`~/Documents/Notes Pages` unless you changed it). The map and quiz are linked
from its top bar. The watcher opens the index after each run that filed
something.

**Filing right away:** a save is picked up within a minute or two. To run it
now and get a report on each capture, type `/route-capture` in Claude Code.
`install.sh` installs this command.

## Settings

`install.sh` saves every setting to `~/.config/notes-clipper/watcher.env`. To
change one, pass it to `install.sh` once, as in step 4.

| Setting | What it is | Default |
|---|---|---|
| `NOTES_VAULT` | Your notes folder | `~/Documents/Notes` |
| `NOTES_OUT` | Where the HTML pages go | `~/Documents/Notes Pages` |
| `NOTES_ROUTING_MAP` | The note in `Handwritten/notes/` listing your topics | `Routing_map_note.md` |
| `NOTES_REFS` | The page builder and its data: quiz bank, map concepts, What's new history | `~/.config/notes-clipper/renderer` |
| `CLAUDE_BIN` | The `claude` program the watcher runs | found through your shell |

Fixed locations: new captures land in `~/Downloads/notes-inbox/`; processed ones
and the log go to `~/Downloads/notes-inbox-processed/`.

## Your notes folder

```
<NOTES_VAULT>/
  Handwritten/
    inbox/      drop scanned pages here
    archive/    every original, kept word for word, with its images
    notes/      your topic notes, plus Routing_map_note.md and General_note.md
```

Everything Notes Clipper writes goes under `Handwritten/`, whatever the source.
The name comes from the project's first use (scanned paper notes). The rest of
your folder is left alone.

Each topic note is a markdown file named `<Topic>_note.md`. Notes cite their
sources and embed images as `![[filename]]`, which most markdown note apps
display.

## Troubleshooting

See what the watcher is doing:

```bash
tail -f ~/Downloads/notes-inbox-processed/watcher.log
```

- **Nothing happens after saving.** Check that the capture is in
  `~/Downloads/notes-inbox/`. If not, check Chrome's download settings (step 2).
- **macOS notification: "Can't read …"**. Notes Clipper Runner lacks folder
  access. Open System Settings → Privacy & Security → Files and Folders, and
  allow it.
- **"isn't set up" or a signed-out alert.** Re-run step 3, then `install.sh`.
  Also re-run `install.sh` after upgrading Node, which can move `claude`.
- **A capture failed.** It's retried on the next runs. After 3 tries you get a
  "gave up" notification and it stays in `notes-inbox-processed/failed/`.

Stop the watcher (captures then wait in the inbox until you install again):

```bash
bash <repo>/watcher/uninstall.sh
```

## How it works

```
Chrome side panel ──▶ ~/Downloads/notes-inbox/      web clips, images, whole pages, videos
phone scan ─────────▶ <notes>/Handwritten/inbox/    handwritten pages
  │  each becomes a capture record (docs/capture-record.md)
  │  launchd starts a run when a capture lands, and every 15 min
  ▼
queue (~/Downloads/notes-inbox-processed/)
  │  scans only: transcribed → needs-review/ → you approve on the review page
  ▼
router: watcher/route-capture.md    original → archive/, summary → topic notes,
                                    quiz questions + map concepts as proposals
  ▼
watcher/verify.sh                   did it really reach the notes? → done/ | failed/ | skipped/
  ▼
renderer/                           rebuilds the notes pages, map and quiz
```

**What the background run may do.** It reads web pages, which can contain text
written to manipulate an AI, so it gets only what filing needs: it can read and
write files in your notes folder and the processed folder, and nothing else. No
shell, no web access, none of your other Claude connectors (mail, chat, browser).
It can't touch the quiz bank or the page builder: it writes quiz questions and
map concepts as proposals, and `watcher/merge_proposals.py` checks every field
before applying them. Its instructions forbid deleting or overwriting anything
already in your notes.

**Done means done.** Claude's own exit status doesn't decide whether a capture
was filed. `verify.sh` checks the notes folder: an archive file must name the
capture and keep its source, its images must be in the archive, and a topic note
must cite it. Anything less goes to `failed/` and is retried.

**Folder access.** launchd doesn't run the script directly. It starts **Notes
Clipper Runner**, a small app `install.sh` builds from `watcher/runner/`,
because macOS grants folder access per app. `install.sh` rebuilds it only when
its source changes, since a rebuild needs the access granted again.

**Other sources.** Anything that writes a capture record into
`~/Downloads/notes-inbox/` is filed the same way. The format is in
[docs/capture-record.md](docs/capture-record.md).

## Files

- `extension/`: the Chrome side panel (Manifest V3).
- `watcher/process_inbox.sh`: one run: claims captures, fetches video captions,
  runs Claude with the routing instructions, sorts each capture by what
  `verify.sh` finds, applies proposals, rebuilds the pages.
- `watcher/route-capture.md`: the routing instructions, shared by the background
  run and `/route-capture` (`skills/route-capture/`).
- `watcher/transcribe-scan.md`, `apply_corrections.py`, `review_page.py`: scan
  transcription and your approval of it.
- `watcher/merge_proposals.py`: checks and applies quiz and map proposals.
- `watcher/verify.sh`: decides whether a capture reached the notes.
- `watcher/validate_record.py`, `docs/capture-record.md`: the capture record
  format and its checker.
- `watcher/install.sh`, `uninstall.sh`, `setup_paths.sh`: install, remove, and
  work out the settings. `com.notes-clipper.watcher.plist` is the launchd
  template; `runner/` is the launcher app's source.
- `renderer/`: the page builder (`build_html.py` for notes, index and map;
  `build_quiz.py`; `build_review.py`) and `mermaid.min.js` for diagrams
  ([Mermaid](https://github.com/mermaid-js/mermaid), MIT).
  `install.sh` links the scripts into `NOTES_REFS`, where their data lives.
- `starter-vault/`: the `Handwritten/` layout a new notes folder starts from.
- `tests/`: see below.

To tune the pages, edit the lists at the top of `renderer/build_html.py`: `PREF`
(tab order), `GLOSSARY` (concepts the map always looks for) and `WORD` (words to
keep upper-case in titles).

## Tests

```bash
bash tests/run.sh
```

The watcher tests run `process_inbox.sh` against sample captures in a throwaway
home folder, with stand-ins for Claude, yt-dlp, the Keychain and notifications,
so they never touch your inbox, token, usage or screen. One test runs the real
page builder end to end, so it needs pandoc. The extension tests load the side
panel's code in a sandbox and check the markdown it writes.

## Known limits

- Some pages can't be read by the extension (`chrome://` pages, the Chrome Web
  Store, some PDFs). Use **Paste text instead**.
- A video with no captions isn't filed, since the captions are its only content.
  It goes to `skipped/` and the log says `NOT ROUTED`. Paste a transcript instead.
- Removing a capture from the processed folder doesn't remove it from your notes.
- Unsaved image clips are held in the browser until you save. Many large ones
  make the panel slow, so save or clear them.

## License

MIT. See [LICENSE](LICENSE).
