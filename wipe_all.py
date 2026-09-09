"""Wipe an entire MongoDB / Atlas instance for a clean demo reset.

DESTRUCTIVE. Unlike cleanup.py (which only drops the collections this repo
creates), this drops EVERYTHING so you can re-run several ingestions from
scratch without deleting collections one by one.

Two scopes:
  --scope database  (default): drop every collection in MONGODB_DATABASE.
  --scope instance          : drop every non-system database in the cluster
                              (skips admin/local/config).

Safeguards:
  - Lists exactly what will be dropped first.
  - Requires an explicit typed confirmation (the database or cluster host),
    unless --yes is given.
  - Never touches the system databases admin/local/config.
  - Never modifies your .env.

Examples:
    python wipe_all.py                      # wipe MONGODB_DATABASE (confirm)
    python wipe_all.py --scope instance     # wipe whole cluster (confirm)
    python wipe_all.py --yes                # wipe MONGODB_DATABASE, no prompt
    python wipe_all.py --list               # show what exists, drop nothing
"""

import argparse
import sys

from common.mongo import _client, get_db

SYSTEM_DATABASES = {"admin", "local", "config"}


def _wipe_database(db, dry_run: bool) -> int:
    names = [n for n in db.list_collection_names()]
    for name in names:
        if dry_run:
            print(f"  would drop {db.name}.{name} ({db[name].count_documents({})} docs)")
        else:
            db.drop_collection(name)
            print(f"  dropped {db.name}.{name}")
    return len(names)


def _scope_database(args) -> None:
    db = get_db()
    print(f"Scope: database '{db.name}'. Collections present:")
    collections = db.list_collection_names()
    if not collections:
        print("  (none) — nothing to wipe.")
        return
    for name in collections:
        print(f"  {name}: {db[name].count_documents({})} documents")

    if args.list:
        return
    if not _confirm(args, expected=db.name, what=f"ALL {len(collections)} collection(s) in '{db.name}'"):
        return

    dropped = _wipe_database(db, dry_run=False)
    print(f"Done. Dropped {dropped} collection(s) from '{db.name}'.")


def _scope_instance(args) -> None:
    client = _client()
    all_dbs = [n for n in client.list_database_names() if n not in SYSTEM_DATABASES]
    print("Scope: entire instance. Non-system databases present:")
    if not all_dbs:
        print("  (none) — nothing to wipe.")
        return
    for name in all_dbs:
        coll_count = len(client[name].list_collection_names())
        print(f"  {name}: {coll_count} collection(s)")
    print(f"  (system databases {sorted(SYSTEM_DATABASES)} are always preserved)")

    if args.list:
        return
    if not _confirm(args, expected="WIPE INSTANCE", what=f"ALL {len(all_dbs)} database(s) on the cluster"):
        return

    for name in all_dbs:
        client.drop_database(name)
        print(f"  dropped database {name}")
    print(f"Done. Dropped {len(all_dbs)} database(s).")


def _confirm(args, expected: str, what: str) -> bool:
    print(f"\nAbout to permanently delete {what}. THIS CANNOT BE UNDONE.")
    if args.yes:
        return True
    answer = input(f"Type '{expected}' to confirm: ").strip()
    if answer != expected:
        print("Confirmation did not match. Aborted. Nothing was dropped.")
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scope", choices=["database", "instance"], default="database",
                        help="Wipe the configured database (default) or every non-system database.")
    parser.add_argument("--yes", action="store_true", help="Skip the typed confirmation.")
    parser.add_argument("--list", action="store_true", help="List what exists, drop nothing.")
    args = parser.parse_args()

    if args.scope == "instance":
        _scope_instance(args)
    else:
        _scope_database(args)


if __name__ == "__main__":
    main()
