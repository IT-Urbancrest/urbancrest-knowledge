# Service-Time Confidence Update 0.6.2

This patch makes Urbancrest's regular service times authoritative for retrieval.

## Install

Copy the patch contents into the root of `urbancrest-knowledge`, preserving folders.

Commit and push the changes, then run:

**Actions → Build Knowledge Search Index → Run workflow**

Give `BASE44_SERVICE_TIMES_PATCH.md` to the Base44 website AI agent so its retrieval code honors the new authority and exclusion fields.

## Expected answer

For a general question such as:

> What time are Sunday services?

The agent should answer confidently:

> Urbancrest has Sunday worship services at 9:30 AM and 11:00 AM.

It should also include the Plan Your Visit link.

For a specific Sunday or holiday date, it should check the live event registry for a documented exception.
