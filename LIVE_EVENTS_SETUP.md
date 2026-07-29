# Live Events Setup

The live sync uses two Planning Center sources:

- The private iCal feed supplies recurring event occurrences, dates, times, and locations.
- The authenticated Calendar API supplies the rich public event description, public URLs, registration URL, and image.

The Calendar API `description` is used as the generated event's **Details** section.

## 1. Add the iCal feed secret

In GitHub, open:

**Settings → Secrets and variables → Actions → New repository secret**

Create:

```text
Name: ICAL_FEED_URL
Value: your complete Planning Center webcal:// feed URL
```

## 2. Create a Planning Center Personal Access Token

Open your Planning Center developer account and create a Personal Access Token for a user who has access to Calendar and the events being synchronized.

Planning Center will provide a `client_id` and `secret`. Keep both private.

## 3. Add the Calendar API secrets

Create these GitHub Actions repository secrets:

```text
Name: PLANNING_CENTER_APP_ID
Value: the Personal Access Token client_id
```

```text
Name: PLANNING_CENTER_SECRET
Value: the Personal Access Token secret
```

Do not commit either credential to the repository.

## 4. Run the workflow

Open:

**Actions → Sync Live Events → Run workflow**

A successful enriched run will include a log similar to:

```text
Calendar API enrichment matched 152 parsed event occurrences; imported rich details for 1.
```

The generated event registry will use:

```yaml
source: planning_center_ical+calendar_api
```

Events with rich details will include:

```yaml
details_source: planning_center_calendar_api
```

## Automatic schedule

The workflow runs every three hours at 17 minutes past the hour.

## API behavior

The API version is pinned in `.github/workflows/sync-events.yml`. The sync requests only public Calendar event fields and only the date window covered by the iCal workflow. The iCal feed remains the source for recurrence expansion.

If API credentials are absent, the workflow continues with iCal only. If credentials are present but the Calendar API returns an authentication or permissions error, the workflow fails instead of overwriting enriched records with incomplete data.

## Security

The iCal feed URL and Planning Center Personal Access Token both grant access to church data. Store them only as encrypted GitHub Actions secrets.
