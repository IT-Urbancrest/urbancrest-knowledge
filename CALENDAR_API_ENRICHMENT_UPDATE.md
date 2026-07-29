# Calendar API Enrichment Update 1.4.3

This update supplements the Planning Center iCal feed with the Planning Center Calendar API.

## Why this is needed

Planning Center exposes two public event text fields through the Calendar API:

- `summary`: plain text public summary
- `description`: rich text public description

The iCal feed can contain the plain summary without the rich description. The sync now retrieves the rich API description and writes it to the generated event's `details` field and `## Details` section.

## Install

Copy this patch into the root of `urbancrest-knowledge`, preserving folders.

Add these GitHub Actions secrets:

- `PLANNING_CENTER_APP_ID`
- `PLANNING_CENTER_SECRET`

Then run:

**Actions → Sync Live Events → Run workflow**

## Verify

Check `registry/events-live.yaml` for the Wednesday Night Dinner occurrence. It should include:

```yaml
details: |
  Menu: ...
details_source: planning_center_calendar_api
planning_center_event_id: "..."
planning_center_event_instance_id: "..."
```

The generated Markdown article should contain a `## Details` section, and `runtime/search-index.json` should include the same menu text.
