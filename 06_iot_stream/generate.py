"""Generate a high-volume IoT telemetry stream for CDC testing.

Situation: many devices emitting frequent readings with a monotonically
increasing ``event_time``. Drives the connector's incremental (CDC) path
across many microbatches, and can run continuously to simulate a live
stream landing on the connector between triggers.
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import InsertOne

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.mongo import ensure_index, get_collection  # noqa: E402

COLLECTION = "iot_telemetry"
CURSOR_FIELD = "event_time"


def make_reading(device_index: int, seq: int) -> dict:
    return {
        "_id": ObjectId(),
        "device_id": f"sensor-{device_index:05d}",
        "seq": seq,
        # Monotonic BSON date: the CDC cursor. now(UTC) always increases.
        "event_time": datetime.now(timezone.utc),
        "temperature_c": round(15 + (seq % 20) + device_index % 5 * 0.1, 2),
        "humidity_pct": round(40 + (seq % 40), 2),
        "battery_pct": max(0, 100 - (seq % 100)),
        "location": {"lat": round(40.0 + device_index * 1e-4, 6), "lon": round(-74.0 - device_index * 1e-4, 6)},
        "status": "ok" if seq % 17 else "warn",
    }


def write_wave(collection, devices: int, docs_per_device: int, batch: int) -> int:
    ops: list[InsertOne] = []
    written = 0
    for seq in range(docs_per_device):
        for d in range(devices):
            ops.append(InsertOne(make_reading(d, seq)))
            if len(ops) >= batch:
                collection.bulk_write(ops, ordered=False)
                written += len(ops)
                ops = []
    if ops:
        collection.bulk_write(ops, ordered=False)
        written += len(ops)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--devices", type=int, default=50, help="Number of distinct devices.")
    parser.add_argument("--docs-per-device", type=int, default=100, help="Readings per device per wave.")
    parser.add_argument("--batch", type=int, default=1000, help="Bulk write size.")
    parser.add_argument("--interval-ms", type=int, default=0, help="Delay between waves in continuous mode.")
    parser.add_argument("--continuous", action="store_true", help="Keep emitting waves until Ctrl+C.")
    parser.add_argument("--drop", action="store_true", help="Drop the collection before inserting.")
    args = parser.parse_args()

    collection = get_collection(COLLECTION, drop=args.drop)
    ensure_index(collection, CURSOR_FIELD)

    wave = 0
    total = 0
    try:
        while True:
            wave += 1
            written = write_wave(collection, args.devices, args.docs_per_device, args.batch)
            total += written
            print(f"Wave {wave}: wrote {written} readings (session total {total}).")
            if not args.continuous:
                break
            if args.interval_ms:
                time.sleep(args.interval_ms / 1000.0)
    except KeyboardInterrupt:
        print(f"\nStopped. Session total {total} readings.")

    print(f"Collection '{COLLECTION}' now holds {collection.count_documents({})} documents.")


if __name__ == "__main__":
    main()
