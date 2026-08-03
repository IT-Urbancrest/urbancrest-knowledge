# General Schedule System 0.8.0

This patch replaces ministry-specific recurring schedule patches with one structured schedule registry.

## Source of truth

`registry/schedule.yaml` is now the authoritative source for normal recurring service and ministry meeting times.

It contains the currently established weekly schedule:

- Sunday Worship Services: Sunday at 9:30 AM and 11:00 AM
- Kids Sunday School: Sunday at 9:30 AM and 11:00 AM
- AWANA: Wednesday at 6:15 PM
- Student Ministry: Sunday at 9:30 AM and Wednesday at 6:30 PM
- Student Ministry regular gatherings pause during the summer while students participate in local missions efforts
- Adult Bible Studies: Wednesday at 6:30 PM
- Wednesday Night Dinner: Wednesday at 5:30 PM in the Gymnasium

## Generated runtime records

The updated index builder creates:

- one specific record per recurring activity
- one aggregate record per ministry
- one overall weekly schedule record

For example:

```text
schedule.worship.sunday
schedule.kids.sunday_school
schedule.kids.awana
schedule.students.weekly
schedule.ministry.kids
schedule.ministry.students
schedule.weekly
```

## Legacy schedule FAQs

The builder suppresses legacy Markdown records whose IDs match:

```text
ministries.<ministry>.schedule
```

This prevents the existing Student Ministry schedule FAQ and the newer Kids schedule FAQ from competing with the structured schedule source.

The Markdown files can remain in the repository during migration.

## Install

Copy the patch contents into the root of `urbancrest-knowledge`, preserving paths.

Commit and push, then run:

**Actions → Build Knowledge Search Index → Run workflow**

After the index rebuild, apply `BASE44_GENERAL_SCHEDULE_RETRIEVAL_PROMPT.md` to the current Base44 website AI implementation.

Do not replace the current Base44 function with an older version.

## Future schedule changes

Going forward, recurring ministry schedule changes should normally require editing only:

```text
registry/schedule.yaml
```

Examples:

- changing a weekly meeting time
- adding a new recurring ministry
- adding an alias users may search for
- adding a seasonal note
- changing the recommended ministry contact

A new Base44 code patch should not be required for each ministry.
