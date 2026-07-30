# Base44 Implementation Prompt: Activity Availability and Typo Tolerance

Update the existing Urbancrest `queryKnowledgeBase` function to correctly answer
questions such as:

- Does Urbancrest have pickleball?
- Does Urbancrest have pickeball?
- Can I play pickle ball at Urbancrest?

Before editing, inspect the current implementation. Preserve all existing behavior,
including:

- retrieval from `runtime/search-index.json`
- approved Base44 KnowledgeEntry retrieval
- current calendar and date filtering
- Calendar API-enriched event details
- Small Group handling
- service-time authority rules
- staff routing and Staff cards
- action links
- Markdown presentation
- analytics and unanswered-question behavior
- the existing JSON response shape

Use the supplied `BASE44_ACTIVITY_RETRIEVAL_PATCH.md` as the implementation
specification.

The important requirements are:

1. Detect activity-availability phrasing such as `does Urbancrest have`, `do you
   offer`, `is there`, and `can I play`.
2. Keep future event records eligible for those questions even when no calendar word
   appears.
3. Add conservative typo tolerance for tokens of at least five characters, with a
   maximum edit distance of one.
4. Apply activity and fuzzy scoring before the best 6–8 records are selected.
5. Match against title, activity aliases, search terms, and tags.
6. Dedupe recurring occurrences and use the earliest future match unless all dates are
   requested.
7. Do not describe a calendar activity as a permanent ministry unless the knowledge
   base explicitly says that it is one.
8. Keep the response as Markdown inside the current JSON response shape.

Run every acceptance test listed in `BASE44_ACTIVITY_RETRIEVAL_PATCH.md` and report
the changed website files and results.
