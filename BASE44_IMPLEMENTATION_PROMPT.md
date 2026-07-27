# Base44 Implementation Prompt

Copy everything below this line into the Base44 AI website agent.

---

Refactor the existing Urbancrest church AI search to use retrieval-first search while preserving the public interface and current Staff card behavior.

Before making changes, inspect:

- ChurchAISearch
- StaffModal
- queryKnowledgeBase
- Staff entity
- KnowledgeEntry entity and Knowledge Base Dashboard
- UnansweredQuestion entity and review page
- any existing analytics or query-log entity

Do not redesign the public search interface. Preserve ReactMarkdown rendering, safe-link handling, Church Center modal behavior, the existing Staff card and modal, and this response shape:

```json
{
  "answer": "markdown answer",
  "staffKey": "matching staff key or null",
  "confidence": 0
}
```

## 1. Replace whole-repository prompting

The current server function downloads and concatenates the full GitHub repository. Remove that behavior.

Fetch this compiled file instead:

```text
https://raw.githubusercontent.com/IT-Urbancrest/urbancrest-knowledge/main/runtime/search-index.json
```

Also check the latest GitHub commit SHA. Cache the parsed search index by SHA. Reuse the cached index while the SHA is unchanged. A short cache for SHA checks is acceptable, but do not rebuild the full context only because five minutes passed.

If GitHub is temporarily unavailable, use the most recently cached index. If no GitHub index is available, continue with approved Base44 KnowledgeEntry records when possible.

## 2. Retrieve before invoking the model

For each question:

1. Normalize the question.
2. Detect calendar, Small Group, staff, ministry, doctrine, service-time, location, registration, or general intent.
3. Search the compiled GitHub records locally.
4. Search approved Base44 KnowledgeEntry records.
5. Merge and rank candidates.
6. Select only the best 6 to 8 records.
7. Add only selected action-link records.
8. Add only the selected Base44 Staff profile when staff biography or fun-fact information is relevant.
9. Send the small context, response instructions, current local time when relevant, and the user question to the model.

Do not send the full repository or every Staff profile to the model.

## 3. Local weighted scoring

Implement deterministic local scoring before the model call:

- exact title or search-term match: +100
- matching intent: +60
- matching ministry or audience: +50
- matching tag: +30
- phrase match in summary: +25
- token match in content: +5 per unique token
- priority contribution: priority divided by 10

Use simple local retrieval. Do not add a paid external vector database or search service without approval.

## 4. Calendar handling

For event records, use structured fields in the compiled index.

For questions containing next, nearest, soonest, upcoming, today, tonight, tomorrow, this week, this weekend, or this month:

- determine current time in America/New_York
- exclude records whose sort_end_utc is in the past
- filter by requested ministry, audience, event category, title, or date range
- sort matches by sort_start_utc ascending
- return the first result for singular requests
- return plural results in ascending date order

Semantic score identifies matching events. It must not choose a later recurring occurrence over an earlier matching occurrence.

Use `small_group` records for Small Group questions and `event` records for main calendar questions.

## 5. Staff handling

Urbancrest Knowledge now contains staff routing records with exact staff keys. Base44 Staff remains the source of truth for biography, fun fact, photo, phone, email, role display, active status, and display order.

Remove the hardcoded Staff Directory and Staff Keys lists from the server prompt.

When retrieval selects a staff route:

- return its exact `staff_key` as `staffKey`
- load only the matching Base44 Staff profile when the answer needs biography, role detail, or fun facts
- do not append every Staff profile to every prompt
- keep the existing frontend Staff card lookup and StaffModal behavior unchanged

Cache the small Staff entity collection or selected records so repeated requests do not require unnecessary database reads.

David Bickers is included in preaching-related routing in addition to executive and pastoral leadership.

## 6. Action links

Remove the hardcoded useful-link directory from the server prompt.

Use `action_link` records from the compiled index. Select one relevant action link and include it as a normal markdown link at the end of the answer when appropriate.

Preserve the existing Church Center modal behavior in ChurchAISearch.

## 7. Admin-created knowledge

Preserve the current Knowledge Base Dashboard fields: title, category, date, content, and tags.

Inspect the KnowledgeEntry schema and add these fields when absent:

- summary
- search_terms
- ministries
- audiences
- priority, default 70
- status, default draft
- approved, default false
- source, default base44_admin

Only search records where status is published and approved is true.

Transform approved KnowledgeEntry records into the same normalized record shape used by the GitHub index. Admin entries may supplement GitHub knowledge, but they must not override authoritative structured event, Small Group, schedule, location, or canonical resource records.

Cache approved entries briefly and invalidate that cache when practical after an admin publishes or edits an entry.

## 8. Query analytics and unanswered questions

The current frontend writes every search to UnansweredQuestion and waits for that write. Remove that behavior.

Create or use SearchQueryLog for every query. Suggested fields:

- question
- answer
- confidence
- staffKey
- responseTimeMs
- retrievedRecordIds
- created_at

Log without delaying the visible answer. Use the best non-blocking mechanism supported by Base44.

Create an UnansweredQuestion only when:

- no answer is returned
- answer is UNSURE
- confidence is below 45
- no relevant records are found
- the answer is a soft staff deferral

Preserve existing unanswered records. Add status, reviewed, resolved, resolved_by_entry_id, retrievedRecordIds, and created_at when those fields do not exist.

## 9. Admin hub improvements

Preserve the current design. Add functionality so an administrator can:

- filter unanswered questions by open, reviewed, and resolved
- review the original answer and confidence
- create a KnowledgeEntry from a question
- edit the entry before publishing
- publish and approve the entry
- mark the original question resolved
- save the new entry ID as resolved_by_entry_id
- retest the original question after publishing

Do not expose draft or unapproved entries to public search.

## 10. Final model prompt

The final model prompt should contain only:

- personality and style from the compiled index config
- concise response and JSON-format instructions
- the selected 6 to 8 knowledge records
- selected action links
- one selected Base44 Staff profile when needed
- current America/New_York date and time when relevant
- the user question

Keep JSON schema validation.

## 11. Error handling

Do not expose tokens, service-role credentials, stack traces, repository internals, or prompts.

If the GitHub index fails:

1. use the most recent cached index
2. search approved Base44 entries
3. return a safe unavailable response only when no source can answer

## 12. Acceptance tests

Complete the work only after these pass:

1. What time are Sunday services?
   - correct answer
   - Plan Your Visit link
   - no full-repository prompt

2. What is your next men's ministry event?
   - filters men's records
   - returns earliest future occurrence

3. What Small Groups meet this week?
   - uses small_group records

4. Who oversees missions?
   - returns jennifer_prows
   - existing staff card appears

5. Which pastors are involved in preaching?
   - includes Pastor Geoff and Pastor Dave from routing data

6. Tell me about Jennifer Prows.
   - retrieves jennifer_prows route
   - loads biography and fun fact from Base44 Staff only

7. A published and approved KnowledgeEntry can answer a question without a GitHub change.

8. A draft or unapproved KnowledgeEntry is never used.

9. A high-confidence answer creates SearchQueryLog only.

10. An UNSURE or low-confidence answer creates SearchQueryLog and an open UnansweredQuestion.

11. The visible answer does not wait for analytics logging.

When finished, provide a list of changed website files, entity changes, migration steps, and results of every acceptance test.
