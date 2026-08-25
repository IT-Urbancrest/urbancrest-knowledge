# Changelog

## Post-1.0 Base44 query runtime improvements

The knowledge architecture remains `1.0.0`. The following changes were made in the independently versioned Base44 `queryKnowledgeBase` runtime and its permanent regression coverage.

### 0.10.50

- Added broad staff fun-fact routing for natural questions about hobbies, interests, free time, spare time, and what a staff member likes to do for fun.
- Prevented broad fun-fact questions such as `What does he do for fun?` from falling through to the biography route.
- Preserved targeted fun-fact extraction for specific questions such as whether a staff member likes a particular food, activity, team, or interest.
- Expanded multi-turn staff regression coverage to verify broad and targeted profile-detail questions remain on the same canonical staff subject and do not require the language model.

### 0.10.49

- Made short-lived session conversation context resilient to blocked out-of-scope side branches.
- Preserved the last trusted canonical subject after an out-of-scope request so the user can resume the prior Urbancrest topic.
- Added referential named-event follow-up routing and canonical event pinning so generic phrases such as `the conference` cannot drift to a different event.
- Added a four-turn regression proving that an out-of-scope interruption does not break a subsequent Women’s Conference follow-up.
- Added prompt-content regression assertions so authoritative event details can be verified even when the executable harness mocks the final language-model answer.

### 0.10.48

- Added Phase 1 session conversation context with a 30-minute inactivity TTL.
- Stored only one trusted canonical subject in browser `sessionStorage`; no conversation transcript or history is stored or sent.
- Added backend context revalidation against current authoritative records before context can influence routing.
- Added context-aware response caching and explicit Clear behavior.
- Added permanent multi-turn regressions for staff pronouns, named-event follow-ups, scope protection, and critical-safety precedence.

### 0.10.47

- Improved targeted staff fun-fact answers so a specific profile-detail question returns the smallest relevant sentence or clause instead of the entire fun-fact field.
- Added permanent regression coverage for focused Skyline/Coney Bowl extraction while excluding unrelated hobbies and sports details.

### 0.10.46

- Added deterministic Base44 Staff profile routing for biographies, fun facts, and other published profile details.
- Made Base44 `Staff` the authoritative source for staff biographies, fun facts, photos, phone, email, and active/display status while GitHub registries remain the source for stable identity and routing.
- Added no-guess behavior when a requested personal detail is absent from the published staff profile.
- Added regression coverage for Senior Pastor profile resolution and named staff fun-fact questions.

### 0.10.45

- Added an institutional-role guard preventing users from assigning the assistant a fabricated Urbancrest role or using user-supplied premises to create new official doctrine, policy, identity, or institutional positions.
- Added permanent regression coverage for declarative role assignment and invented institutional-belief prompts.

### 0.10.44

- Added a deterministic scope firewall before index retrieval for unrelated translation, roleplay, coding, homework, creative-use, and general-trivia requests.
- Added a fixed product-identity response for blocked requests and a second-stage no-record guard to prevent the runtime from becoming a general-purpose assistant.
- Preserved critical safety handling ahead of the scope firewall.

### 0.10.43

- Added deterministic shorthand location routing for natural variants such as `Where r u at?` so location questions resolve to the canonical Urbancrest directions record instead of general retrieval.

### 0.10.42

- Added event hero images for single named Planning Center Registration event answers when an approved event image is present.
- Kept broad event and ministry lists image-free and preserved existing sermon-series artwork behavior.

### 0.10.41

- Added named-event precedence so event queries such as `women's conference` select the specific event instead of being captured by a broad ministry overview.
- Added regression coverage requiring the Women’s Conference event record and excluding the Women’s Ministry overview for that query.

## 1.0.0

- Stabilized the retrieval-first architecture across the GitHub knowledge repository and the Base44 `queryKnowledgeBase` runtime.
- Migrated recurring schedule compilation to the authoritative schema 2.1 registry and added individual activity and ministry schedule records.
- Preserved structured live-event metadata including all-day state, registration availability and status, capacity, source metadata, and public-listing state.
- Added executable routing regressions that run the actual production `entry.ts` handler against the current search index and fixed-time synthetic calendar fixtures.
- Added deterministic regression coverage for doctrine, sermons, schedules, ministry routing, staff ownership, directions, live calendar boundaries, unmatched event queries, and critical safety short-circuiting.
- Fixed activity-availability false positives so generic words such as `upcoming` and `events` cannot qualify unrelated live records.
- Added consistent event-year formatting plus conservative no-end event handling, including a six-hour timed-event grace window and local-day handling for all-day events.
- Added live-data freshness contracts for calendar and Small Group sources using the sync registries' independent `generated_at` heartbeats and an eight-hour stale threshold.
- Added deterministic stale-data responses that refuse potentially outdated live details and route users to the approved Events page or Small Groups directory.
- Added SHA-pinned search-index fetching, retryable Turnstile loading, aligned Base44 SDK versions, and server-side question-length protection while preserving critical safety precedence.
- Added deeper long-article retrieval through bounded supplemental search terms without expanding prompt content, and eliminated timestamp-only index commits when semantic output is unchanged.
- Expanded permanent build, index, fixture, runtime-invariant, and executable routing validation so future changes fail before publishing when core behavior regresses.

## 0.9.7

- Revised all nine structured sermon records using the published Subsplash fill-in notes as the canonical source for official titles, primary Scripture, and sermon outlines.
- Replaced inferred sermon titles with the official note titles, including `A Blueprint for God’s Blessing`, `God’s Blueprint for Your Blessing`, `Faith That Influences`, `Radical Righteousness and Kingdom Relationships`, `God is Up to Something`, `Truthfulness and Revenge`, and `What To Do With People Who Do Not Love You Back`.
- Preserved transcript-derived summaries and concise explanatory detail while removing inferred outline points that were not part of the official fill-in outline.
- Added supporting Scripture references from each week’s fill-in notes without copying full Bible passages into runtime knowledge.
- Added explicit provenance metadata for title, outline, primary Scripture, and summary sources.
- Added `templates/sermon-record-template.md` and updated `SERMON_KNOWLEDGE.md` so future weekly sermon updates follow the same source-priority workflow.
- Updated sermon retrieval regression tests for the official titles and current structured records.

## 0.9.6

- Added structured weekly sermon knowledge records for June 7 through August 2, 2026.
- Added the Summer on the Mount sermon-series record and automatic series membership in the compiled search index.
- Added dedicated sermon and sermon-series retrieval so historical sermon content is opt-in and does not compete with canonical beliefs, ministry, policy, or schedule records.
- Added sermon date, speaker, Scripture, series, and fill-in-notes metadata to the runtime search index.
- Added support for relative sermon questions such as last Sunday, explicit sermon dates, speaker queries, topic queries, current-series questions, and fill-in-note requests.
- Added the approved Subsplash fill-in-note URLs to each weekly sermon record.
- Corrected Habakkuk spelling in the July 19 sermon record and normalized Urbancrest naming in all derived sermon knowledge.
- Added sermon retrieval regression tests.

## 0.9.5

- Fixed a general-retrieval regression that could reject relevant records when a natural-language question reduced to a single strong topic word, such as `donuts`, `coffee`, `livestream`, or `diapers`.
- Kept the 0.9.1 protection that prevents record priority alone from making unrelated records eligible.
- Added high-signal metadata token matching against titles, search terms, aliases, and tags for general fallback retrieval.
- Restricted general fallback context to answer-bearing knowledge, approved FAQ, and sermon records so structural relationship/routing records cannot outrank actual content.
- Added deterministic intent recognition for common parking, giving, and livestream questions.
- Strengthened Guest Services refreshment metadata and added regression coverage for the $1 suggested donation.
- Added cross-ministry general-retrieval regression tests to guard against future over-filtering.


## 0.9.4

- Expanded Women's Ministry from a placeholder overview into an approved ministry description plus seven focused FAQ records.
- Added Women's Ministry answers for participation, membership, volunteering, Small Groups/Bible studies, inviting friends, finding upcoming events, and connecting with other women.
- Updated the canonical Women's Ministry registry description and aliases.
- Reused the existing approved Church Center resources for volunteering and Small Groups.
- Added Women's Ministry retrieval acceptance tests.

## 0.9.3

- Added authoritative church office hours: Monday through Friday, 9:00 AM to 4:00 PM.
- Added a dedicated office-hours article that also distinguishes weekday office hours from Sunday worship times for vague visit questions.


## 0.9.2

- Fixed staff-card routing for Senior Pastor / lead pastor questions so Geoff Prows is deterministically selected.
- Added `lead pastor`, `lead pastor`, and `head pastor` aliases to the canonical Senior Leadership relationship.
- Changed staff selection precedence so an explicit named staff member wins first, canonical ministry/role ownership wins second, and generic staff-route scoring is only a fallback.
- Added regression tests distinguishing Senior Pastor/lead pastor (Geoff Prows) from Executive Pastor (David Bickers).


## 0.9.1

- Added a pre-retrieval safety layer for critical self-harm, violence-risk, immediate abuse-danger, and overdose/medical-emergency statements.
- Added restricted sensitive pastoral-care retrieval for grief, depression, abuse, addiction, marriage/family crisis, and general personal crisis.
- Added the approved U.S. 988 Suicide & Crisis Lifeline resource to `registry/safety.yaml`.
- Added `registry/contact.yaml`; no church office phone number is currently approved.
- Added post-generation phone-number allowlisting to prevent hallucinated contact numbers.
- Redacted raw sensitive questions and answers from SearchQueryLog.
- Tightened general fallback retrieval so record priority alone cannot make unrelated records eligible.
- Added safety and sensitive-query regression tests.

## 0.9.0

- Condensed staff ownership into canonical ministry areas instead of maintaining separate relationships for every routing topic.
- Combined IT, Production, Creative, Website, video, livestream, audio, lighting, and technology under `technical_creative`, owned by Matthew Kirby.
- Combined finance, giving, stewardship, and donations under `finance`, owned by Tanya Byrd.
- Consolidated first-visit and accessibility routing under Guest Services, student parent communication under Students, worship serving under Worship, and Kids safety under Kids.
- Marked the Kids Ministry Director position as vacant and made Sarah Coleman, Preschool Director, the recommended current point person, mirroring Global Missions vacancy handling.
- Added a focused Kids Ministry leadership article and a review trigger for when the Kids Ministry Director position is filled.
- Enhanced compiled staff-ownership records with aliases and topics for deterministic routing.
- Added staff-ownership routing regression tests.

## 0.8.8

- Removed one-time Base44 prompt and patch documents from the knowledge repository.
- Removed stale install and historical update notes that were no longer part of runtime behavior.
- Removed the duplicate legacy emergency-food article.
- Simplified `manifest.yaml` to repository metadata instead of a stale manual file inventory.
- Updated action-link intent guidance for the Google Maps and Apple Maps directions bundle.
- Rebuilt the runtime search index from the current repository state.
- Updated the stale Student Ministry retrieval test to use the generalized schedule record.
- Normalized synced public event copy to avoid em dashes and reduced unnecessary HTML parsing in the event sync.

## 0.7.0

- Added detailed public ministry overviews and one-question, one-answer FAQs for Student Ministry, Preschool, Guest Services, Men's Summit, the Urbancrest Golf Classic, Worship Ministry, and Urbancrest Kids.
- Added Kids Ministry public safety guidance while keeping tactical emergency procedures out of public retrieval.
- Expanded staff routing and ministry relationships for student, preschool, guest, worship, accessibility, and Kids safety questions.
- Added retrieval regression tests for the new ministry content.

## 0.6.3

- Added Planning Center Calendar API enrichment to the live event sync.
- Maps iCal EventInstance IDs to Calendar API EventInstance and Event records.
- Imports the rich public event description as `details`.
- Imports public Church Center, registration, and image URLs when available.
- Pins the Calendar API version and adds secure GitHub Actions secrets.
- Adds regression tests for UID mapping, JSON:API enrichment, and duplicate removal.

## 0.6.2

- Made the weekly schedule and service-time article authoritative retrieval sources.
- Added a dedicated service-time intent.
- Added an indexed `schedule.weekly` record with Sunday times at 9:30 AM and 11:00 AM.
- Preserved authority, confidence, and answer-guidance metadata in the search index.
- Marked routine dated Sunday service occurrences as ineligible for general service-time retrieval.
- Added regression tests for regular service times and date-specific exceptions.

## 0.6.1

- Added current Global Missions Pastor vacancy and transition guidance.
- Updated Jennifer Prows routing to identify her as Missions Administrator and recommended current global missions contact.
- Separated global missions, local missions, and missions administration relationships.
- Added a focused answer for "Who oversees missions?"
- Updated retrieval indexing to retain leadership status, open-role, recommended-contact, and answer-guidance metadata.
- Added regression tests for global missions leadership and local missions routing.

## 0.6.0

- Added a compiled runtime search index for retrieval-first AI answers.
- Added staff identity and routing registries while keeping biographies and fun facts in Base44 Staff.
- Added David Bickers to preaching-related staff routing.
- Added ministry-to-staff relationships and approved action-link records.
- Added runtime source precedence for GitHub knowledge, Base44 Staff, and approved Base44 KnowledgeEntry records.
- Added a dedicated search-index workflow and integrated index rebuilding into the live event sync.
- Included the Small Group title-and-location consolidation fix from event sync 1.4.1.
- Added Base44 implementation and data-model migration instructions.
- Added retrieval acceptance tests.

## 1.4.0

- Split routine Small Group meetings into `small-groups-live.yaml`.
- Added one generated knowledge article per Small Group series.
- Collapsed recurring Small Group occurrences into a single series record.
- Added configurable event categories and priority levels.
- Protected major and ministry events before lower-priority events when applying limits.
- Added a 365-day default lookahead window.
- Added `event-overrides.yaml` for title- or UID-based corrections.
- Added separate Small Group retrieval rules.
- Updated the workflow to stage additions, changes, and deletions across both collections.
- Added tests for category priority, Small Group routing, and chronological selection.
