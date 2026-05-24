# Medium Posting Guide

Everything you need to post the article on Medium in 3 minutes.

## Files

- `ARTICLE_FOR_MEDIUM.md` - Cleaned-up markdown (TOC removed, anchors stripped, mermaid replaced with image placeholders)
- `diagrams/diagram_1.png` - ORM stack (7 layers)
- `diagrams/diagram_2.png` - Raw stack (2 layers)
- `diagrams/diagram_3.png` - Connection architecture
- `diagrams/diagram_4.png` - Decision flowchart

## Steps

1. Open https://medium.com/new-story
2. Open `ARTICLE_FOR_MEDIUM.md` in any text editor, select all, copy
3. Paste into Medium editor body
4. The first H1 ("Your ORM is the bottleneck") will auto-become the title. If not, move it.
5. For each `![Diagram N](diagrams/diagram_N.png)` placeholder in the text:
   - Click on that line in Medium
   - Use the `+` button on the left margin to insert an image
   - Upload the corresponding PNG from `diagrams/`
   - Optionally caption: "Diagram 1: ORM stack — 7 layers per row" etc.

## Diagram positions in the article

| Placeholder | File | Context |
|------------|------|---------|
| Diagram 1 | `diagram_1.png` | After "Every row through SQLAlchemy goes through this:" |
| Diagram 2 | `diagram_2.png` | After "Raw `executemany` does this:" |
| Diagram 3 | `diagram_3.png` | Under "Connection architecture" |
| Diagram 4 | `diagram_4.png` | Under "When to throw the ORM out" |

## Medium-specific cleanup after paste

- Tables render in Medium's native format. They look OK but narrow tables may need column reordering.
- Code blocks render correctly with syntax highlighting (Medium auto-detects language).
- Block quotes (`>`) work.
- Inline code (backticks) works.
- All external links work.

## Tags to add when publishing

Suggested tags (Medium allows 5):
- SQLite
- Python
- Performance
- Database
- Benchmarks

## Subtitle suggestion

"What 9.4 hours and 230 million rows taught me about where the time actually goes."

## Publishing checklist

- [ ] Title: "Your ORM is the bottleneck"
- [ ] Subtitle filled in
- [ ] 4 diagrams uploaded
- [ ] First image set as feature image (Medium prompts for this)
- [ ] 5 tags added
- [ ] Canonical URL set to GitHub article (for SEO if you also publish there): `https://github.com/TanayK07/sqlite-orm-bench/blob/main/ARTICLE.md`
- [ ] Preview the post once
- [ ] Publish
