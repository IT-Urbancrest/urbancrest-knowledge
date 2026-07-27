# Changelog

## 1.3.0

- Added `intents/calendar.yaml` with structured date-aware retrieval rules.
- Added normalized `sort_start_utc` and `sort_end_utc` fields.
- Added `chronological_rank`.
- Added `next_for_ministries` and `next_for_audiences`.
- Made `registry/events-live.yaml` the explicit source of truth for calendar intents.
- Added punctuation normalization for curly apostrophes and quotation marks.
- Added calendar retrieval tests.
- Included the corrected GitHub Actions commit step that stages generated files before checking for changes.
