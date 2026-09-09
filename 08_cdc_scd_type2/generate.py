"""Generate slowly-changing entities to replicate with SCD Type 2.

Situation: business entities (customers) whose attributes change over
time. Each change is an in-place MongoDB update that bumps a monotonic
``updated_at`` (the CDC cursor). MongoDB always holds ONE current document
per ``_id``; the version history is meant to be reconstructed in Delta by
the pipeline's ``scd_type: SCD_TYPE_2`` apply.

Run insert, then one or more update rounds (optionally between pipeline
triggers) so the destination accumulates one row per version.
"""

import argparse
import os
import random
import sys
from datetime import datetime, timezone

from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.mongo import ensure_index, get_collection  # noqa: E402

COLLECTION = "cdc_scd_type2"
CURSOR_FIELD = "updated_at"

STATUSES = ["prospect", "active", "delinquent", "churned"]
PLANS = ["free", "pro", "enterprise"]
CITIES = ["NYC", "SF", "LON", "BER", "TYO"]


def make_customer(i: int) -> dict:
    return {
        "_id": ObjectId(),
        "customer_id": f"cust-{i:05d}",
        "status": "prospect",
        "plan": random.choice(PLANS),
        "address": {"city": random.choice(CITIES)},
        "version": 1,
        "updated_at": datetime.now(timezone.utc),
    }


def phase_insert(collection, count: int) -> None:
    collection.insert_many([make_customer(i) for i in range(count)])
    print(f"Inserted {count} customers (version 1) into '{COLLECTION}'.")


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
                    "status": random.choice(STATUSES),
                    "plan": random.choice(PLANS),
                    "address": {"city": random.choice(CITIES)},
                    "updated_at": datetime.now(timezone.utc),  # newer cursor = a new version
                },
                "$inc": {"version": 1},
            },
        )
    print(f"Applied a new version to {len(sample)} of {len(ids)} customers (in-place update).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=["insert", "update", "both"], default="both")
    parser.add_argument("--count", type=int, default=50, help="Customers to insert.")
    parser.add_argument("--rounds", type=int, default=1, help="Number of update rounds to apply.")
    parser.add_argument("--update-fraction", type=float, default=0.5, help="Fraction updated per round.")
    parser.add_argument("--drop", action="store_true", help="Drop the collection before inserting.")
    args = parser.parse_args()

    collection = get_collection(COLLECTION, drop=args.drop)
    ensure_index(collection, CURSOR_FIELD)

    if args.phase in ("insert", "both"):
        phase_insert(collection, args.count)
    if args.phase in ("update", "both"):
        for r in range(args.rounds):
            print(f"-- update round {r + 1}/{args.rounds} --")
            phase_update(collection, args.update_fraction)

    print(f"Collection '{COLLECTION}' holds {collection.count_documents({})} current documents (one per _id).")


if __name__ == "__main__":
    main()
