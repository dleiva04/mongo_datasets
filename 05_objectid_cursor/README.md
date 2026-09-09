# objectid_cursor — CDC sequenced by the ObjectId `_id`

## What the generator writes

`05_objectid_cursor/generate.py` inserts documents whose `_id` is a fresh `ObjectId`. Because ObjectIds
embed their creation time, sequential inserts produce a monotonically increasing `_id`, which the
connector can use directly as the CDC cursor. An optional second wave (after a pause) lets you test
`start_timestamp` supplied as an ObjectId hex string.

```bash
python 05_objectid_cursor/generate.py --drop --count 500
python 05_objectid_cursor/generate.py --count 500 --second-wave 500 --pause-seconds 3
```

The generator prints the first `_id` of each wave so you can copy it into `start_timestamp`.

## How the connector works for this case (today)

- **Ingestion type:** `cdc`. Set `cursor_field=_id`, `cursor_type=objectid`.
- Query: `{_id: {$gt: ObjectId(since), $lte: ObjectId.from_datetime(init_cap)}}` sorted ascending,
  limited by `max_records_per_batch`. The offset is stored as the 24-char hex string.
- Because the cursor **is** `_id`, no extra cursor column is added — the schema stays `_id` +
  `document_json`. (`_id` is already a column.)
- `start_timestamp`, when set for the first read, is parsed as an `ObjectId` hex string.

## Recommended options

| Option | Value |
|---|---|
| `cursor_field` | `_id` |
| `cursor_type` | `objectid` |
| `start_timestamp` | optional ObjectId hex (e.g. the value the generator prints) |

`_id` is always indexed by MongoDB, so no extra index is needed.

## What to assert in Databricks

- CDC advances by `_id`; each triggered microbatch reads the next block of ObjectIds in order.
- No extra cursor column appears (unlike timestamp cursors).
- With a second wave inserted after the first drain, the next trigger only ingests the new
  ObjectIds (offset advanced past wave 1).
