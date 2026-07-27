# Urbancrest Live Events Release 1.1.0

This release creates one AI-readable Markdown file per upcoming event.

Copy the contents into the root of `urbancrest-knowledge`, replacing the previous live-event files. Keep the existing `ICAL_FEED_URL` GitHub Actions secret, then run **Actions → Sync Live Events → Run workflow**.

Generated files:

```text
registry/events-live.yaml
knowledge/events/upcoming-events.md
knowledge/events/generated/<event-file>.md
```

The generated folder is rebuilt every sync, so expired, removed, and canceled events are deleted automatically. Do not manually edit files inside `knowledge/events/generated/`.

Suggested tests:

- What events are coming up?
- Tell me about [event title].
- When is [event title]?
- Where is [event title]?
- Are there any events for kids?
- What can I attend this weekend?
