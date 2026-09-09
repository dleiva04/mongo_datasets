"""Generate deeply nested documents (snapshot ingestion).

Situation: documents with several levels of nesting and arrays of
sub-objects (customer -> orders -> line items -> attributes). Confirms the
connector does NOT flatten nested fields into columns; everything stays
inside ``document_json``.
"""

import argparse
import os
import random
import sys
from datetime import datetime, timezone

from bson import Decimal128, ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.mongo import get_collection  # noqa: E402

COLLECTION = "nested_only"


def make_line_item(j: int) -> dict:
    return {
        "line_no": j,
        "product": {
            "sku": f"SKU-{random.randint(1000, 9999)}",
            "name": random.choice(["Alpha", "Beta", "Gamma"]),
            "attributes": {
                "color": random.choice(["red", "green", "blue"]),
                "dimensions": {"w": random.randint(1, 50), "h": random.randint(1, 50)},
                "flags": random.sample(["gift", "fragile", "hazmat"], k=random.randint(0, 2)),
            },
        },
        "qty": random.randint(1, 5),
        "unit_price": Decimal128(str(round(random.uniform(1, 500), 2))),
    }


def make_order(k: int) -> dict:
    return {
        "order_id": f"ord-{k:04d}",
        "placed_at": datetime.now(timezone.utc),
        "items": [make_line_item(j) for j in range(random.randint(1, 4))],
        "shipping": {"address": {"city": random.choice(["NYC", "LA"]), "geo": {"lat": 40.7, "lon": -74.0}}},
    }


def make_customer(i: int) -> dict:
    return {
        "_id": ObjectId(),
        "customer_id": f"cust-{i:05d}",
        "profile": {
            "name": {"first": "Jane", "last": f"Doe{i}"},
            "contact": {"emails": [f"jane{i}@example.com"], "phones": [{"type": "mobile", "num": "555-0100"}]},
        },
        "orders": [make_order(k) for k in range(random.randint(1, 3))],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=50, help="Number of customer documents to insert.")
    parser.add_argument("--drop", action="store_true", help="Drop the collection before inserting.")
    args = parser.parse_args()

    collection = get_collection(COLLECTION, drop=args.drop)
    docs = [make_customer(i) for i in range(args.count)]
    collection.insert_many(docs)
    print(f"Inserted {len(docs)} nested customer documents into '{COLLECTION}'.")


if __name__ == "__main__":
    main()
