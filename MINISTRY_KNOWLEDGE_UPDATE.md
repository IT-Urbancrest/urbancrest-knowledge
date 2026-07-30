# Ministry Knowledge Update 0.7.0

This release adds public-facing ministry overviews and FAQs for:

- Student Ministry
- Preschool
- Guest Services
- Men's Summit
- Urbancrest Golf Classic
- Worship Ministry
- Urbancrest Kids

## Public safety boundary

The Kids Ministry documents publish family-relevant policies such as volunteer screening, check-in and checkout, well-child guidance, allergies, discipline, and general emergency readiness. Tactical lockdown locations, room-specific hiding instructions, barricade procedures, and detailed security communications remain internal and are not included in public retrieval.

## Install

Copy the patch into the root of the Urbancrest Knowledge repository, preserving folders. Commit and push. Then run:

**Actions → Build Knowledge Search Index → Run workflow**

The patch intentionally does not include `runtime/search-index.json` so the workflow rebuilds the index against the repository's current live event data.
