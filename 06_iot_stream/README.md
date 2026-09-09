# iot_stream — high-volume IoT telemetry, CDC ingestion

## What the generator writes

`06_iot_stream/generate.py` inserts telemetry readings for many devices into the `iot_telemetry`
collection. Each reading carries a monotonic BSON `event_time` (the CDC cursor), plus
`device_id`, `temperature_c`, `humidity_pct`, `battery_pct`, and a nested `location`. It creates an
ascending index on `event_time` automatically.

```bash
# One large wave (50 devices x 100 readings = 5,000 docs) — exceeds the default
# max_records_per_batch (1000) so multiple CDC microbatches fire.
python 06_iot_stream/generate.py --drop --devices 50 --docs-per-device 100

# Simulate a live stream: keep emitting waves every 500ms until Ctrl+C.
python 06_iot_stream/generate.py --continuous --interval-ms 500 --devices 20 --docs-per-device 50
```

## How the connector works for this case (today)

- **Ingestion type:** `cdc`. Set `cursor_field=event_time`, `cursor_type=timestamp`.
- Each trigger reads `{event_time: {$gt: since, $lte: init_cap}}` sorted ascending, capped at
  `max_records_per_batch`. The `init_cap` is the connector's start time, so a trigger only drains
  data that existed when it began; the next trigger picks up newer readings. This is what makes the
  stream converge under `Trigger.AvailableNow`.
- Schema: `_id`, `document_json`, plus a typed `event_time TIMESTAMP` column (the sequencing key).
- Rows are upserted by `_id`; since IoT readings are insert-only with unique `_id`s, each reading
  becomes one row.

## Recommended options

| Option | Value | Why |
|---|---|---|
| `cursor_field` | `event_time` | Monotonic BSON date. |
| `cursor_type` | `timestamp` | Matches the stored BSON type. |
| `max_records_per_batch` | e.g. `1000` | Microbatch size; lower it to force more batches. |
| `batch_size` | optional | PyMongo network round-trip sizing. |

An index on `event_time` is **required** (the generator creates it).

## What to assert in Databricks

- With a single large wave, the pipeline advances the offset across several microbatches and
  eventually drains (end offset stops changing).
- Running the generator in `--continuous` mode while the pipeline triggers repeatedly shows new
  readings arriving on later triggers.
- No duplicate `_id`s; `event_time` column is populated and monotonic.
