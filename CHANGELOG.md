# Changelog

## 0.6.3

- Added Planning Center Calendar API enrichment to the live event sync.
- Maps iCal EventInstance IDs to Calendar API EventInstance and Event records.
- Imports the rich public event description as `details`.
- Imports public Church Center, registration, and image URLs when available.
- Pins the Calendar API version and adds secure GitHub Actions secrets.
- Adds regression tests for UID mapping, JSON:API enrichment, and duplicate removal.

## 0.6.2

- Made the weekly schedule and service-time article authoritative retrieval sources.
- Added a dedicated service-time intent.
- Added an indexed `schedule.weekly` record with Sunday times at 9:30 AM and 11:00 AM.
- Preserved authority, confidence, and answer-guidance metadata in the search index.
- Marked routine dated Sunday service occurrences as ineligible for general service-time retrieval.
- Added regression tests for regular service times and date-specific exceptions.

## 0.6.1

- Added current Global Missions Pastor vacancy and transition guidance.
- Updated Jennifer Prows routing to identify her as Missions Administrator and recommended current global missions contact.
- Separated global missions, local missions, and missions administration relationships.
- Added a focused answer for "Who oversees missions?"
- Updated retrieval indexing to retain leadership status, open-role, recommended-contact, and answer-guidance metadata.
- Added regression tests for global missions leadership and local missions routing.

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
