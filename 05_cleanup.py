#!/usr/bin/env python3
"""Step 5 - Delete the demo tables.

DeleteTable removes the table, all items and all GSIs in one call (TTL settings
go with it). On AWS, on-demand tables cost nothing when empty, but deleting
keeps the account tidy between cohort sessions.

Usage:
    python3 05_cleanup.py          # asks for confirmation
    python3 05_cleanup.py --yes    # no prompt
"""
import sys

from common import (
    banner,
    describe_target,
    dynamodb_client,
    is_local,
    step,
    table_definitions,
    wait_for_table_gone,
)


def main() -> None:
    banner("05 - Cleanup")
    describe_target()
    names = [t["TableName"] for t in table_definitions()]

    if "--yes" not in sys.argv and not is_local():
        answer = input(f"Delete {names} in AWS? type 'yes' to continue: ")
        if answer.strip().lower() != "yes":
            print("aborted")
            return

    client = dynamodb_client()
    for name in names:
        step(f"DeleteTable {name}")
        try:
            client.delete_table(TableName=name)
            wait_for_table_gone(client, name)
            print(f"   ✅ {name} deleted")
        except client.exceptions.ResourceNotFoundException:
            print(f"   ℹ️  {name} did not exist")

    print("\nRemaining tables:", client.list_tables()["TableNames"])


if __name__ == "__main__":
    main()
