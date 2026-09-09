# schema_drift — documents that sometimes send different columns

## What the generator writes

`03_schema_drift/generate.py` inserts documents into `schema_drift` where the set of fields varies per
record: `firmware`, `tags`, `location`, `metrics`, and `experiment` appear only some of the time, and
`user_id` is sometimes an integer and sometimes a string (type drift on the same key).

```bash
python 03_schema_drift/generate.py --drop --count 200
```

## How the connector works for this case (today)

- **Ingestion type:** `snapshot` (no `cursor_field`).
- This is exactly what the envelope is designed for: every document, regardless of which fields it
  has, becomes `_id` + `document_json`. The Spark schema is **stable at two columns** — new or
  missing fields never change the table schema, and there is no schema-evolution churn or type
  conflict on drifting keys like `user_id`.
- All varying fields (including the sometimes-int/sometimes-string `user_id`) live inside
  `document_json` as Relaxed Extended JSON.

## Recommended options

None. Snapshot is the natural fit. If you want incremental instead, add a monotonic `updated_at` and
switch to CDC — but the drift-handling behavior is identical because the envelope is the same.

## What to assert in Databricks

- The table has only `_id` and `document_json` even though source documents have many different
  field sets.
- Parsing `document_json` for a field that only some documents have (`firmware`) returns `null` for
  the others rather than failing.
- `user_id` can be read as both int and string across rows because it is untyped inside the JSON.
