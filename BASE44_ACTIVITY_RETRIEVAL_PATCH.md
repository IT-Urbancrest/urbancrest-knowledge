# Base44 Activity and Typo-Tolerant Event Retrieval Patch

Apply this patch to the current `queryKnowledgeBase` function. Do not replace the
function with an older version. Preserve the current retrieval-first architecture,
Calendar API enrichment, Markdown formatting, staff routing, logging, and confidence
handling.

## Why this is needed

A generated event can exist but still be missed when:

1. The question is phrased as availability rather than as an event question:
   `Does Urbancrest have pickleball?`
2. The activity is misspelled by one character:
   `pickeball`
3. Event records are filtered out before local scoring because the question does not
   contain words such as `event`, `calendar`, `next`, or `upcoming`.

## 1. Detect activity-availability questions

Add this helper:

```javascript
function isActivityAvailabilityQuestion(question) {
  const normalized = normalizeText(question);

  return [
    /\bdoes\s+(urbancrest|the church|church)\s+(have|offer)\b/,
    /\bdo\s+(you|we)\s+(have|offer)\b/,
    /\bis\s+there\b/,
    /\bcan\s+i\s+(play|join|participate|attend)\b/,
    /\bwhere\s+can\s+i\s+(play|join|participate)\b/,
  ].some((pattern) => pattern.test(normalized));
}
```

When this returns true:

- set or include the intent `activity_availability`
- keep future `event` records eligible even when the question does not contain
  `event`, `calendar`, `next`, or `upcoming`
- do not search only static ministry articles
- exclude past event occurrences
- prefer the earliest future matching occurrence

## 2. Add conservative typo tolerance

Use typo tolerance only for meaningful tokens with at least five characters. Allow a
maximum edit distance of one. This catches `pickeball` → `pickleball` without making
short words or unrelated records fuzzy.

```javascript
function editDistanceAtMostOne(left, right) {
  const a = String(left || '');
  const b = String(right || '');

  if (a === b) return true;
  if (Math.abs(a.length - b.length) > 1) return false;

  let i = 0;
  let j = 0;
  let edits = 0;

  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      i += 1;
      j += 1;
      continue;
    }

    edits += 1;
    if (edits > 1) return false;

    if (a.length > b.length) i += 1;
    else if (b.length > a.length) j += 1;
    else {
      i += 1;
      j += 1;
    }
  }

  if (i < a.length || j < b.length) edits += 1;
  return edits <= 1;
}

function fuzzyTokenMatches(queryToken, recordToken) {
  if (!queryToken || !recordToken) return false;
  if (queryToken.length < 5 || recordToken.length < 5) return false;
  if (Math.abs(queryToken.length - recordToken.length) > 1) return false;

  return editDistanceAtMostOne(queryToken, recordToken);
}
```

Use the same normalization and stop-word removal already used by local scoring.

## 3. Score activity records before candidate truncation

For an `activity_availability` question, compare meaningful query tokens against:

- `record.title`
- `record.activity_aliases`
- `record.search_terms`
- `record.tags`

Recommended scoring:

```javascript
function activityMatchScore(questionTokens, record) {
  if (record.record_type !== 'event') return 0;

  const activityText = [
    record.title,
    ...(record.activity_aliases || []),
    ...(record.search_terms || []),
    ...(record.tags || []),
  ].join(' ');

  const recordTokens = tokenize(activityText);
  let score = 0;

  for (const queryToken of questionTokens) {
    if (recordTokens.includes(queryToken)) {
      score += 90;
      continue;
    }

    if (recordTokens.some((token) => fuzzyTokenMatches(queryToken, token))) {
      score += 70;
    }
  }

  return score;
}
```

Add this score before selecting the best 6–8 records. Do not apply fuzzy scoring after
candidate selection because the correct event may already have been discarded.

## 4. Dedupe recurring occurrences

Several future records may represent the same recurring activity. After matching:

1. Group event candidates by their first simplified `activity_aliases` value, falling
   back to normalized title.
2. Sort each group by `sort_start_utc`.
3. Keep the earliest future occurrence for the answer unless the user asks for all
   dates.

## 5. Answer behavior

When a future matching event exists, answer confidently that Urbancrest has the
activity on its current calendar and provide the next known date, time, location, and
relevant details.

Do not claim an ongoing permanent ministry merely because one calendar occurrence
exists. Phrase the answer as an event or activity shown on the current calendar.

When no future record matches, use the existing unsure behavior.

## 6. Required acceptance tests

- `Does Urbancrest have pickleball?`
  - retrieves `OPEN GYM Pickleball`
  - answers yes based on a future event record
- `Does Urbancrest have pickeball?`
  - retrieves the same record despite the one-character typo
- `Can I play pickle ball at Urbancrest?`
  - retrieves the same record
- `When is the next OPEN GYM Pickleball?`
  - returns the earliest future occurrence
- An unrelated misspelled word does not produce a false event match
