# Urbancrest Knowledge

The source of truth for Urbancrest Church's website AI and future digital tools.

## Mission

Every nation. Every street. One mission.

Helping people know Jesus, grow in faith, and live on mission together.

## Repository Structure

- `knowledge/` contains public-facing answer documents.
- `registry/` stores canonical structured data.
- `relationships/` maps discipleship and visitor journeys.
- `intents/` routes common questions to preferred answers.
- `schemas/` defines required content structure.
- `templates/` provides authoring templates.
- `tests/` contains retrieval and response tests.
- `manifest.yaml` lists every indexed document.

## Core Rules

1. One question. One answer. One document.
2. Use registry IDs instead of duplicating links.
3. Organize by user intent.
4. Keep answers biblical, clear, pastoral, and specific to Urbancrest.
5. Never present a confession of faith as equal to Scripture.
6. Use the term Small Groups, not Grow Groups.
7. Do not use em dashes.

## Runtime Retrieval

- `runtime/search-index.json` is the compiled retrieval file used by the website AI.
- `scripts/build_search_index.py` creates the index from public knowledge, registries, relationships, and intents.
- `registry/staff-routing.yaml` maps questions and ministries to exact Base44 staff keys.
- `registry/action-links.yaml` provides approved response links.
- Staff biographies, fun facts, photos, contact details, active status, and display order remain in Base44 Staff.
- Approved Base44 KnowledgeEntry records supplement the GitHub index at runtime.
- SearchQueryLog and UnansweredQuestion remain operational Base44 data and are never indexed as public knowledge.
