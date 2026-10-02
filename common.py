"""Shared helpers for the Scania component-traceability DynamoDB demo.

Every numbered script imports this module. It does three things:

1. Builds a boto3 DynamoDB resource/client that works against *either*
   DynamoDB Local or real AWS, driven by one environment variable:

       export AWS_ENDPOINT_URL_DYNAMODB=http://localhost:8000   # DynamoDB Local
       unset  AWS_ENDPOINT_URL_DYNAMODB                         # real AWS

   boto3 honours AWS_ENDPOINT_URL_DYNAMODB natively, so the generated data
   access layer (dynamodb_schema/generated_dal) uses the same switch.

2. Loads the table definitions and sample items from `dynamodb_data_model.json`,
   the file the MCP server's `dynamodb_data_model_validation` tool consumes.
   The scripts therefore create exactly the tables the MCP tools validated.

3. Provides small printing helpers so students can see request/response
   shapes (incl. consumed capacity) without wading through boto3 noise.
"""
from __future__ import annotations

import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.config import Config

HERE = Path(__file__).resolve().parent
MODEL_JSON = HERE / "dynamodb_data_model.json"

COMPONENTS_TABLE = "ScaniaComponents"
VEHICLES_TABLE = "ScaniaVehicles"

_deserializer = TypeDeserializer()


# --------------------------------------------------------------------------- #
# Connection
# --------------------------------------------------------------------------- #
def endpoint_url() -> str | None:
    """Return the DynamoDB endpoint override, or None for real AWS."""
    return os.getenv("AWS_ENDPOINT_URL_DYNAMODB") or None


def is_local() -> bool:
    url = endpoint_url() or ""
    return "localhost" in url or "127.0.0.1" in url


def _session() -> boto3.session.Session:
    # DynamoDB Local accepts any credentials, but boto3 still insists on having some.
    if is_local():
        os.environ.setdefault("AWS_ACCESS_KEY_ID", "local")
        os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "local")
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    return boto3.session.Session()


def dynamodb_resource():
    """High-level resource API (Table objects, Python types, batch_writer)."""
    return _session().resource(
        "dynamodb",
        endpoint_url=endpoint_url(),
        config=Config(retries={"max_attempts": 5, "mode": "standard"}),
    )


def dynamodb_client():
    """Low-level client API (raw DynamoDB JSON, control-plane calls)."""
    return _session().client(
        "dynamodb",
        endpoint_url=endpoint_url(),
        config=Config(retries={"max_attempts": 5, "mode": "standard"}),
    )


def describe_target() -> None:
    target = endpoint_url() or "AWS (region %s)" % _session().region_name
    print(f"🎯 DynamoDB target: {target}")


# --------------------------------------------------------------------------- #
# Model file (produced/validated by the MCP server)
# --------------------------------------------------------------------------- #
def load_model() -> dict:
    if not MODEL_JSON.exists():
        sys.exit(f"{MODEL_JSON} not found - run the dynamodb_data_model_validation MCP tool first")
    with MODEL_JSON.open() as fh:
        return json.load(fh)


def table_definitions() -> list[dict]:
    """boto3 create_table kwargs, straight from dynamodb_data_model.json."""
    return load_model()["tables"]


def sample_items() -> dict[str, list[dict]]:
    """Sample items per table, converted from DynamoDB JSON to Python types."""
    out: dict[str, list[dict]] = {}
    for table_name, requests in load_model()["items"].items():
        out[table_name] = [
            {k: _deserializer.deserialize(v) for k, v in req["PutRequest"]["Item"].items()}
            for req in requests
        ]
    return out


# --------------------------------------------------------------------------- #
# Waiting / printing
# --------------------------------------------------------------------------- #
def wait_for_table(client, table_name: str, status: str = "ACTIVE", timeout: int = 120) -> dict:
    """Poll DescribeTable until the table (and all GSIs) reach `status`."""
    deadline = time.time() + timeout
    while True:
        desc = client.describe_table(TableName=table_name)["Table"]
        gsi_status = {g["IndexName"]: g["IndexStatus"] for g in desc.get("GlobalSecondaryIndexes", [])}
        if desc["TableStatus"] == status and all(s == "ACTIVE" for s in gsi_status.values()):
            return desc
        if time.time() > deadline:
            raise TimeoutError(f"{table_name} did not reach {status} (table={desc['TableStatus']}, gsis={gsi_status})")
        time.sleep(1)


def wait_for_table_gone(client, table_name: str, timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            client.describe_table(TableName=table_name)
        except client.exceptions.ResourceNotFoundException:
            return
        time.sleep(1)
    raise TimeoutError(f"{table_name} still exists after {timeout}s")


class _DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o == o.to_integral_value() else float(o)
        if isinstance(o, set):
            return sorted(o)
        return super().default(o)


def dump(obj) -> str:
    return json.dumps(obj, indent=2, cls=_DecimalEncoder, ensure_ascii=False)


def banner(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def step(title: str) -> None:
    print(f"\n--- {title}")


def show_capacity(response: dict, label: str = "") -> None:
    """Print ConsumedCapacity so students can compare with the MCP cost report."""
    cap = response.get("ConsumedCapacity")
    if not cap:
        return
    caps = cap if isinstance(cap, list) else [cap]
    for c in caps:
        units = c.get("CapacityUnits")
        extra = ""
        if "GlobalSecondaryIndexes" in c:
            extra = "  GSIs: " + ", ".join(f"{k}={v['CapacityUnits']}" for k, v in c["GlobalSecondaryIndexes"].items())
        print(f"   ⚡ {label}consumed {units} capacity units on {c.get('TableName')}{extra}")
