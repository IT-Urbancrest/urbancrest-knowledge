# Knowledge Object Schema

Every knowledge article should use this structure unless there is a clear reason not to.

```yaml
---
id:
version: 1.0
status: published
priority: 50

title:
summary:

category:
  - 

intent:
  primary:
  secondary:
    - 

audience:
  - 

answer_style: conversational
confidence: high

owner:
  ministry:

review:
  doctrinal:
  factual:

tags:
  - 

search_terms:
  - 

scripture:
  - 

resources:
  - 

next_steps:
  - 

related:
  - 

last_updated: 2026-07-06
---
```

## Field Notes

- `id` should be unique and stable.
- `resources` should reference registry IDs such as `church_center.connect_card`.
- `next_steps` should reference related articles or journey steps.
- `priority` helps identify the importance of the document for retrieval.
- `confidence` should be `high`, `medium`, or `pastoral`.
