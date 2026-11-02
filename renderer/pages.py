"""Page names for topic notes: one rule, shared by build_html.py (which writes
the pages) and build_quiz.py (which links to them), so the two can't disagree.

Topic notes are created by the router from captured pages, so a filename is
untrusted. A page name keeps letters and digits from any script, joined by
dashes, and nothing else, so it is safe in a filename, a URL and HTML. Names
that reduce to the same page, or to a page the build writes itself (quiz, map,
index, help), get -2, -3...

A note keeps its page for good: names already given out are recorded in
pages.json (beside the quiz bank) and never move to another note, even when a
new note sorts ahead of it or the old one is deleted. Bookmarks and links in
pages already open stay right.
"""
import json, os, re

PREFIX = "handwritten-"
BUILT_IN = {"quiz", "knowledge-map", "notes-index", "search-index", "help"}


def stem_of(fn):
    return fn[:-len("_note.md")] if fn.endswith("_note.md") else fn[:-3]


def page_names(filenames, state_dir, save=False):
    """{note filename: page filename} for every *.md in the notes folder.
    save=True records new names; build_html.py saves, build_quiz.py (which runs
    first, on the same notes) only reads, and gets the same answer."""
    path = os.path.join(state_dir, "pages.json")
    try:
        given = json.load(open(path, encoding="utf-8"))
        # A name the build now writes itself (a page added later, like help) is
        # taken back: that note gets a new name rather than overwrite the page.
        given = {k: v for k, v in given.items() if isinstance(k, str) and isinstance(v, str) and v not in BUILT_IN}
    except (OSError, ValueError, AttributeError):
        given = {}
    taken, out = set(BUILT_IN) | set(given.values()), {}
    for fn in sorted(filenames):
        if fn in given:
            out[fn] = PREFIX + given[fn] + ".html"
            continue
        base = re.sub(r"[\W_]+", "-", stem_of(fn).lower()).strip("-") or "note"
        name, n = base, 1
        while name in taken:
            n += 1
            name = f"{base}-{n}"
        taken.add(name)
        given[fn] = name
        out[fn] = PREFIX + name + ".html"
    if save:
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(given, fh, ensure_ascii=False, indent=1)
        os.replace(path + ".tmp", path)
    return out
