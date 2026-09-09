"""Generate insert-then-delete traffic to exercise delete handling.

Situation: documents are inserted, then a known subset is HARD DELETED
from MongoDB. The current connector cannot see deletes (no
``read_table_deletes`` / change streams), so this dataset demonstrates the
gap and prepares for a future ``cdc_with_deletes`` implementation.

Optionally (``--tombstones``) the deleted ``_id``s are also recorded in a
separate ``cdc_deletes_tombstones`` collection with a ``deleted_at``
cursor, which is one way a future delete-aware read could source them.
"""

import argparse
import os
import random
import sys
from datetime import datetime, timezone

from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.mongo import ensure_index, get_collection, get_db  # noqa: E402

COLLECTION = "cdc_deletes"
TOMBSTONE_COLLECTION = "cdc_deletes_tombstones"
CURSOR_FIELD = "updated_at"


def make_document(i: int) -> dict:
    return {
        "_id": ObjectId(),
        "order_id": f"ord-{i:05d}",
        "amount": round(random.uniform(1, 1000), 2),
        "state": "open",
        "updated_at": datetime.now(timezone.utc),
    }


def phase_insert(collection, count: int) -> None:
    collection.insert_many([make_document(i) for i in range(count)])
    print(f"Inserted {count} documents into '{COLLECTION}'.")


def phase_delete(collection, fraction: float, tombstones: bool) -> None:
    ids = [d["_id"] for d in collection.find({}, {"_id": 1})]
    if not ids:
        print("Nothing to delete — run '--phase insert' first.")
        return
    victims = random.sample(ids, k=max(1, int(len(ids) * fraction)))

    print(f"Deleting {len(victims)} of {len(ids)} documents. Deleted _id(s):")
    for _id in victims:
        print(f"  {_id}")

    if tombstones:
        db = get_db()
        tomb = db[TOMBSTONE_COLLECTION]
        ensure_index(tomb, "deleted_at")
        now = datetime.now(timezone.utc)
        tomb.insert_many([{"_id": _id, "deleted_at": now} for _id in victims])
        print(f"Recorded {len(victims)} tombstones in '{TOMBSTONE_COLLECTION}'.")

    collection.delete_many({"_id": {"$in": victims}})
    print(f"'{COLLECTION}' now holds {collection.count_documents({})} documents.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["insert", "delete", "both"], default="both")
    parser.add_argument("--count", type=int, default=100, help="Documents to insert.")
    parser.add_argument("--delete-fraction", type=float, default=0.3, help="Fraction to hard delete.")
    parser.add_argument("--tombstones", action="store_true", help="Also record deleted _id(s) in a tombstone collection.")
    parser.add_argument("--drop", action="store_true", help="Drop the collection before inserting.")
    args = parser.parse_args()

    collection = get_collection(COLLECTION, drop=args.drop)
    ensure_index(collection, CURSOR_FIELD)

    if args.phase in ("insert", "both"):
        phase_insert(collection, args.count)
    if args.phase in ("delete", "both"):
        phase_delete(collection, args.delete_fraction, args.tombstones)


if __name__ == "__main__":
    main()
