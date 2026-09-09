# snapshot_typed — mixed BSON types, snapshot ingestion

## What the generator writes

`01_snapshot_typed/generate.py` inserts ~30 richly-typed documents into the `snapshot_typed`
collection. Each document covers the BSON types the connector must preserve: `String`, `Int32`,
`Int64` (`big_count`), `Double`, `Decimal128` (`price`), `Boolean`, `Null`, `Date` (`created_at`),
`ObjectId` (`_id`, `supplier_ref`), `Binary` (`thumbnail`), arrays of scalars, and a nested object
(`dimensions`).

```bash
python 01_snapshot_typed/generate.py --drop --count 30
```

## How the connector works for this case (today)

- **Ingestion type:** `snapshot`. Leave `cursor_field` unset. The connector runs `find({})` and
  fully refreshes the destination on every trigger.
- **Envelope schema:** `_id STRING`, `document_json STRING`. The whole document is serialized with
  `bson.json_util.dumps` in **Relaxed Extended JSON**, so types round-trip as:
  - `ObjectId` → `{"$oid": "..."}`
  - `Decimal128` → `{"$numberDecimal": "..."}`
  - `Date` → `{"$date": "..."}`
  - `Binary` → `{"$binary": {...}}`
- The Spark schema stays fixed at two columns regardless of per-document differences, which is the
  point of the envelope.

## Recommended options

No table options required. Optionally set `batch_size` to tune PyMongo network round-trips.

## What to assert in Databricks

- The destination table has exactly `_id` and `document_json`.
- Row count equals the collection count; re-running the pipeline fully refreshes (no duplicates).
- `parse_json(document_json)` (or `:` accessors) recovers each typed field, and `$numberDecimal` /
  `$date` / `$oid` / `$binary` wrappers are present for those types.
