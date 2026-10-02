#!/usr/bin/env python3
"""Step 4 - Modify live tables (control plane) and close the loop with the MCP server.

A new requirement arrives: "List everything a plant produced in a date range"
(pattern #13). This script shows the DynamoDB side of that change:

  1. UpdateTable - add a GSI `ByPlant` (plant_code, produced_at) online.
     DynamoDB backfills the index from existing items; we wait until ACTIVE.
  2. Query the new GSI with a sort-key range (BETWEEN on ISO timestamps).
  3. UpdateTimeToLive - enable TTL on ScaniaVehicles (`expires_at`) so that,
     e.g., temporary diagnostic events can age out automatically.
  4. DescribeTable - show what changed.
  5. Optional: --remove-gsi deletes ByPlant again (one GSI change per UpdateTable call).

Closing the loop with the MCP server (do this in Kiro afterwards):
  • Add pattern #13 + the ByPlant GSI to dynamodb_data_model.md, then ask Kiro to
    re-run `compute_performances_and_costs` -> see how every write now also pays
    for a third index.
  • Add the GSI + a Query to dynamodb_data_model.json and re-run
    `dynamodb_data_model_validation`.
  • Re-run `dynamodb_data_model_schema_converter` / `generate_data_access_layer`
    to get a typed `list_components_by_plant()` repository method.

Usage:
    python3 04_modify_table.py            # add GSI + TTL
    python3 04_modify_table.py --remove-gsi
"""
import sys

from boto3.dynamodb.conditions import Key

from common import (
    COMPONENTS_TABLE,
    VEHICLES_TABLE,
    banner,
    describe_target,
    dump,
    dynamodb_client,
    dynamodb_resource,
    show_capacity,
    step,
    wait_for_table,
)

NEW_GSI = "ByPlant"


def add_plant_gsi(client) -> None:
    step(f"1) UpdateTable - add GSI {NEW_GSI} (plant_code, produced_at) to {COMPONENTS_TABLE}")
    existing = {g["IndexName"] for g in client.describe_table(TableName=COMPONENTS_TABLE)["Table"].get("GlobalSecondaryIndexes", [])}
    if NEW_GSI in existing:
        print(f"   ℹ️  {NEW_GSI} already exists - skipping")
        return
    client.update_table(
        TableName=COMPONENTS_TABLE,
        # New key attributes must be declared here; existing ones are kept automatically
        AttributeDefinitions=[
            {"AttributeName": "plant_code", "AttributeType": "S"},
            {"AttributeName": "produced_at", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexUpdates=[
            {
                "Create": {
                    "IndexName": NEW_GSI,
                    "KeySchema": [
                        {"AttributeName": "plant_code", "KeyType": "HASH"},
                        {"AttributeName": "produced_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "INCLUDE", "NonKeyAttributes": ["component_type", "batch_id", "status"]},
                }
            }
        ],
    )
    print("   ⏳ backfilling index (seconds locally, minutes-to-hours on AWS for big tables) ...")
    desc = wait_for_table(client, COMPONENTS_TABLE)
    print("   ✅ GSIs now:", [g["IndexName"] for g in desc["GlobalSecondaryIndexes"]])


def query_plant_gsi(ddb) -> None:
    step("2) Query ByPlant - everything Tucumán produced on 2026-10-01 (sort-key BETWEEN)")
    resp = ddb.Table(COMPONENTS_TABLE).query(
        IndexName=NEW_GSI,
        KeyConditionExpression=Key("plant_code").eq("TUC")
        & Key("produced_at").between("2026-10-01T00:00:00Z", "2026-10-01T23:59:59Z"),
        ReturnConsumedCapacity="INDEXES",
    )
    show_capacity(resp)
    print(f"   -> {resp['Count']} components; first 3:")
    for it in resp["Items"][:3]:
        print(f"   {it['produced_at']}  {it['serial_number']}  {it['component_type']}  {it['status']}")


def enable_ttl(client) -> None:
    step(f"3) UpdateTimeToLive - enable TTL attribute `expires_at` on {VEHICLES_TABLE}")
    current = client.describe_time_to_live(TableName=VEHICLES_TABLE)["TimeToLiveDescription"]
    if current.get("TimeToLiveStatus") in ("ENABLED", "ENABLING"):
        print(f"   ℹ️  TTL already {current['TimeToLiveStatus']} on `{current.get('AttributeName')}`")
        return
    resp = client.update_time_to_live(
        TableName=VEHICLES_TABLE,
        TimeToLiveSpecification={"Enabled": True, "AttributeName": "expires_at"},
    )
    print("   ✅", dump(resp["TimeToLiveSpecification"]))
    print("   💡 items with a numeric epoch-seconds `expires_at` in the past are deleted within ~48 h, free of WCU")


def describe(client) -> None:
    step("4) DescribeTable - the table after the changes")
    desc = client.describe_table(TableName=COMPONENTS_TABLE)["Table"]
    summary = {
        "TableStatus": desc["TableStatus"],
        "ItemCount": desc.get("ItemCount"),
        "BillingMode": desc.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED"),
        "GlobalSecondaryIndexes": [
            {"IndexName": g["IndexName"], "Keys": [k["AttributeName"] for k in g["KeySchema"]], "Projection": g["Projection"]["ProjectionType"], "Status": g["IndexStatus"]}
            for g in desc.get("GlobalSecondaryIndexes", [])
        ],
    }
    print(dump(summary))


def remove_plant_gsi(client) -> None:
    step(f"UpdateTable - delete GSI {NEW_GSI}")
    client.update_table(
        TableName=COMPONENTS_TABLE,
        GlobalSecondaryIndexUpdates=[{"Delete": {"IndexName": NEW_GSI}}],
    )
    desc = wait_for_table(client, COMPONENTS_TABLE)
    print("   ✅ GSIs now:", [g["IndexName"] for g in desc.get("GlobalSecondaryIndexes", [])])


def main() -> None:
    banner("04 - Modify tables: add GSI, query it, enable TTL")
    describe_target()
    client = dynamodb_client()
    ddb = dynamodb_resource()

    if "--remove-gsi" in sys.argv:
        remove_plant_gsi(client)
        return

    add_plant_gsi(client)
    query_plant_gsi(ddb)
    enable_ttl(client)
    describe(client)
    print("\nNow go back to Kiro and ask it to re-run compute_performances_and_costs with the ByPlant GSI.")
    print("Next: python3 05_cleanup.py --yes")


if __name__ == "__main__":
    main()
