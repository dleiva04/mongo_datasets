# cdc_gaps — missing cursor field and cursor type mismatch

## What the generator writes

`07_cdc_gaps/generate.py` inserts three groups into `cdc_gaps`:

| `kind` | `updated_at` | Expected under CDC (`cursor_type=timestamp`) |
|---|---|---|
| `good` | BSON `Date` | Ingested |
| `missing` | absent | Skipped (no cursor value) |
| `string` | ISO **string** | Skipped (BSON type != Date) |

```bash
python 07_cdc_gaps/generate.py --drop --each 30
```

## How the connector works for this case (today)

- **CDC** (`cursor_field=updated_at`, `cursor_type=timestamp`): the query is
  `{updated_at: {$gt: since, $lte: init_cap}}`. Documents **without** `updated_at` never match, and
  documents storing `updated_at` as a string never match a `Date` bound — MongoDB compares within a
  BSON type. So only the `good` group is ingested. This directly reflects the connector's documented
  requirements: *"Documents that lack the cursor field are not ingested in CDC mode"* and *"cursor
  type must match the BSON type."*
- **Snapshot** (no `cursor_field`) reads **all** documents regardless of `updated_at`, so it is the
  control that proves the `missing`/`string` docs exist and are otherwise valid.

## Recommended options

Run it twice to compare:

1. CDC: `cursor_field=updated_at`, `cursor_type=timestamp` → expect only `good`.
2. Snapshot: no `cursor_field` → expect all three groups.

An index on `updated_at` is created by the generator.

## What to assert in Databricks

- CDC destination row count ≈ number of `good` docs; no `missing`/`string` rows.
- Snapshot destination contains all three `kind` values.
- Fixing a `string` doc to a real BSON `Date` (or backfilling `missing`) makes it appear on the next
  CDC trigger — as long as its `updated_at` is above the current offset.
