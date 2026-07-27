# Urbancrest Knowledge Missions Leadership Update 0.6.1

This update reflects Urbancrest's current missions leadership structure:

- Urbancrest is searching for its next Global Missions Pastor.
- Jennifer Prows serves as Missions Administrator and is the recommended current contact for global missions questions and coordination.
- Darrel Schick serves as Local Missions Strategist for local missions and community outreach.
- Staff biographies and fun facts remain in the Base44 Staff entity.

## Install

Copy the contents of this patch into the root of `urbancrest-knowledge`, preserving folders and replacing existing files.

Commit and push the changes. Then run:

**Actions → Build Knowledge Search Index → Run workflow**

The patch includes an already rebuilt `runtime/search-index.json`, but the workflow should still be run after installation to confirm the repository-generated index is current.

## Test questions

- Who oversees missions?
- Who is the Global Missions Pastor?
- Who should I contact about global missions?
- Who do I contact about mission trips?
- Who oversees local missions?
- Tell me about Jennifer Prows.

Expected behavior:

- Explain the Global Missions Pastor search before recommending Jennifer.
- Identify Jennifer as Missions Administrator, never as Global Missions Pastor.
- Return `jennifer_prows` for general or global missions contact questions.
- Return `darrel_schick` for local missions questions.
- Load biographies and fun facts from Base44 Staff only.
