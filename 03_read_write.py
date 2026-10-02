#!/usr/bin/env python3
"""Step 3 - Walk through access patterns #1-#11 with boto3.

Each function below is ONE row of the "Access Pattern Mapping" table in
dynamodb_data_model.md. The `dynamodb_data_model_validation` MCP tool ran the
same patterns as AWS CLI commands; here they are as boto3 resource calls so
students can compare the two syntaxes side by side.

ReturnConsumedCapacity="INDEXES" is set on every call so the printed capacity
units can be compared with the "Cost Report" the `compute_performances_and_costs`
MCP tool appended to dynamodb_data_model.md (e.g. a PutItem that touches a GSI
costs 1 WCU on the table AND 1 WCU on the index).

Usage:
    python3 03_read_write.py
"""
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key

from common import (
    COMPONENTS_TABLE,
    VEHICLES_TABLE,
    banner,
    describe_target,
    dump,
    dynamodb_resource,
    sample_items,
    show_capacity,
    step,
)

CC = {"ReturnConsumedCapacity": "INDEXES"}

NEW_SERIAL = "GBX-TUC-000199"
NEW_VIN = "9BSR4X20005399499"  # Brazil-built (WMI 9BS) truck


# ----------------------------------------------------------------------------- Components
def p1_register_component(components) -> None:
    step("#1 PutItem - register a produced component (idempotent via attribute_not_exists)")
    item = {
        "serial_number": NEW_SERIAL,
        "component_type": "GEARBOX",
        "plant_code": "TUC",
        "batch_id": "GBX-2026-W38-A",
        "produced_at": "2026-09-14T09:00:00Z",
        "status": "PRODUCED",
        "version": 1,
    }
    resp = components.put_item(
        Item=item, ConditionExpression="attribute_not_exists(serial_number)", **CC
    )
    show_capacity(resp)
    print(f"   ✅ registered {NEW_SERIAL}")

    # Second registration of the same serial must fail - show the exception students will meet
    try:
        components.put_item(Item=item, ConditionExpression="attribute_not_exists(serial_number)")
    except ClientError as e:
        print(f"   🔁 retry rejected as expected: {e.response['Error']['Code']}")


def p2_get_component(components) -> None:
    step("#2 GetItem - look up a component by serial number")
    resp = components.get_item(Key={"serial_number": "GBX-TUC-000101"}, **CC)
    show_capacity(resp)
    print(dump(resp.get("Item")))


def p3_install_component(components) -> None:
    step("#3 UpdateItem - install component into a vehicle (condition: status = PRODUCED)")
    resp = components.update_item(
        Key={"serial_number": NEW_SERIAL},
        UpdateExpression="SET vin = :vin, installed_at = :ts, #s = :installed, version = version + :one",
        ConditionExpression="#s = :produced",
        ExpressionAttributeNames={"#s": "status"},  # 'status' is a reserved word
        ExpressionAttributeValues={
            ":vin": NEW_VIN,
            ":ts": "2026-10-02T08:30:00Z",
            ":installed": "INSTALLED",
            ":produced": "PRODUCED",
            ":one": 1,
        },
        ReturnValues="ALL_NEW",
        **CC,
    )
    show_capacity(resp)
    print("   ✅ now:", dump(resp["Attributes"]))
    print("   💡 setting `vin` made this item appear in the sparse ByVehicle GSI (see GSI capacity above)")


def p4_components_by_vehicle(components) -> None:
    step("#4 Query ByVehicle GSI - bill of materials for one VIN")
    resp = components.query(
        IndexName="ByVehicle", KeyConditionExpression=Key("vin").eq("YS2R4X20005399401"), **CC
    )
    show_capacity(resp)
    for it in resp["Items"]:
        print(f"   {it['component_type']:8s} {it['serial_number']}  plant={it['plant_code']} batch={it['batch_id']}")
    print(f"   -> {resp['Count']} items; only INCLUDE-projected attributes came back (no status/produced_at)")


def p5_recall_by_batch(components) -> None:
    step("#5 Query ByBatch GSI - recall: every component of a batch and where it ended up")
    batch_id = "GBX-2026-W38-A"
    items, start_key = [], None
    while True:  # pagination loop - a real batch has ~200 items
        kwargs = {"IndexName": "ByBatch", "KeyConditionExpression": Key("batch_id").eq(batch_id), **CC}
        if start_key:
            kwargs["ExclusiveStartKey"] = start_key
        resp = components.query(**kwargs)
        show_capacity(resp)
        items.extend(resp["Items"])
        start_key = resp.get("LastEvaluatedKey")
        if not start_key:
            break
    for it in items:
        print(f"   {it['serial_number']}  {it['status']:11s}  vin={it.get('vin', '-')}")
    affected = sorted({it["vin"] for it in items if "vin" in it})
    print(f"   -> batch {batch_id}: {len(items)} components, {len(affected)} vehicles affected: {affected}")


def p6_quarantine_with_optimistic_lock(components) -> None:
    step("#6 UpdateItem - quarantine with optimistic locking on `version`")
    serial = "GBX-TUC-000102"
    current = components.get_item(Key={"serial_number": serial})["Item"]
    expected = current["version"]

    def quarantine(expected_version):
        return components.update_item(
            Key={"serial_number": serial},
            UpdateExpression="SET #s = :q, version = :new",
            ConditionExpression="version = :cur",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":q": "QUARANTINED", ":cur": expected_version, ":new": expected_version + 1},
            ReturnValues="ALL_NEW",
            **CC,
        )

    resp = quarantine(expected)
    show_capacity(resp)
    print(f"   ✅ {serial} -> {resp['Attributes']['status']} (version {expected} -> {resp['Attributes']['version']})")

    # A second writer still holding the OLD version loses:
    try:
        quarantine(expected)
    except ClientError as e:
        print(f"   🔒 stale writer rejected: {e.response['Error']['Code']} (lost-update prevented)")


# ----------------------------------------------------------------------------- Vehicles
def p7_create_vehicle(vehicles) -> None:
    step("#7 PutItem - create vehicle profile (sk = PROFILE)")
    resp = vehicles.put_item(
        Item={"vin": NEW_VIN, "sk": "PROFILE", "model": "P 280", "assembly_plant": "SBC", "build_date": "2026-10-02"},
        ConditionExpression="attribute_not_exists(vin)",
        **CC,
    )
    show_capacity(resp)
    print(f"   ✅ profile created for {NEW_VIN}")


def p8_get_vehicle(vehicles) -> None:
    step("#8 GetItem - vehicle profile (composite key vin + sk)")
    resp = vehicles.get_item(Key={"vin": "YS2R4X20005399401", "sk": "PROFILE"}, **CC)
    show_capacity(resp)
    print(dump(resp["Item"]))


def p9_record_service_event(vehicles) -> None:
    step("#9 PutItem - record a workshop visit (sk = SERVICE#<ts>#<event_id>)")
    ts, event_id = "2026-12-20T14:00:00Z", "EVT-0004"
    resp = vehicles.put_item(
        Item={
            "vin": "YS2R4X20005399401",
            "sk": f"SERVICE#{ts}#{event_id}",
            "event_id": event_id,
            "service_date": ts,
            "mileage_km": 31900,
            "workshop": "Scania Malmö",
            "description": "Brake pad replacement",
        },
        **CC,
    )
    show_capacity(resp)
    print("   ✅ EVT-0004 written")


def p10_service_history(vehicles) -> None:
    step("#10 Query - service history newest first (begins_with + ScanIndexForward=False)")
    resp = vehicles.query(
        KeyConditionExpression=Key("vin").eq("YS2R4X20005399401") & Key("sk").begins_with("SERVICE#"),
        ScanIndexForward=False,
        Limit=20,
        **CC,
    )
    show_capacity(resp)
    for it in resp["Items"]:
        print(f"   {it['service_date']}  {it['mileage_km']:>7} km  {it['workshop']:22s} {it['description']}")


def p11_latest_service_event(vehicles) -> None:
    step("#11 Query - latest service event (same query, Limit=1)")
    resp = vehicles.query(
        KeyConditionExpression=Key("vin").eq("YS2R4X20005399401") & Key("sk").begins_with("SERVICE#"),
        ScanIndexForward=False,
        Limit=1,
        **CC,
    )
    show_capacity(resp)
    print(dump(resp["Items"][0]))


def reset_demo_state(components, vehicles) -> None:
    """Make the script re-runnable: remove what it creates, restore what it mutates.

    DeleteItem is idempotent (deleting a missing item succeeds), and re-putting
    the sample rows from dynamodb_data_model.json resets GBX-TUC-000102 from
    QUARANTINED back to PRODUCED/version 1 for the optimistic-locking demo.
    """
    step("reset - DeleteItem leftovers from a previous run, restore sample items")
    components.delete_item(Key={"serial_number": NEW_SERIAL})
    vehicles.delete_item(Key={"vin": NEW_VIN, "sk": "PROFILE"})
    vehicles.delete_item(Key={"vin": "YS2R4X20005399401", "sk": "SERVICE#2026-12-20T14:00:00Z#EVT-0004"})
    for table_name, items in sample_items().items():
        table = components if table_name == COMPONENTS_TABLE else vehicles
        with table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)
    print("   ✅ clean slate")


def main() -> None:
    banner("03 - Read / write: access patterns #1-#11")
    describe_target()
    ddb = dynamodb_resource()
    components = ddb.Table(COMPONENTS_TABLE)
    vehicles = ddb.Table(VEHICLES_TABLE)

    reset_demo_state(components, vehicles)
    p1_register_component(components)
    p2_get_component(components)
    p3_install_component(components)
    p4_components_by_vehicle(components)
    p5_recall_by_batch(components)
    p6_quarantine_with_optimistic_lock(components)
    p7_create_vehicle(vehicles)
    p8_get_vehicle(vehicles)
    p9_record_service_event(vehicles)
    p10_service_history(vehicles)
    p11_latest_service_event(vehicles)

    print("\nNext: python3 04_modify_table.py")


if __name__ == "__main__":
    main()
