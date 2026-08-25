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

## 1.0 runtime contract

This repository is the authoritative public knowledge layer for the Urbancrest website assistant. Base44 does not send the entire repository to the language model. The repository is compiled into:

```text
runtime/search-index.json
```

That compiled index is the runtime boundary between the knowledge repository and `queryKnowledgeBase`. Do not edit `runtime/search-index.json` manually.

`queryKnowledgeBase` retrieves a small set of relevant records locally and uses deterministic handling where exact church-owned behavior is required. Deterministic routes include critical safety responses, doctrine, recurring schedules and service times, sermons, directions, staff ownership, current events, Small Groups, and other structured live-data lookups. The language model is used only after deterministic routing and record selection when a generated response is appropriate.

### Versioning

The knowledge architecture and the Base44 query runtime are versioned independently.

- Knowledge architecture: `1.0.0`
- Current Base44 `queryKnowledgeBase` runtime: `0.10.50`

The knowledge architecture version changes when the repository contract, source-of-truth structure, compiled-index schema, precedence rules, or other platform-level behavior changes. Query-runtime versions may advance independently for routing, conversational context, deterministic answer handling, regression coverage, and other application-layer improvements that do not change the knowledge architecture contract.

### Sources of truth

- Recurring service and ministry schedules: `registry/schedule.yaml`
- Live events: `registry/events-live.yaml`
- Small Groups: `registry/small-groups-live.yaml`
- Staff identity and routing: `registry/staff.yaml` and `registry/staff-routing.yaml`
- Ministry-to-staff ownership and contact routing: `relationships/ministry-staff.yaml`
- Staff biographies, photos, contact information, and fun facts: Base44 `Staff`
- Approved response links: `registry/action-links.yaml`
- Public knowledge: `knowledge/`

Source precedence and live-data freshness policy are defined in `registry/runtime-sources.yaml`.

### Informational and transactional boundaries

Urbancrest knowledge and the website assistant are the informational layer. They should answer questions directly from approved church-owned sources.

Church Center is the transactional layer for actions such as registration, giving, baptism interest, Small Groups, and serving interest. Approved Church Center destinations are maintained in the registries rather than reconstructed by the runtime.

### Live-data freshness

Current event and Small Group answers use independent source heartbeats compiled from the `generated_at` value in their live registries. The freshness threshold is currently eight hours.

Freshness is based on the live source registry heartbeat, not the search index `generated_at` timestamp. If a live source exceeds its configured freshness threshold, the runtime does not present its records as current. It returns the approved fallback destination instead. Evergreen knowledge remains available, while stale live-event enrichment is omitted.

## Validation and regression protection

Knowledge changes are protected by the permanent build pipeline:

1. Build `runtime/search-index.json`.
2. Finalize the generated index.
3. Run `scripts/validate_search_index.py` against the index and regression declarations.
4. Commit the compiled index only after validation passes.

The Base44 app has a separate permanent CI gate that validates runtime invariants, executes the actual production `queryKnowledgeBase` routing source through the executable regression harness, and builds the application. This protects deterministic routing behavior rather than relying only on source-marker checks.

## Rebuild the search index

After changing knowledge, registries, intents, or relationships, run:

**Actions → Build Knowledge Search Index → Run workflow**

The live-event sync also rebuilds and validates the index after updating calendar data.

## Live events

See `LIVE_EVENTS_SETUP.md` for Planning Center iCal and Calendar API configuration.

## Content conventions

- One question, one answer, one document when practical.
- Use YAML frontmatter on public knowledge articles.
- Use stable IDs and reference registry values instead of duplicating URLs or staff data.
- Use **Small Groups**, never Grow Groups.
- Do not use em dashes in Urbancrest-authored public copy.
- Do not publish tactical security procedures or private operational information.
