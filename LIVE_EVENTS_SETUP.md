# Live Events Setup

This update synchronizes the Planning Center iCal feed into two AI-readable files:

- `registry/events-live.yaml`
- `knowledge/events/upcoming-events.md`

## 1. Add the iCal URL as a GitHub secret

In the GitHub repository, open:

**Settings → Secrets and variables → Actions → New repository secret**

Create this secret:

```text
Name: ICAL_FEED_URL
Value: your complete webcal:// Planning Center feed URL
```

Do not commit the private feed URL directly to the repository.

## 2. Add the files

Copy this update into the root of the repository while preserving the folder structure.

## 3. Run the first sync

Open:

**Actions → Sync Live Events → Run workflow**

The workflow will download the feed, generate the event files, and commit them back to the repository.

## Automatic schedule

The workflow runs every three hours at 17 minutes past the hour.

## Generated event window

By default, the sync includes:

- Upcoming events for the next 120 days
- A maximum of 75 events
- Times converted to `America/New_York`
- Recurring event instances
- Confirmed and tentative events
- No canceled or expired events

These limits can be changed in `.github/workflows/sync-events.yml`.

## Security note

A Planning Center iCal URL functions like a private access token. Keep it in GitHub Actions secrets. If the URL is ever exposed publicly, regenerate the feed URL in Planning Center.
