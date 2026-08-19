# Ministry Knowledge Structure

Each canonical ministry should live in its own folder. The canonical entry point is always `overview.md`.

## Standard layout

```text
knowledge/ministries/
  <ministry-slug>/
    overview.md
    faq/
      <question>.md
    programs/
      <evergreen-program>.md
```

Examples:

```text
men/
  overview.md
  faq/
  programs/

women/
  overview.md
  faq/

kids/
  overview.md
  faq/

students/
  overview.md
  faq/
```

## File paths are not record identity

The frontmatter `id` is the stable record identity. Moving a file must **not** change its canonical ID merely because its path changes.

For example:

```yaml
# knowledge/ministries/men/overview.md
id: ministries.mens_ministry
```

## Overview documents

Every canonical overview should contain:

- stable `id`
- `version`
- `status: published`
- `priority`
- visitor-facing `title`
- concise `summary`
- `category: [ministries]`
- `intent.primary: ministry_info`
- ministry-specific secondary intents
- audience
- `owner.ministry`
- focused tags and natural search terms
- canonical `ministries`
- approved resources
- related record IDs when useful
- `last_updated`

The body should explain:

1. what the ministry is,
2. who it serves,
3. its purpose and vision,
4. its primary pathways or activities.

Do not put internal routing instructions, selection rules, or staff-description warnings in public article bodies.

## FAQs

Use `faq/` for direct question-and-answer records. One file should answer one question.

Keep the ministry's canonical intent as a secondary intent when the FAQ has a more specific primary intent such as `small_groups`, `serving`, `registration`, or `ministry_contact`.

## Programs

Use `programs/` for evergreen ministry-specific programs that are more substantial than a FAQ but are not the ministry overview itself.

Do not hardcode current event dates in these files. Live dates belong in the live event registry.

## Leadership

Leadership ownership, vacancies, and current points of contact belong primarily in `relationships/ministry-staff.yaml` and structured frontmatter. Broad ministry overview bodies should focus on the ministry itself.

Questions such as `Who leads Kids Ministry?` should use the ownership relationship rather than relying on prose in the overview.

## Events

Broad ministry answers may combine the canonical overview with deterministic live-event enrichment.

Specific event/date questions should use live event records directly.

## Repository hygiene

- No `.DS_Store` files.
- No duplicate frontmatter IDs.
- No canonical overview Markdown files directly under `knowledge/ministries/` other than this README.
- Preserve IDs when moving files.
