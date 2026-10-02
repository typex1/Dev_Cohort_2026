#!/usr/bin/env python3
"""Step 2 - Populate the tables.

Two sources of data:

  a) The sample items from dynamodb_data_model.json - the exact rows the
     `dynamodb_data_model_validation` MCP tool inserted into DynamoDB Local.
     They are stored as DynamoDB JSON ({"S": "..."}), so common.sample_items()
     deserialises them to plain Python before the resource API writes them.

  b) A synthetic "plant shift": 25 gearboxes from Tucumán in one batch.
     This is access pattern #12 (BatchWriteItem). boto3's `batch_writer()`
     chunks to 25 items per request and retries UnprocessedItems for you -
     compare with the raw `batch_write_item` call in the MCP validation JSON.

Usage:
    python3 02_populate.py
"""
from datetime import datetime, timedelta, timezone

from common import (
    COMPONENTS_TABLE,
    VEHICLES_TABLE,
    banner,
    describe_target,
    dynamodb_resource,
    sample_items,
    step,
)

SHIFT_BATCH = "GBX-2026-W40-S1"  # one Tucumán gearbox shift


def write_sample_items(ddb) -> None:
    step("a) Sample items from dynamodb_data_model.json (batch_writer)")
    for table_name, items in sample_items().items():
        table = ddb.Table(table_name)
        with table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)
        print(f"   ✅ {len(items):2d} items -> {table_name}")


def write_plant_shift(ddb) -> None:
    step(f"b) Access pattern #12 - bulk-register a shift ({SHIFT_BATCH}) via BatchWriteItem")
    table = ddb.Table(COMPONENTS_TABLE)
    start = datetime(2026, 10, 1, 5, 0, tzinfo=timezone.utc)
    items = [
        {
            "serial_number": f"GBX-TUC-{10000 + i:06d}",
            "component_type": "GEARBOX",
            "plant_code": "TUC",
            "batch_id": SHIFT_BATCH,
            "produced_at": (start + timedelta(minutes=3 * i)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "PRODUCED",  # no vin -> NOT in the sparse ByVehicle GSI
            "version": 1,
        }
        for i in range(25)
    ]
    # overwrite_by_pkeys de-duplicates within the batch; DynamoDB rejects duplicate keys per request
    with table.batch_writer(overwrite_by_pkeys=["serial_number"]) as batch:
        for item in items:
            batch.put_item(Item=item)
    print(f"   ✅ {len(items)} PRODUCED gearboxes written (one 25-item BatchWriteItem under the hood)")


def summarize(ddb) -> None:
    step("Item counts (Scan with Select=COUNT - fine for a demo, never for production access patterns)")
    for name in (COMPONENTS_TABLE, VEHICLES_TABLE):
        count = ddb.Table(name).scan(Select="COUNT")["Count"]
        print(f"   {name}: {count} items")


def main() -> None:
    banner("02 - Populate tables")
    describe_target()
    ddb = dynamodb_resource()
    write_sample_items(ddb)
    write_plant_shift(ddb)
    summarize(ddb)
    print("\nNext: python3 03_read_write.py")


if __name__ == "__main__":
    main()
