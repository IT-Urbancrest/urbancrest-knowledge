# Contributing

## Before adding content

1. Search for an existing article that already answers the question.
2. Prefer one question, one answer, one document.
3. Use YAML frontmatter and a stable unique `id`.
4. Reference registry IDs for links, ministries, staff, and locations instead of duplicating structured data.
5. Add or update retrieval tests when the new content introduces a new intent, routing rule, schedule, or policy answer.
6. Rebuild `runtime/search-index.json` after changes.

`manifest.yaml` contains repository metadata only. It is not a manually maintained document inventory.

## Review

Belief and doctrine articles require pastoral review. Operational details require factual review by the responsible ministry.

## Generated content

Do not manually edit generated live-event or Small Group articles unless the sync system explicitly supports an override. Use the appropriate registry override or source system instead.
