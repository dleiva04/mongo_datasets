# cdc_deletes — hard deletes (delete handling gap + future design)

## What the generator writes

`09_cdc_deletes/generate.py` inserts documents into `cdc_deletes`, then **hard deletes** a known subset
and prints the deleted `_id`s. With `--tombstones` it also records each deleted `_id` (plus a
`deleted_at` timestamp) in a separate `cdc_deletes_tombstones` collection.

```bash
python 09_cdc_deletes/generate.py --drop --phase insert --count 100
# ...let the pipeline trigger once...
python 09_cdc_deletes/generate.py --phase delete --delete-fraction 0.3
# or, capture deletes for a future delete-aware read:
python 09_cdc_deletes/generate.py --phase delete --tombstones
```

## How the connector works for this case (today)

**Deletes are not tracked.** The MongoDB connector implements only `snapshot` and `cdc`, and its CDC
query is `{updated_at: {$gt: since, $lte: init_cap}}` — a hard delete removes the document, so there
is nothing for CDC to read. Consequences:

- **CDC (`ingestion_type: cdc`):** the deleted `_id`'s Delta row **remains** (stale). CDC only ever
  inserts/updates by `_id`; it never removes.
- **Snapshot (`ingestion_type: snapshot`):** the next full refresh runs `find({})`, which no longer
  returns the deleted documents, so they naturally disappear from the destination. Snapshot is the
  only current way to reflect deletes — at the cost of a full re-read every trigger.

## Not built yet — intended design (`cdc_with_deletes`)

The Lakeflow Connect interface defines a delete-aware ingestion type that the MongoDB connector does
**not** yet implement:

- `read_table_metadata` would return `ingestion_type: "cdc_with_deletes"`.
- The connector would implement `read_table_deletes(table_name, start_offset, table_options)`,
  returning deleted records that carry at least the **primary key (`_id`)** and the **cursor** field,
  following the same offset/pagination protocol as `read_table`.
- The framework's APPLY CHANGES would then **remove** the key (SCD Type 1) or **close** its history
  with `__END_AT` (SCD Type 2).

Two plausible sources for the delete feed:

1. **Change streams** — watch the collection for `operationType: delete` and emit
   `documentKey._id`. Requires a replica set / Atlas and a resumable change-stream token as the
   offset. This is the option the connector README calls out (`no cdc_with_deletes / change streams
   yet`).
2. **Tombstone collection** — the application soft-records deletions (what `--tombstones` simulates):
   `read_table_deletes` reads `cdc_deletes_tombstones` ordered by `deleted_at`, emitting each `_id`.

## What to assert

- **Today:** after a delete + CDC trigger, the deleted `_id` is still present in the CDC destination
  (proving the gap); a snapshot refresh drops it.
- **After `cdc_with_deletes` lands:** the deleted `_id`s from the printout / tombstones should be
  removed (SCD1) or end-dated (SCD2) in the destination on the next trigger.
