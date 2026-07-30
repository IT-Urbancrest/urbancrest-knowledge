# Urbancrest Activity Retrieval Patch 0.7.1

This focused patch fixes event discovery for general availability questions and
one-character misspellings.

## What it changes

### Urbancrest Knowledge

`scripts/build_search_index.py` now gives generated event records:

- the `activity_availability` intent
- public activity aliases
- availability-style search phrases
- activity aliases in tags and structured fields

For `OPEN GYM Pickleball`, the index will include aliases such as:

- `OPEN GYM Pickleball`
- `Pickleball`
- `Pickle ball`

### Base44

The Base44 patch:

- recognizes questions such as `Does Urbancrest have ...?`
- keeps future event records eligible for those questions
- adds conservative one-character typo tolerance
- applies fuzzy scoring before candidate truncation
- deduplicates recurring occurrences

## Install

1. Copy `scripts/build_search_index.py` into the Urbancrest Knowledge repository.
2. Commit and push.
3. Run **Actions → Build Knowledge Search Index → Run workflow**.
4. Give `BASE44_ACTIVITY_RETRIEVAL_PROMPT.md` and
   `BASE44_ACTIVITY_RETRIEVAL_PATCH.md` to the Base44 agent.
5. Test both `pickleball` and `pickeball`.

The generated event Markdown file is not the primary retrieval source. The compiled
index is built from `registry/events-live.yaml`, so the search-index workflow must run
after this patch is installed.
