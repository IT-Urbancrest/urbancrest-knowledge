# Changelog

## 0.6.0

- Added a compiled runtime search index for retrieval-first AI answers.
- Added staff identity and routing registries while keeping biographies and fun facts in Base44 Staff.
- Added David Bickers to preaching-related staff routing.
- Added ministry-to-staff relationships and approved action-link records.
- Added runtime source precedence for GitHub knowledge, Base44 Staff, and approved Base44 KnowledgeEntry records.
- Added a dedicated search-index workflow and integrated index rebuilding into the live event sync.
- Included the Small Group title-and-location consolidation fix from event sync 1.4.1.
- Added Base44 implementation and data-model migration instructions.
- Added retrieval acceptance tests.

## 1.4.0

- Split routine Small Group meetings into `small-groups-live.yaml`.
- Added one generated knowledge article per Small Group series.
- Collapsed recurring Small Group occurrences into a single series record.
- Added configurable event categories and priority levels.
- Protected major and ministry events before lower-priority events when applying limits.
- Added a 365-day default lookahead window.
- Added `event-overrides.yaml` for title- or UID-based corrections.
- Added separate Small Group retrieval rules.
- Updated the workflow to stage additions, changes, and deletions across both collections.
- Added tests for category priority, Small Group routing, and chronological selection.
