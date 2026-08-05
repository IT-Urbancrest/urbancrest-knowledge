# Changelog

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
