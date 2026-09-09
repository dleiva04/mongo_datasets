# cdc_scd_type2 — entity history to replicate with SCD Type 2

## What the generator writes

`08_cdc_scd_type2/generate.py` inserts customers, then applies one or more **update rounds** that change
`status` / `plan` / `address`, bump `version`, and set a newer `updated_at` (the CDC cursor). MongoDB
keeps exactly **one current document per `_id`**; the point of this dataset is to reconstruct the full
version history in Delta via **SCD Type 2**.

```bash
python 08_cdc_scd_type2/generate.py --drop --phase insert --count 50
# ...pipeline trigger #1 captures version 1...
python 08_cdc_scd_type2/generate.py --phase update --rounds 1 --update-fraction 0.5
# ...pipeline trigger #2 captures version 2 for the changed customers... etc.
```

Trigger the pipeline between update rounds so each version crosses the CDC offset separately.

## How the connector + pipeline work for this case

**Connector (implemented):** `ingestion_type: cdc` with `cursor_field=updated_at`,
`cursor_type=timestamp`. Every time a customer's `updated_at` advances, the connector re-emits that
document (same `_id`) with a typed `updated_at` column. That column is the natural **`sequence_by`**.

**Pipeline `scd_type` (this is where Type 1 vs Type 2 is decided — not in the driver):**

- `SCD_TYPE_1` (default): upsert by `_id`, destination keeps only the latest version (one row per
  customer). History is lost. This is what [`04_cdc_updates/`](../04_cdc_updates/) shows.
- `SCD_TYPE_2` (**what you want here**): the destination keeps **one row per version** with
  `__START_AT` / `__END_AT` validity columns. The prior row is end-dated and a new row is opened when
  a customer changes.

Intended pipeline spec entry:

```yaml
objects:
  - table:
      source_table: cdc_scd_type2
      table_configuration:
        scd_type: SCD_TYPE_2
        primary_keys: [_id]
        sequence_by: updated_at   # the CDC cursor column the connector surfaces
```

## Status of SCD Type 2 for this source

`SCD_TYPE_2` is a supported **pipeline** setting in the community connector framework (validated
values are `SCD_TYPE_1`, `SCD_TYPE_2`, `APPEND_ONLY`, with `sequence_by`). The MongoDB CDC path
already emits the sequence column needed to drive it, but Type 2 apply for this connector is not
exercised by the connector's own tests — treat it as the wiring to validate. Two caveats to note:

- **Deletes:** Type 2 will not end-date a row on a **hard delete** until `cdc_with_deletes` exists
  (see [`09_cdc_deletes/`](../09_cdc_deletes/)); only inserts/updates drive history today.
- **Monotonic cursor:** `updated_at` must only increase (this generator guarantees it). A regressing
  cursor would drop versions.

## What to assert in Databricks

- Under `SCD_TYPE_2`, a customer updated N times has **N rows** — one open row (`__END_AT` null) and
  N-1 closed rows with contiguous `__START_AT`/`__END_AT` ordered by `updated_at`.
- The same run under `SCD_TYPE_1` yields **one row** per customer (latest only) — the contrast that
  demonstrates history capture.
