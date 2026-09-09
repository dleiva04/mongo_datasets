# cdc_updates — in-place updates, CDC upsert (SCD Type 1)

## What the generator writes

`04_cdc_updates/generate.py` inserts documents (`version: 1`) into `cdc_updates`, then updates a subset
**in place**: it changes `balance`/`status`, bumps `version`, and sets a **newer** `updated_at` (the
CDC cursor). Run the phases separately to observe the upsert between pipeline triggers.

```bash
python 04_cdc_updates/generate.py --drop --phase insert --count 100
# ...let the pipeline trigger once...
python 04_cdc_updates/generate.py --phase update --update-fraction 0.4
```

## How the connector works for this case (today)

- **Ingestion type:** `cdc`. Set `cursor_field=updated_at`, `cursor_type=timestamp`.
- When a document's `updated_at` moves past the last offset, the connector re-reads that document and
  emits it again with the same `_id`. The framework **upserts by `_id`**, so the destination row is
  overwritten with the newest document — this is **SCD Type 1** (latest wins). `version` in
  `document_json` reflects the newest value.
- MongoDB still holds exactly one document per `_id`; the "history" only ever exists as the latest
  state unless you opt into Type 2 (see [`08_cdc_scd_type2/`](../08_cdc_scd_type2/)).

## Recommended options

| Option | Value |
|---|---|
| `cursor_field` | `updated_at` |
| `cursor_type` | `timestamp` |
| pipeline `scd_type` | `SCD_TYPE_1` (default) |

An index on `updated_at` is **required** (the generator creates it).

## Caveat about non-monotonic updates

The cursor must only increase. This generator always sets `updated_at = now(UTC)` on update, so it
stays monotonic. If an application ever wrote an older `updated_at`, CDC would skip it — that failure
mode is covered in [`07_cdc_gaps/`](../07_cdc_gaps/).

## What to assert in Databricks

- After the update phase and the next trigger, the changed `_id`s show their new `balance`/`status`
  and higher `version` — with **no new rows** (row count unchanged).
- Unchanged documents are not re-emitted.
