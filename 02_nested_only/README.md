# nested_only — deeply nested documents, snapshot ingestion

## What the generator writes

`02_nested_only/generate.py` inserts customer documents with several levels of nesting and arrays of
sub-objects: `customer -> profile.contact.phones[]` and `customer -> orders[] -> items[] ->
product.attributes.dimensions`. It also nests a `Decimal128` (`unit_price`) inside line items.

```bash
python 02_nested_only/generate.py --drop --count 50
```

## How the connector works for this case (today)

- **Ingestion type:** `snapshot` (no `cursor_field`).
- The connector does **not** flatten nested fields. Each document is emitted as `_id` +
  `document_json`, with the entire nested structure preserved inside `document_json` as Relaxed
  Extended JSON (nested `Decimal128`/`Date` keep their `$numberDecimal`/`$date` wrappers).
- There is no column explosion and no depth limit imposed by the connector; the 16 MB BSON document
  limit still applies at the MongoDB side.

## Recommended options

None. To work with nested data downstream, parse `document_json` in Databricks (e.g. `from_json` /
`parse_json`, then `:` / dot accessors like `document_json:orders[0].items[0].unit_price`).

## What to assert in Databricks

- The table has only `_id` and `document_json`; no `orders`, `profile`, etc. columns are created.
- Parsing `document_json` recovers the full nested tree, including arrays of objects and nested
  `Decimal128`/`Date` values.
