"""Generate a small snapshot dataset covering many BSON types.

Situation: a normal collection with heterogeneous, richly-typed documents.
Exercises the connector's snapshot path and its Relaxed Extended JSON
envelope, which must round-trip ObjectId, Decimal128, dates and binary.
"""

import argparse
import os
import random
import sys
from datetime import datetime, timedelta, timezone

from bson import Binary, Decimal128, ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.mongo import get_collection  # noqa: E402

COLLECTION = "snapshot_typed"


def build_documents(count: int) -> list[dict]:
    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    docs = []
    for i in range(count):
        docs.append(
            {
                "_id": ObjectId(),
                "sku": f"SKU-{i:04d}",
                "name": random.choice(["Widget", "Gadget", "Gizmo", "Sprocket"]),
                "quantity": random.randint(0, 5000),
                "big_count": random.randint(2**31, 2**52),
                "price": Decimal128(str(round(random.uniform(1, 999), 2))),
                "weight_kg": round(random.uniform(0.1, 50.0), 3),
                "in_stock": bool(random.getrandbits(1)),
                "discontinued": None,
                "created_at": base + timedelta(hours=i),
                "supplier_ref": ObjectId(),
                "thumbnail": Binary(bytes(random.getrandbits(8) for _ in range(16))),
                "tags": random.sample(["new", "sale", "clearance", "premium", "eco"], k=2),
                "ratings": [random.randint(1, 5) for _ in range(3)],
                "dimensions": {
                    "length_cm": round(random.uniform(1, 100), 1),
                    "width_cm": round(random.uniform(1, 100), 1),
                    "height_cm": round(random.uniform(1, 100), 1),
                },
            }
        )
    return docs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=30, help="Number of documents to insert.")
    parser.add_argument("--drop", action="store_true", help="Drop the collection before inserting.")
    args = parser.parse_args()

    collection = get_collection(COLLECTION, drop=args.drop)
    docs = build_documents(args.count)
    collection.insert_many(docs)
    print(f"Inserted {len(docs)} documents into '{COLLECTION}'. Total now: {collection.count_documents({})}.")


if __name__ == "__main__":
    main()
