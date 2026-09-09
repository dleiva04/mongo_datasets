"""Drop the collections created by the dataset generators.

By default this only touches the collections this repo creates, and asks
for confirmation before dropping. It never drops the database itself and
never modifies your .env.

Examples:
    python cleanup.py                 # show what exists, then confirm
    python cleanup.py --yes           # drop all generated collections, no prompt
    python cleanup.py --only cdc_gaps iot_telemetry
    python cleanup.py --list          # just list counts, drop nothing
"""

import argparse
import sys

from common.mongo import get_db

# Every collection any generator can create.
GENERATED_COLLECTIONS = [
    "snapshot_typed",
    "iot_telemetry",
    "schema_drift",
    "objectid_cursor",
    "cdc_updates",
    "cdc_gaps",
    "nested_only",
    "cdc_deletes",
    "cdc_deletes_tombstones",
    "cdc_scd_type2",
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--only", nargs="+", metavar="NAME", help="Only drop these collections.")
    parser.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    parser.add_argument("--list", action="store_true", help="List generated collections and counts, drop nothing.")
    args = parser.parse_args()

    db = get_db()
    existing = set(db.list_collection_names())

    targets = args.only if args.only else GENERATED_COLLECTIONS
    if args.only:
        unknown = [t for t in args.only if t not in GENERATED_COLLECTIONS]
        if unknown:
            print(f"Refusing unknown collection(s) not created by this repo: {unknown}", file=sys.stderr)
            sys.exit(1)

    present = [name for name in targets if name in existing]

    if not present:
        print(f"Nothing to drop in database '{db.name}'. No generated collections found.")
        return

    print(f"Database '{db.name}' — generated collections present:")
    for name in present:
        print(f"  {name}: {db[name].count_documents({})} documents")

    if args.list:
        return

    if not args.yes:
        answer = input(f"\nDrop these {len(present)} collection(s)? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted. Nothing was dropped.")
            return

    for name in present:
        db.drop_collection(name)
        print(f"Dropped '{name}'.")
    print(f"Done. Dropped {len(present)} collection(s).")


if __name__ == "__main__":
    main()
