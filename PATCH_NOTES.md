# Urbancrest Sermon Retrieval Fix 0.9.8

This focused repository patch contains only hand-authored source/test files. It intentionally does not contain generated events, `runtime/search-index.json`, workflow files, or `scripts/build_search_index.py`.

Changes:
- Adds the official Summer on the Mount artwork URL to the sermon-series record.
- Strengthens sermon regression expectations for relative "last Sunday" lookup, complete series-member listing, fill-in-note URL inclusion, and sermon-speaker staff routing.
- Strengthens the existing general retrieval regression suite by requiring the canonical answer record to be the only selected record for the accepted natural-language regression cases.

Deployment:
1. Copy this patch over a clean, current `main` branch.
2. Commit and push these source/test files.
3. Replace the Base44 `queryKnowledgeBase` function with `queryKnowledgeBase-0.9.8.js` supplied separately.
4. Replace `ChurchAISearch.jsx` with `ChurchAISearch-0.9.8.jsx` to enable structured series artwork rendering.
5. Run Build Knowledge Search Index after the repository patch is on `main`.
