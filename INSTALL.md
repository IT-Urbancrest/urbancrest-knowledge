# Urbancrest Live Events Release 1.3.0

Version 1.3 adds date-aware retrieval for calendar intents.

## What this fixes

When several recurring occurrences have nearly identical text, semantic retrieval may rank a later occurrence above the nearest one. Version 1.3 makes the live registry authoritative for calendar questions and adds normalized UTC sort fields.

## Install

Copy the ZIP contents into the root of `urbancrest-knowledge`, preserving the folder structure.

Replace:

```text
.github/workflows/sync-events.yml
scripts/sync_events.py
registry/events-live.yaml
knowledge/events/upcoming-events.md
```

Add:

```text
intents/calendar.yaml
tests/calendar-intents.yaml
AI_PERSONALITY-CALENDAR-PATCH.md
```

The requirements file is unchanged but is included for completeness.

## Required agent instruction

Copy the contents of `AI_PERSONALITY-CALENDAR-PATCH.md` into the existing `AI_PERSONALITY.md`.

Do not replace the rest of `AI_PERSONALITY.md`.

Make sure the AI runtime can retrieve:

```text
intents/calendar.yaml
registry/events-live.yaml
knowledge/events/generated/
```

## Run the sync

Go to:

**Actions → Sync Live Events → Run workflow**

The generated registry and event articles will now include:

```yaml
sort_start_utc: "2026-08-01T12:00:00Z"
sort_end_utc: "2026-08-01T13:30:00Z"
chronological_rank: 1
next_for_ministries: [men]
next_for_audiences: [men]
```

The exact values will depend on the event.

## Test

Ask:

> What is your next men's ministry event?

The agent should:

1. Load `registry/events-live.yaml`.
2. Filter for `men`.
3. Exclude past events.
4. Sort by `sort_start_utc` ascending.
5. Select the first result.
6. Read that event's `knowledge_file` for details.

Also test:

- When is the next Men's Breakfast?
- What student events are coming up?
- What is happening this weekend?
- What events are happening this month?

## Important

Semantic relevance still determines whether an event matches the user's topic. Chronological sorting determines which matching future occurrence is next.
