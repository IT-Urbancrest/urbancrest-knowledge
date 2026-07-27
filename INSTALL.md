# Urbancrest Live Events Release 1.4.0

Version 1.4 prevents recurring Small Group meetings from crowding major and ministry events out of the live calendar knowledge base.

## Architecture

```text
registry/events-live.yaml
knowledge/events/generated/

registry/small-groups-live.yaml
knowledge/small-groups/generated/
```

The main event registry contains major, ministry, churchwide, class, and general events.

The Small Groups registry contains recurring Small Group series. Each group is stored once with its next meeting and a limited list of future meetings.

## Install

Copy the ZIP contents into the root of `urbancrest-knowledge`, preserving folders.

Replace:

```text
.github/workflows/sync-events.yml
scripts/sync_events.py
registry/events-live.yaml
knowledge/events/upcoming-events.md
intents/calendar.yaml
AI_PERSONALITY-CALENDAR-PATCH.md
```

Add:

```text
registry/small-groups-live.yaml
registry/event-categories.yaml
registry/event-overrides.yaml
knowledge/small-groups/upcoming-small-groups.md
knowledge/small-groups/generated/.gitkeep
intents/small-groups.yaml
tests/event-priority-and-small-groups.yaml
```

Copy the updated contents of `AI_PERSONALITY-CALENDAR-PATCH.md` into your existing `AI_PERSONALITY.md`. Replace the older calendar patch section instead of adding a duplicate.

## Workflow settings

```yaml
EVENT_LOOKAHEAD_DAYS: "365"
EVENT_MAX_MAIN_EVENTS: "150"
SMALL_GROUP_MAX_SERIES: "100"
SMALL_GROUP_MAX_OCCURRENCES: "12"
```

High-priority major and ministry events are protected before lower-priority events when the main-event limit is applied.

## Default categories

| Category | Priority | Collection |
|---|---:|---|
| Major event | 100 | Main events |
| Ministry event | 80 | Main events |
| Churchwide program | 60 | Main events |
| General event | 50 | Main events |
| Class or Bible study | 40 | Main events |
| Small Group meeting | 20 | Small Groups |

Edit `registry/event-categories.yaml` to adjust keyword classification.

Use `registry/event-overrides.yaml` for exact exceptions, corrections, or promotions.

## Run

Go to:

**Actions → Sync Live Events → Run workflow**

The log should report:

```text
Wrote X main events from Y main-event candidates.
Collapsed X Small Group occurrences into Y Small Group series.
```

## Test

Ask the AI:

- What women's ministry events are coming up?
- What is the next women's ministry event?
- What major events are coming up?
- What Small Groups meet this week?
- When does [Small Group name] meet?

The October women's event should now remain in `events-live.yaml` even when the calendar contains many recurring Small Group meetings.
