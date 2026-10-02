#!/usr/bin/env python3
"""Step 1 - Create the tables exactly as the MCP server validated them.

MCP tools involved *before* this script runs:
  • dynamodb_data_modeling          -> dynamodb_requirement.md, dynamodb_data_model.md
  • compute_performances_and_costs  -> cost report appended to dynamodb_data_model.md
  • dynamodb_data_model_validation  -> consumes dynamodb_data_model.json (tables/items/patterns)

This script reads the SAME dynamodb_data_model.json and passes each table
definition to boto3 `create_table(**definition)`. No hand-written key schema:
if the model changes, re-validate with the MCP tool and re-run this script.

Usage:
    export AWS_ENDPOINT_URL_DYNAMODB=http://localhost:8000   # or unset for AWS
    python3 01_create_tables.py
"""
from common import (
    banner,
    describe_target,
    dump,
    dynamodb_client,
    step,
    table_definitions,
    wait_for_table,
)


def main() -> None:
    banner("01 - Create tables from dynamodb_data_model.json")
    describe_target()
    client = dynamodb_client()

    for definition in table_definitions():
        name = definition["TableName"]
        step(f"CreateTable {name}")
        print(dump({k: v for k, v in definition.items() if k != "TableName"}))
        try:
            client.create_table(**definition)
            print(f"   ⏳ creating {name} ...")
        except client.exceptions.ResourceInUseException:
            print(f"   ℹ️  {name} already exists - skipping create")

        desc = wait_for_table(client, name)
        gsis = [g["IndexName"] for g in desc.get("GlobalSecondaryIndexes", [])]
        print(
            f"   ✅ {name} is {desc['TableStatus']} | "
            f"billing={desc.get('BillingModeSummary', {}).get('BillingMode', 'PROVISIONED')} | "
            f"GSIs={gsis or '-'}"
        )

    step("ListTables")
    print(dump(client.list_tables()["TableNames"]))
    print("\nNext: python3 02_populate.py")


if __name__ == "__main__":
    main()
