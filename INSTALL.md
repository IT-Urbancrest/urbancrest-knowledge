# Urbancrest Knowledge Release 0.6.0

This release adds the Urbancrest Knowledge files required for retrieval-first website AI search.

## What stays in Base44

The Staff entity remains the source of truth for biography, fun fact, photo, phone, email, role display, active status, and display order.

KnowledgeEntry, SearchQueryLog, and UnansweredQuestion remain Base44 entities.

## What is added to Urbancrest Knowledge

```text
registry/staff-routing.yaml
registry/action-links.yaml
registry/runtime-sources.yaml
relationships/ministry-staff.yaml
intents/staff.yaml
intents/action-links.yaml
scripts/build_search_index.py
scripts/requirements-index.txt
.github/workflows/build-search-index.yml
runtime/search-index.json
runtime/README.md
schemas/search-index-schema.md
tests/retrieval-index-tests.yaml
BASE44_IMPLEMENTATION_PROMPT.md
BASE44_DATA_MODEL.md
```

The release also updates:

```text
registry/staff.yaml
AI_PERSONALITY.md
manifest.yaml
README.md
CHANGELOG.md
.github/workflows/sync-events.yml
scripts/sync_events.py
registry/event-overrides.yaml
```

David Bickers includes preaching in his staff routing.

## Install the repository files

Copy the release contents into the root of the current `urbancrest-knowledge` repository, preserving folder structure. Commit and push the changes.

Do not copy the `.git` directory from an older repository backup. This release does not include one.

## Build the index

After pushing, run:

**Actions -> Build Knowledge Search Index -> Run workflow**

The workflow should commit:

```text
runtime/search-index.json
```

The live event workflow also rebuilds the index after every calendar sync.

## Update Base44

Open `BASE44_IMPLEMENTATION_PROMPT.md` and copy the prompt into the Base44 AI website agent.

The agent should preserve the public search design and staff-card behavior while replacing whole-repository prompting with local retrieval from `runtime/search-index.json`.

## Base44 entities

Follow `BASE44_DATA_MODEL.md`.

Important changes:

- Keep existing KnowledgeEntry fields.
- Add publication and retrieval metadata when absent.
- Add SearchQueryLog for all searches.
- Use UnansweredQuestion only for missing, low-confidence, or deferred answers.
- Do not wait for analytics logging before showing the answer.

## Verify

Run the tests in `tests/retrieval-index-tests.yaml` after the Base44 agent completes the website changes.

Start with:

- What time are Sunday services?
- What is your next men's ministry event?
- What Small Groups meet this week?
- Who oversees missions?
- Which pastors are involved in preaching?
- Tell me about Jennifer Prows.
