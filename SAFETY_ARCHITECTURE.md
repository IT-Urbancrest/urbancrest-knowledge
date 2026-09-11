# Safety and Sensitive Query Architecture

Urbancrest AI search uses a pre-retrieval safety layer for delicate personal-care queries.

## Critical safety mode

Critical statements involving suicidal/self-harm risk, imminent violence, immediate abuse danger, or a stated overdose bypass ordinary knowledge retrieval. The application returns a controlled safety response instead of asking the language model to improvise from unrelated knowledge records.

The United States 988 Suicide & Crisis Lifeline is stored in `registry/safety.yaml` as an approved crisis resource for self-harm responses. Pastoral care is presented as secondary to immediate safety support.

## Sensitive pastoral-care mode

Non-immediate grief, depression, abuse, addiction, marriage/family crisis, and general pastoral-crisis questions use only vetted records under `knowledge/pastoral-care/`. Ordinary events, ministry articles, Base44 KnowledgeEntry records, and unrelated search results are excluded from that prompt.

## Contact integrity

`registry/contact.yaml` is the controlled source for church-wide contact information. No church office phone number is currently approved there. The Base44 Staff card remains the source for staff phone numbers. The language model is not given staff phone numbers.

Generated answers are checked for phone numbers before being returned. A phone number is allowed only when the exact normalized number is present in selected authoritative records or the approved safety-resource/contact configuration. Sentences containing unapproved phone numbers are removed.

## Privacy and audit logging

Sensitive and critical searches are preserved in `SearchQueryLog` as the canonical audit record. The stored record keeps the exact user question, the exact response returned by the AI search, the selected safety/pastoral record IDs, and sensitivity metadata when available. This preserves the underlying record for authorized legal, compliance, or incident-response review.

The normal Admin Hub analytics experience must not display the raw sensitive question or answer. Redaction is applied only at presentation time in the Admin Hub, using the configured sensitive category and redacted question/answer formats from `registry/safety.yaml`. The display-layer redaction must not overwrite or mutate the underlying `SearchQueryLog` record.

Historical logs that were already stored as redacted placeholders cannot be reconstructed and remain as originally recorded.

## Normal retrieval

Normal fallback retrieval now requires a meaningful lexical, intent, ministry, audience, or content signal. Record priority alone no longer makes an unrelated record eligible.
