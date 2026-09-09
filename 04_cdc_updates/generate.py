"""Generate insert-then-update traffic for CDC upsert (Type 1) testing.

Situation: rows are inserted, then a subset is updated in place with a
NEWER ``updated_at`` and changed payload. Under the connector's CDC path
each changed document is re-read and upserted by ``_id``, so the
destination keeps only the latest version (SCD Type 1).

Run ``--phase insert`` first, then ``--phase update`` (optionally between
pipeline triggers) to observe the upsert.
"""

import argparse
import os
import random
import sys
from datetime import datetime, timezone

from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.mongo import ensure_index, get_collection  # noqa: E402

COLLECTION = "cdc_updates"
CURSOR_FIELD = "updated_at"


def make_document(i: int) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "_id": ObjectId(),
        "account_id": f"acct-{i:05d}",
        "balance": round(random.uniform(0, 10000), 2),
        "status": "active",
        "version": 1,
        "updated_at": now,
    }


def phase_insert(collection, count: int) -> None:
    docs = [make_document(i) for i in range(count)]
    collection.insert_many(docs)
    print(f"Inserted {count} documents (version 1) into '{COLLECTION}'.")


def phase_update(collection, fraction: float) -> None:
    ids = [d["_id"] for d in collection.find({}, {"_id": 1})]
    if not ids:
        print("Nothing to update — run '--phase insert' first.")
        return
    sample = random.sample(ids, k=max(1, int(len(ids) * fraction)))
    for _id in sample:
        collection.update_one(
            {"_id": _id},
            {
                "$set": {
                    "balance": round(random.uniform(0, 10000), 2),
                    "status": random.choice(["active", "frozen", "closed"]),
                    # Newer updated_at so CDC re-reads this document.
                    "updated_at": datetime.now(timezone.utc),
                },
                "$inc": {"version": 1},
            },
        )
    print(f"Updated {len(sample)} of {len(ids)} documents in place with a newer 'updated_at'.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["insert", "update", "both"], default="both")
    parser.add_argument("--count", type=int, default=100, help="Documents to insert.")
    parser.add_argument("--update-fraction", type=float, default=0.4, help="Fraction to update in place.")
    parser.add_argument("--drop", action="store_true", help="Drop the collection before inserting.")
    args = parser.parse_args()

    collection = get_collection(COLLECTION, drop=args.drop)
    ensure_index(collection, CURSOR_FIELD)

    if args.phase in ("insert", "both"):
        phase_insert(collection, args.count)
    if args.phase in ("update", "both"):
        phase_update(collection, args.update_fraction)

    print(f"Collection '{COLLECTION}' holds {collection.count_documents({})} documents.")


if __name__ == "__main__":
    main()
