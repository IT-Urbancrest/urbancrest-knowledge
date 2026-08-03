# Urbancrest Knowledge

Public knowledge and structured retrieval data for the Urbancrest Church website assistant.

## What belongs here

- Public-facing knowledge articles in `knowledge/`
- Stable registries in `registry/`
- Retrieval intent metadata in `intents/`
- Ministry and journey relationships in `relationships/`
- Live event and Small Group sync data generated from Planning Center
- Search-index and sync scripts in `scripts/`
- Retrieval regression tests in `tests/`

## Runtime architecture

Base44 does not send this entire repository to the language model. The repository is compiled into:

```text
runtime/search-index.json
```

`queryKnowledgeBase` fetches that index, retrieves a small set of relevant records locally, applies deterministic handling for schedules, live events, directions, Local Missions, food assistance, benevolence, staff routing, and action links, then sends only the selected context to the model.

### Sources of truth

- Recurring service and ministry schedules: `registry/schedule.yaml`
- Live events: `registry/events-live.yaml`
- Small Groups: `registry/small-groups-live.yaml`
- Staff identity and routing: `registry/staff.yaml` and `registry/staff-routing.yaml`
- Staff biographies, photos, contact information, and fun facts: Base44 `Staff`
- Approved response links: `registry/action-links.yaml`
- Public knowledge: `knowledge/`

Source precedence is defined in `registry/runtime-sources.yaml`.

## Rebuild the search index

After changing knowledge, registries, intents, or relationships, run:

**Actions → Build Knowledge Search Index → Run workflow**

The live-event sync also rebuilds the index after updating calendar data.

Do not edit `runtime/search-index.json` manually.

## Live events

See `LIVE_EVENTS_SETUP.md` for Planning Center iCal and Calendar API configuration.

## Content conventions

- One question, one answer, one document when practical.
- Use YAML frontmatter on public knowledge articles.
- Use stable IDs and reference registry values instead of duplicating URLs or staff data.
- Use **Small Groups**, never Grow Groups.
- Do not use em dashes in Urbancrest-authored public copy.
- Do not publish tactical security procedures or private operational information.
