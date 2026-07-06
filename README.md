# Urbancrest Knowledge

This repository is the source of truth for Urbancrest Church's website AI search and future digital tools.

## Current Primary Use

Agentic AI search on the Urbancrest website.

## Architecture

Release 0.4.0 introduces the Urbancrest Knowledge Object Model.

The repository now includes:

- `knowledge/` for user-facing AI knowledge articles
- `registry/` for canonical structured data such as links, ministries, locations, and staff references
- `relationships/` for journey and next-step mapping
- `intents/` for user intent routing
- `schemas/` for content structure and metadata standards
- `tests/` for quality assurance prompts

## Core Rule

One question. One answer. One document.

Knowledge articles should reference registry IDs instead of duplicating URLs or contact information.
