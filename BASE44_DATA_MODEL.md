# Base44 Data Model Changes

This file describes website-side entities. These records remain in Base44 and are not copied into Urbancrest Knowledge.

## Staff

Keep the existing Staff entity as the source of truth for:

- biography
- fun fact
- photo
- phone
- email
- role display
- active status
- display order

Urbancrest Knowledge supplies staff routing and the exact `staffKey` only.

## KnowledgeEntry

Preserve the current fields:

- title
- category
- date
- content
- tags

Add these fields when absent:

- `summary` - text
- `search_terms` - text list
- `ministries` - text list
- `audiences` - text list
- `priority` - number, default 70
- `status` - draft or published, default draft
- `approved` - boolean, default false
- `source` - text, default base44_admin

Only records with `status = published` and `approved = true` participate in public retrieval.

## SearchQueryLog

Create this entity if it does not exist:

- question
- answer
- confidence
- staffKey
- responseTimeMs
- retrievedRecordIds
- created_at

Record every public query for analytics without delaying the visible answer.

## UnansweredQuestion

Preserve existing records and fields. Add these fields when absent:

- status - open, reviewed, or resolved
- reviewed - boolean
- resolved - boolean
- resolved_by_entry_id - relationship or text ID
- retrievedRecordIds - text list
- created_at

Create an UnansweredQuestion only when:

- the answer is missing
- the answer is `UNSURE`
- confidence is below 45
- no relevant retrieval records were found
- the answer is a soft deferral to staff

When an administrator creates a KnowledgeEntry from an unanswered question, connect the new entry through `resolved_by_entry_id` and mark the question resolved.
