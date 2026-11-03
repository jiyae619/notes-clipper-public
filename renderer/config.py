"""Your own settings for the page builder, kept beside its data (quiz bank,
map concepts) as renderer-config.json, so the build scripts themselves stay
shared and update with the repo. Every key is optional:

  vault            your notes folder, when NOTES_VAULT isn't set (e.g. a hook)
  out              where the pages go, when NOTES_OUT isn't set
  tab_order        note filenames to show first, in this order
  map_terms        concepts the knowledge map always looks for
  reference_pdfs   PDFs in archive/ that are documents, not your scans, shown
                   under their own names instead of "Notebook scan N"
  display_names    {note stem: name} for the quiz, e.g. {"PM_UX": "PM / UX"}
  review_topic_order  topics listed first on the scan review page

A missing or malformed file, or a value of the wrong type, is ignored: the
pages still build with the defaults.
"""
import json, os

_TYPES = {"vault": str, "out": str, "tab_order": list, "map_terms": list, "reference_pdfs": list,
          "display_names": dict, "review_topic_order": list}


def load(data_dir):
    try:
        raw = json.load(open(os.path.join(data_dir, "renderer-config.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    conf = {}
    for k, t in _TYPES.items():
        v = raw.get(k)
        if not isinstance(v, t):
            continue
        if t is list:
            v = [x for x in v if isinstance(x, str)]
        elif t is dict:
            v = {a: b for a, b in v.items() if isinstance(a, str) and isinstance(b, str)}
        conf[k] = v
    return conf


def path(env_name, conf, key, default):
    """A folder setting: the environment first, then the config, then the default."""
    return os.path.expanduser(os.environ.get(env_name) or conf.get(key) or default)
