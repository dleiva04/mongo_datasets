"""Generate documents whose shape drifts from one record to the next.

Situation: a collection where documents "sometimes send different
columns" — extra fields, missing fields, and occasional type changes for
the same key. Confirms the connector's envelope keeps a stable Spark
schema (``_id`` + ``document_json``) no matter how the documents vary.
"""

import argparse
import os
import random
import sys
from datetime import datetime, timezone

from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.mongo import get_collection  # noqa: E402

COLLECTION = "schema_drift"


def make_document(i: int) -> dict:
    """Return an event whose fields vary per record."""
    doc: dict = {
        "_id": ObjectId(),
        "event_id": f"evt-{i:05d}",
        "source": random.choice(["web", "mobile", "api"]),
    }

    # user_id sometimes an int, sometimes a string (type drift on one key).
    if random.random() < 0.5:
        doc["user_id"] = random.randint(1, 9999)
    else:
        doc["user_id"] = f"u-{random.randint(1, 9999)}"

    # Optional extra columns present only some of the time.
    if random.random() < 0.6:
        doc["firmware"] = f"{random.randint(1, 4)}.{random.randint(0, 9)}.{random.randint(0, 9)}"
    if random.random() < 0.4:
        doc["tags"] = random.sample(["a", "b", "c", "d", "e"], k=random.randint(1, 3))
    if random.random() < 0.5:
        doc["location"] = {"city": random.choice(["NYC", "SF", "LON"]), "zip": f"{random.randint(10000, 99999)}"}
    if random.random() < 0.3:
        doc["metrics"] = {"latency_ms": random.randint(1, 500), "retries": random.randint(0, 5)}
    if random.random() < 0.2:
        # Occasionally a whole extra nested blob nobody else has.
        doc["experiment"] = {"name": "beta", "bucket": random.choice(["A", "B"]), "params": {"x": random.random()}}

    doc["created_at"] = datetime.now(timezone.utc)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=200, help="Number of documents to insert.")
    parser.add_argument("--drop", action="store_true", help="Drop the collection before inserting.")
    args = parser.parse_args()

    collection = get_collection(COLLECTION, drop=args.drop)
    docs = [make_document(i) for i in range(args.count)]
    collection.insert_many(docs)

    with_firmware = sum(1 for d in docs if "firmware" in d)
    print(f"Inserted {len(docs)} documents into '{COLLECTION}' ({with_firmware} with 'firmware', varied shapes).")


if __name__ == "__main__":
    main()
