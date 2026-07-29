# Live Event Details Update 1.4.2

This update adds a separate `details` field to live event generation when the Planning Center iCal feed exposes richer event content.

## What it reads

The sync continues to use the standard iCal `DESCRIPTION` field as the event description. It now also checks:

- `X-ALT-DESC`
- `X-PLANNING-CENTER-DESCRIPTION`
- `X-PLANNING-CENTER-DETAILS`
- `X-PCO-DESCRIPTION`
- `X-PCO-DETAILS`
- `DETAILS`
- Future public custom iCal properties containing `DETAIL`, `DESCRIPTION`, or `DESC`

Duplicate copies of the plain description are discarded.

## Generated output

When separate details are available, the sync adds:

```yaml
details: "Menu: ..."
```

to `registry/events-live.yaml` and includes a `## Details` section in the generated Markdown event article. The search index also includes the details content so the agent can answer questions such as:

- What is the menu for Wednesday Night Dinner?
- What are the details for Wednesday Night Dinner?

## Install

Copy the patch contents into the root of `urbancrest-knowledge`, preserving folders. Commit and push, then run:

**Actions → Sync Live Events → Run workflow**

In the workflow log, look for:

```text
Imported separate details for N event occurrences.
```

If the count remains zero, the current iCal feed is not exporting that field. Recreate the feed in Planning Center and enable the relevant event details when prompted. If Planning Center keeps the information only in the Church Center rich description, the next step would be Calendar API enrichment because that field is not guaranteed to appear in iCal.
