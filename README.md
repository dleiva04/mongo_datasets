# MongoDB Connector Test Datasets

CLI generators that populate MongoDB (or MongoDB Atlas) with datasets designed to exercise the
[Lakeflow MongoDB community connector](/Users/david.leiva/Desktop/lakeflow-community-connectors/src/databricks/labs/community_connector/sources/mongodb/mongodb.py).
Each folder is one ingestion/data-engineering situation, with a generator that writes **directly
into MongoDB** and a README that explains how the connector handles that case today and, where a
feature is not built yet, how it is intended to work so you can replicate it later.

## Why Python + PyMongo

The connector itself is built on the official `pymongo` driver and BSON (`bson.json_util`), so the
generators use the same stack. Writing native BSON types (`ObjectId`, `datetime`, `Decimal128`,
`Binary`, nested docs) is the only way to actually test the connector's Relaxed Extended JSON
envelope.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy the keys from [`example.env`](example.env) into your real `.env` (kept private, never edited by
this repo):

```
MONGODB_URI=mongodb+srv://user:password@cluster.mongodb.net
MONGODB_DATABASE=connector_test
```

Run any generator (each supports `--drop` to recreate its collection):

```bash
python 01_snapshot_typed/generate.py --drop
python 06_iot_stream/generate.py --devices 50 --docs-per-device 100
```

Folders are numbered `01_`…`09_` so they list in the recommended learning order (see the timeline
below).

## How the MongoDB community connector works

**Implemented today:**

- **Snapshot** (`ingestion_type: snapshot`, the default): no `cursor_field`. Every trigger runs
  `find({})` and fully refreshes the destination. Envelope schema is `_id` (string) +
  `document_json` (Relaxed Extended JSON). Primary key is `_id`.
- **CDC** (`ingestion_type: cdc`): set `cursor_field` and `cursor_type` (`timestamp` or `objectid`).
  Each trigger reads `{cursor_field: {$gt: since, $lte: init_cap}}` sorted ascending, limited to
  `max_records_per_batch`. Rows are **upserted by `_id`** — the destination keeps the latest
  document per `_id` (Type 1). Docs missing the cursor field are skipped; the cursor's BSON type
  must match `cursor_type`; the cursor field must be indexed.
- **Nested fields** are not flattened — they stay inside `document_json`.

**Not built yet (READMEs describe the intended design):**

- **`cdc_with_deletes`** — a framework ingestion type that also calls `read_table_deletes()` to emit
  deleted keys (primary key + cursor). The MongoDB connector does not implement it, so hard deletes
  are currently invisible to CDC. Intended source: change streams (`operationType: delete`) or a
  tombstone collection.
- **SCD Type 2** — a **pipeline** setting (`table_configuration.scd_type: SCD_TYPE_2` with
  `sequence_by`), not a driver mode. It keeps full history in Delta (`__START_AT` / `__END_AT`). The
  CDC cursor column is the natural `sequence_by`; Type 2 apply for this source is the
  missing/untested wiring.

## Folders

Folders are listed here in their numbered (learning) order.

| Folder | Collection | Situation / process under test | Connector + pipeline options |
|---|---|---|---|
| [`01_snapshot_typed/`](01_snapshot_typed/) | `snapshot_typed` | Snapshot of mixed BSON types; Extended JSON round-trip | snapshot (no `cursor_field`) |
| [`02_nested_only/`](02_nested_only/) | `nested_only` | Deeply nested docs stay inside `document_json` | snapshot |
| [`03_schema_drift/`](03_schema_drift/) | `schema_drift` | Documents that sometimes send different columns | snapshot (envelope stability) |
| [`04_cdc_updates/`](04_cdc_updates/) | `cdc_updates` | Same `_id` rewritten with newer `updated_at` (Type 1 upsert) | `cursor_field=updated_at`; `scd_type: SCD_TYPE_1` |
| [`05_objectid_cursor/`](05_objectid_cursor/) | `objectid_cursor` | CDC sequenced by `_id` | `cursor_field=_id`, `cursor_type=objectid` |
| [`06_iot_stream/`](06_iot_stream/) | `iot_telemetry` | High-volume CDC microbatches / streaming | `cursor_field=event_time`, `cursor_type=timestamp` |
| [`07_cdc_gaps/`](07_cdc_gaps/) | `cdc_gaps` | Missing cursor field + string vs BSON date mismatch | `cursor_field=updated_at`, `cursor_type=timestamp` |
| [`08_cdc_scd_type2/`](08_cdc_scd_type2/) | `cdc_scd_type2` | Entity history to replicate with SCD Type 2 | CDC + `scd_type: SCD_TYPE_2`, `sequence_by: updated_at` |
| [`09_cdc_deletes/`](09_cdc_deletes/) | `cdc_deletes` | Hard deletes after insert | CDC can't see deletes today; future `cdc_with_deletes` |

## Recommended timeline (easiest to most complex)

Work through the datasets in this order. Each stage builds on what the previous one proved, so if
something breaks you already know the simpler layer works.

```mermaid
flowchart TD
  s1["01_snapshot_typed"] --> s2["02_nested_only"]
  s2 --> s3["03_schema_drift"]
  s3 --> s4["04_cdc_updates"]
  s4 --> s5["05_objectid_cursor"]
  s5 --> s6["06_iot_stream"]
  s6 --> s7["07_cdc_gaps"]
  s7 --> s8["08_cdc_scd_type2"]
  s8 --> s9["09_cdc_deletes"]
```

| # | Dataset | Why here | What you learn / validate |
|---|---|---|---|
| 1 | [`01_snapshot_typed/`](01_snapshot_typed/) | Simplest possible: full-refresh snapshot, no cursor | The connection works, the `_id` + `document_json` envelope, and BSON types round-trip as Extended JSON. Start here. |
| 2 | [`02_nested_only/`](02_nested_only/) | Still snapshot, one new idea | Nested docs are not flattened — they stay inside `document_json`. |
| 3 | [`03_schema_drift/`](03_schema_drift/) | Still snapshot, one new idea | The Spark schema stays stable even when documents send different columns/types. |
| 4 | [`04_cdc_updates/`](04_cdc_updates/) | First CDC step | `cursor_field` + `cursor_type=timestamp`, offsets, and upsert-by-`_id` (SCD Type 1). Introduces triggers and the required cursor index. |
| 5 | [`05_objectid_cursor/`](05_objectid_cursor/) | CDC variant | Same CDC idea but sequenced by the `_id` ObjectId (`cursor_type=objectid`) with no extra cursor column. |
| 6 | [`06_iot_stream/`](06_iot_stream/) | CDC at volume | Multiple microbatches, `max_records_per_batch`, the init-time cap, and a live `--continuous` stream. |
| 7 | [`07_cdc_gaps/`](07_cdc_gaps/) | CDC edge cases | What CDC silently skips: docs missing the cursor field and cursor type mismatches (string vs BSON date). Compare against snapshot. |
| 8 | [`08_cdc_scd_type2/`](08_cdc_scd_type2/) | Beyond the driver, into the pipeline | Reconstruct full history in Delta with `scd_type: SCD_TYPE_2` + `sequence_by`. Contrast with the Type 1 result from step 4. |
| 9 | [`09_cdc_deletes/`](09_cdc_deletes/) | The current frontier | Deletes are not tracked yet; understand the gap and the intended `cdc_with_deletes` design. Most conceptual, so it comes last. |

Rough grouping: steps 1-3 are snapshot fundamentals, 4-6 are core CDC, and 7-9 are edge cases and
not-yet-built behavior.

## Cleanup

`cleanup.py` drops the collections these generators create (it never drops the database or touches
your `.env`). By default it lists what exists and asks for confirmation.

```bash
python cleanup.py            # show generated collections + counts, then confirm
python cleanup.py --yes      # drop them all, no prompt
python cleanup.py --list     # just list, drop nothing
python cleanup.py --only cdc_gaps iot_telemetry   # drop specific ones
```

### Full wipe (demo reset)

`wipe_all.py` is the aggressive reset for a demo cluster: it drops **everything**, not just the
collections this repo creates. Useful after several ingestions when you don't want to delete
collections one by one. It never touches the system databases (`admin`/`local`/`config`) or your
`.env`, and requires a typed confirmation.

```bash
python wipe_all.py                   # drop every collection in MONGODB_DATABASE (confirm)
python wipe_all.py --scope instance  # drop every non-system database in the cluster (confirm)
python wipe_all.py --list            # show what exists, drop nothing
python wipe_all.py --yes             # skip the confirmation prompt
```

Use `cleanup.py` for routine, repo-scoped cleanup; use `wipe_all.py` only on a throwaway/demo
instance.

## Notes

- Generators write to MongoDB only; they do not produce local data files.
- Nothing here modifies the `lakeflow-community-connectors` repo or your `.env`.
