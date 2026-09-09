"""Generate a dataset for CDC sequenced by the ObjectId ``_id``.

Situation: an insert-only collection with no timestamp field, using the
natural ``_id`` ObjectId as the incremental cursor (``cursor_type=objectid``).
ObjectIds embed a creation timestamp, so sequential inserts are monotonic.

The optional second wave (``--second-wave``) inserts more documents after a
pause so you can test ``start_timestamp`` given as an ObjectId hex string and
the connector's init-time cap.
"""

import argparse
import os
import sys
import time

from bson import ObjectId
from pymongo import InsertOne

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.mongo import get_collection  # noqa: E402

COLLECTION = "objectid_cursor"


def make_document(seq: int) -> dict:
    # _id is a fresh ObjectId, monotonic with insertion time; it IS the cursor.
    return {
        "_id": ObjectId(),
        "seq": seq,
        "payload": f"record-{seq:06d}",
        "kind": "order" if seq % 2 else "refund",
    }


def insert_wave(collection, count: int, start_seq: int) -> ObjectId:
    docs = [make_document(start_seq + i) for i in range(count)]
    collection.bulk_write([InsertOne(doc) for doc in docs], ordered=True)
    return docs[0]["_id"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=500, help="Documents in the first wave.")
    parser.add_argument("--second-wave", type=int, default=0, help="Documents in a second wave after a pause.")
    parser.add_argument("--pause-seconds", type=float, default=2.0, help="Delay before the second wave.")
    parser.add_argument("--drop", action="store_true", help="Drop the collection before inserting.")
    args = parser.parse_args()

    collection = get_collection(COLLECTION, drop=args.drop)

    first_id = insert_wave(collection, args.count, start_seq=0)
    print(f"Wave 1: inserted {args.count} docs. First _id (hex for start_timestamp): {first_id}")

    if args.second_wave:
        time.sleep(args.pause_seconds)
        second_id = insert_wave(collection, args.second_wave, start_seq=args.count)
        print(f"Wave 2: inserted {args.second_wave} docs after {args.pause_seconds}s. First _id: {second_id}")

    print(f"Collection '{COLLECTION}' now holds {collection.count_documents({})} documents.")


if __name__ == "__main__":
    main()
