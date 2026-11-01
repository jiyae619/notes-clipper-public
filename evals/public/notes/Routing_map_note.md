---
title: "Routing map"
status: consolidated
tags: [routing-map]
---

# Routing map

The router reads this note before filing each capture. It decides which topic
note a capture's summary goes into. Edit it to match what you study: one row
per topic, with a few words on what belongs there.

| Topic note | What goes there |
|---|---|
| General_note.md | Anything that fits no other topic yet |
| Personal_finance_note.md | Budgeting, saving, investing, debt |
| Cooking_note.md | Cooking techniques, recipes, food science |
| Learning_to_code_note.md | Programming concepts, tools and practice |

<!-- Example rows. Copy one above the line and edit it:
| Personal_finance_note.md | Budgeting, saving, investing, taxes |
| Cooking_note.md | Techniques, recipes, food science |
-->

## Rules for the router

- File each capture into the topic note whose row fits best. One capture can
  go into more than one note when it covers more than one topic.
- If a row's note doesn't exist yet, create it in Handwritten/notes/ under
  that exact filename, with a `title:` in its frontmatter, a `# Title`
  heading and a `## Sources` section.
- If nothing fits, use General_note.md and flag it with
  `> [!todo] routing check`, so you can decide whether it needs its own topic.
