# Runtime Search Index

`search-index.json` is generated from the public Urbancrest Knowledge repository.

Do not edit it manually. It is rebuilt by:

```text
scripts/build_search_index.py
```

The live event sync workflow rebuilds it after calendar updates. The dedicated search-index workflow rebuilds it after other knowledge changes.

Base44 should fetch this one file, cache it by GitHub commit SHA, locally retrieve the best records, and send only those records to the language model.
