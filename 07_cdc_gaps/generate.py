"""Generate CDC edge cases: missing cursor fields and type mismatches.

Situation: a collection where some documents cannot be picked up by CDC:
  - "good"    : ``updated_at`` stored as a proper BSON Date (ingested).
  - "missing" : no ``updated_at`` field at all (skipped by CDC).
  - "string"  : ``updated_at`` stored as an ISO STRING, not a Date
                (skipped when ``cursor_type=timestamp`` because the BSON
                type does not match).

Snapshot mode reads all three groups; CDC reads only "good". Use this to
show the difference and to validate the connector's stated requirements.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

from bson import ObjectId

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.mongo import ensure_index, get_collection  # noqa: E402

COLLECTION = "cdc_gaps"
CURSOR_FIELD = "updated_at"


def good_doc(i: int) -> dict:
    return {
        "_id": ObjectId(),
        "kind": "good",
        "label": f"good-{i:04d}",
        "updated_at": datetime.now(timezone.utc),  # BSON Date — matches cursor_type=timestamp
    }


def missing_doc(i: int) -> dict:
    return {
        "_id": ObjectId(),
        "kind": "missing",
        "label": f"missing-{i:04d}",
        # No updated_at field at all: invisible to CDC.
    }


def string_doc(i: int) -> dict:
    return {
        "_id": ObjectId(),
        "kind": "string",
        "label": f"string-{i:04d}",
        # ISO string, NOT a BSON Date: type mismatch for cursor_type=timestamp.
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--each", type=int, default=30, help="Documents per group (good/missing/string).")
    parser.add_argument("--drop", action="store_true", help="Drop the collection before inserting.")
    args = parser.parse_args()

    collection = get_collection(COLLECTION, drop=args.drop)
    ensure_index(collection, CURSOR_FIELD)

    docs = (
        [good_doc(i) for i in range(args.each)]
        + [missing_doc(i) for i in range(args.each)]
        + [string_doc(i) for i in range(args.each)]
    )
    collection.insert_many(docs)

    print(
        f"Inserted into '{COLLECTION}': {args.each} good (BSON Date), "
        f"{args.each} missing cursor, {args.each} string cursor."
    )
    print("CDC (cursor_type=timestamp) should ingest only the 'good' group; snapshot ingests all.")


if __name__ == "__main__":
    main()
