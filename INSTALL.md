# Urbancrest Live Events Release 1.0.0

Copy the contents of this release into the root of the `urbancrest-knowledge` repository.

The final repository paths must be:

```text
.github/workflows/sync-events.yml
scripts/sync_events.py
scripts/requirements-events.txt
registry/events-live.yaml
knowledge/events/upcoming-events.md
```

## GitHub secret

In the repository, go to:

**Settings → Secrets and variables → Actions → New repository secret**

Create:

```text
Name: ICAL_FEED_URL
Value: the complete Planning Center webcal:// feed URL
```

## First run

Go to:

**Actions → Sync Live Events → Run workflow**

The workflow runs automatically every three hours after that.

## Workflow permissions

If the workflow cannot commit generated files, go to:

**Settings → Actions → General → Workflow permissions**

Select **Read and write permissions** and save.
