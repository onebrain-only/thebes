---
name: doc-corpus-markdown-is-barely-parsed
description: The doc renderer parses '# ' and '## ' only, and GalleryUsage matches **bold** and `code` only — anything else reaches the page literally.
metadata:
  type: project
---

`lib/src/gallery/docs/doc_page.dart:206,210` recognises `'# '` and `'## '` and nothing else.
`gallery_page_markup.dart:24` matches `**bold**` and backtick-`code` and nothing else.
**Any other markdown reaches the rendered page as literal characters.**

`_spans` has **no fallback branch** — unmatched text is appended verbatim, never an error. So the
gap is a class, not one bug. Measured across the 58 pages (D-051):

| `###` sub-headings | 181 lines, 57 files |
| bold spanning a line break | 66 spans, 43 files — no `dotAll`, so `.` cannot cross a newline |
| markdown links | 87, 33 files |
| list items | 78, 32 files |

**Links are the most serious** though not the most numerous: D-033's "a component page links to a
foundation; it never repeats it" architecture is carried entirely by links, so it is currently
inert. **Bold-across-a-break has the nastiest mechanism** — the same span renders or corrupts
depending only on where the author's editor wrapped the line, invisible to author and reviewer.

**The corpus is correct; the renderer is incomplete.** D-051(b) rules the direction: the renderer
completes to the corpus, and constraining the corpus to what renders is refused in advance.

Also: `_DocSection` (`doc_view.dart:64-72`) is a bare Column with **no gaps at all** — the `##`
label is welded to its first paragraph and prose blocks abut. The 24px air is between sections
only, from `GallerySections`.

**Why:** the corpus is authored as ordinary markdown and reviewed as prose, so it is natural to
assume list syntax, links, tables and blockquotes render. They do not.

**How to apply:** before ruling on how any markdown construct *looks*, check whether it is parsed
at all — and when you find one unhandled construct, **ask what else that same mechanism predicts
is unhandled.** I read the parser, ruled on `###`, called it "the largest defect in the corpus",
and missed three more that the same two greps already implied (D-051(a)) — the question is usually "is this rendered" before "is this styled". Reading the parser
and the markup matcher answers it in two greps. Say plainly when you have read it off the parser
rather than viewed it rendered. See [[rtl-is-asserted-but-never-rendered]].
