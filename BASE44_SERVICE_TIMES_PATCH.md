# Base44 Service-Time Retrieval Patch

Update the Base44 `queryKnowledgeBase` retrieval logic as follows.

## Detect the intent

Treat questions such as these as `service_times`:

- What time are Sunday services?
- What are your Sunday service times?
- When are services?
- What time does church start?
- What time is church?
- When does Urbancrest meet?

## General service-time questions

1. Prefer records where `authoritative_for` contains `service_times` or `sunday_service_times`.
2. Prefer these record IDs:
   - `schedule.weekly`
   - `about.services.times`
3. Exclude records when:
   - `record_type` is `event`, and
   - `retrieval_exclude_for_intents` contains `service_times`.
4. Answer that Sunday worship services are at **9:30 AM** and **11:00 AM**.
5. Include the `plan_visit` action link.
6. When the authoritative records agree, return confidence from 95 to 100.

## Date-specific questions

For questions that name a date or say `today`, `tomorrow`, `this Sunday`, `next Sunday`, or a holiday:

1. Start with `schedule.weekly`.
2. Search live event records for a dated schedule exception.
3. Use the dated exception only when it is explicitly present.
4. Otherwise use the regular Sunday schedule.

Do not lower confidence merely because multiple routine Sunday service event occurrences exist. Those are calendar occurrences, not competing definitions of the regular weekly schedule.
