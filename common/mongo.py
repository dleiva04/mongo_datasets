"""Shared MongoDB helpers for the dataset generators.

All generators connect through :func:`get_db`, which builds a single
``MongoClient`` from the ``MONGODB_URI`` / ``MONGODB_DATABASE`` values in
your real ``.env`` (loaded via python-dotenv). The ``.env`` file is never
modified by anything in this repo; see ``example.env`` for the keys.
"""

import os
import sys
from functools import lru_cache

from dotenv import load_dotenv
from pymongo import ASCENDING, MongoClient
from pymongo.database import Database

load_dotenv()

_SERVER_SELECTION_TIMEOUT_MS = 20_000
_CONNECT_TIMEOUT_MS = 20_000


@lru_cache(maxsize=1)
def _client() -> MongoClient:
    """Return a process-wide singleton MongoClient built from the env."""
    uri = os.getenv("MONGODB_URI")
    if not uri:
        _fail("Missing required environment variable 'MONGODB_URI'.")
    return MongoClient(
        uri,
        serverSelectionTimeoutMS=_SERVER_SELECTION_TIMEOUT_MS,
        connectTimeoutMS=_CONNECT_TIMEOUT_MS,
    )


def get_db() -> Database:
    """Return the configured database handle."""
    database = os.getenv("MONGODB_DATABASE")
    if not database:
        _fail("Missing required environment variable 'MONGODB_DATABASE'.")
    return _client()[database]


def get_collection(name: str, drop: bool = False):
    """Return a collection, optionally dropping it first for a clean run."""
    db = get_db()
    if drop:
        db.drop_collection(name)
    return db[name]


def ensure_index(collection, field: str) -> None:
    """Create an ascending index on the CDC cursor field if absent.

    The connector sorts by the cursor field and MongoDB aborts in-memory
    sorts larger than 32 MB without an index, so CDC collections need one.
    The ``_id`` field is always indexed by MongoDB, so it is skipped.
    """
    if field == "_id":
        return
    collection.create_index([(field, ASCENDING)])


def _fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    print("Copy the keys from example.env into your real .env first.", file=sys.stderr)
    sys.exit(1)
