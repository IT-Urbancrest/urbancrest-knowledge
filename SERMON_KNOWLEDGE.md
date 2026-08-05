# Sermon Knowledge Workflow

Urbancrest sermon knowledge uses structured weekly sermon records rather than full transcripts.

## Source priority

Use the published fill-in notes as the canonical structural source for each message. They determine:

- official sermon title
- primary Scripture
- official sermon outline and subpoints
- supporting Scripture references
- any explicitly labeled takeaway
- the approved Subsplash notes URL

Use the sermon transcript only as enrichment for:

- concise message summary
- main idea
- short explanations under the official outline points
- application language
- topics and natural-language search terms

If the transcript and fill-in notes differ on the title, primary passage, or outline, follow the fill-in notes. Normalize obvious automated-caption errors in derived knowledge, including `Urban Crest` to `Urbancrest` and incorrect Bible-book spellings such as `Habach` to `Habakkuk`. Do not store the full transcript in normal runtime retrieval.

## Weekly workflow

1. Add one Markdown file under `knowledge/sermons/YYYY/`.
2. Use the fill-in notes for the official title, primary Scripture, outline, supporting Scriptures, and notes URL.
3. Use the transcript to write a short summary, main idea, explanatory detail, topics, and search terms.
4. Set `category: [sermon]` and `intent.primary: sermon`.
5. If the sermon belongs to a series, set `series_id` and `series_title`.
6. Set source metadata so provenance is explicit:
   - `title_source: fill_in_notes`
   - `outline_source: fill_in_notes`
   - `primary_scripture_source: fill_in_notes`
   - `summary_source: sermon_transcript`
7. Run the Build Knowledge Search Index workflow.

The runtime index automatically associates sermon records with their matching `sermon_series` record, so the series file does not need to be manually updated every week just to add another sermon to the list.

## Retrieval behavior

Sermon records are historical message summaries. They become eligible when the user's question is clearly about a sermon, message, speaker, sermon date, sermon topic, sermon notes, or sermon series.

Sermon records should not be used as the canonical source for Urbancrest doctrine, policy, schedules, or current ministry information when a dedicated knowledge record exists.

## Fill-in notes

Store the exact Subsplash URL in `notes_url` and `resources`. The website assistant may return that link when the user asks for notes from that message. Do not generate or alter a Subsplash URL.

Do not copy the full Bible text from the fill-in notes into the knowledge record. Store Scripture references instead. This keeps the record concise while preserving the passages used in the message.

## Transcript handling

Full sermon transcripts are not required in the repository. A transcript may be used as source material when creating the structured weekly record, then omitted from normal runtime retrieval.
