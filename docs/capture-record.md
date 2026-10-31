# Capture record (`capture/1`)

The one format every source turns into before routing: a web clip, a
handwritten scan, a kept screenshot, or a pasted link or text. Each source
keeps its own way of capturing, since a phone scanner can't run a Chrome
extension. Everything after capture is shared: one queue, one routing skill,
one check that it reached the vault.

A record is a Markdown file: a small frontmatter header, then the verbatim
content. It lives in an inbox folder with any files it carries beside it.
`watcher/validate_record.py` checks a record against this page.

```markdown
---
record: capture/1
source_type: scan
title: "Seminar: evals for agents"
source: "scan: 2026-09-28-seminar-p01.pdf"
captured: 2026-09-28 14:10
review: transcript
attachments:
  - 2026-09-28-seminar-p01.pdf
---

## Transcript

(verbatim text; unreadable words marked [illegible?], uncertain ones word[?])

## My note

(optional: why it matters, what to connect it to)
```

## Header

| Field | Required | Value |
|---|---|---|
| `record` | yes | `capture/1`, the version of this format |
| `source_type` | yes | `web`, `scan`, `screenshot` or `note` |
| `title` | yes | A JSON-style double-quoted string, so quotes and backslashes are escaped |
| `source` | yes | Where it came from; the form depends on `source_type` (below) |
| `captured` | yes | `YYYY-MM-DD HH:MM`, when it was captured |
| `attachments` | if it has files | Filenames beside the record, one per line as `  - name`. Every one must exist |
| `review` | scans only | `transcript`: a person approves the transcript before it routes |
| `category` | screenshots only | `AI`, `PM`, `DESIGN` or `CAREER` |
| `mode` | no | `summarize`: whole page or talk, so the archive gets a skim summary on top |
| `video_id` | no, web only | A YouTube id; the watcher fetches its captions |
| `written` | no, scans only | `YYYY-MM-DD`, when the page was written, if known |
| `language` | no | e.g. `en`, `ko` |

### `source` by type

| `source_type` | `source` | Content in the body |
|---|---|---|
| `web` | the page URL (`https://…`) | clips as `## Clip N` blockquotes, or `## Full page text` |
| `note` | the link's URL, or `pasted` | the verbatim text |
| `scan` | `scan: <filename>`, and that file is in `attachments` | `## Transcript` |
| `screenshot` | `photos: <uuid>` or `file: <filename>` | `## Text in the screenshot` (OCR), with the image in `attachments` |

A screenshot record must carry one of these four categories; a tool that
sorts screenshots keeps any others to itself rather than queueing them.

## Rules the rest of the pipeline relies on

- **The body is verbatim.** It is the archive's source of truth: never a
  summary, never cleaned up. Scans mark what they can't read instead of
  guessing.
- **The header decides; the body never does.** Page text can contain anything,
  including a line that looks like a header field. Only the frontmatter block is
  read for `source_type`, `video_id`, `attachments` and the rest.
- **Files travel with the record.** A record and its attachments move between
  queue states together, and `verify.sh` checks each attachment reached the
  vault archive.
- **Scans stop for review.** A record with `review: transcript` never routes
  until a person has approved its transcript.

## Web captures from before `capture/1`

The Chrome extension's captures already carry nearly all of this. The
validator reads one with `type: web-capture` and no `record` field as a `web`
record, and its `images:` list as `attachments`, so nothing about the
extension or the files already saved has to change.
