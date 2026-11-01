"""Page names for topic notes: one rule, shared by build_html.py (which writes
the pages) and build_quiz.py (which links to them), so the two can't disagree.

Topic notes are created by the router from captured pages, so a filename is
untrusted. A page name keeps letters and digits from any script, joined by
dashes, and nothing else, so it is safe in a filename, a URL and HTML. Names
that reduce to the same page, or to a page the build writes itself (quiz, map,
index), get -2, -3... in filename order, so no page overwrites another.
"""
import re

PREFIX = "handwritten-"
BUILT_IN = {"quiz", "knowledge-map", "notes-index", "search-index"}


def stem_of(fn):
    return fn[:-len("_note.md")] if fn.endswith("_note.md") else fn[:-3]


def page_names(filenames):
    """{note filename: page filename} for every *.md in the notes folder."""
    taken, out = set(BUILT_IN), {}
    for fn in sorted(filenames):
        base = re.sub(r"[\W_]+", "-", stem_of(fn).lower()).strip("-") or "note"
        name, n = base, 1
        while name in taken:
            n += 1
            name = f"{base}-{n}"
        taken.add(name)
        out[fn] = PREFIX + name + ".html"
    return out
