# DynamoDB + the AWS DynamoDB MCP Server - Scania component traceability demo

A worked example of using the **awslabs DynamoDB MCP server** from Kiro, end to end:
model a DynamoDB design, cost it, validate it against DynamoDB Local, generate CDK and a
Python data access layer - and then drive the resulting tables with plain boto3.

Use case: traceability for Scania's modular production system. Serialised components
(gearboxes from Tucumán, cabs from Oskarshamn, frames from Luleå, engines from Södertälje)
are registered, installed into vehicles (VINs), and must be found by batch during a recall.
Workshops log service events per VIN.

## First thing to understand

The DynamoDB MCP server is **not** a CRUD server. It has no `put_item` or `query` tool.
It is a *design-time* assistant: most of its tools return long expert prompts that Kiro then
follows, and a few tools do real work (cost math, running your access patterns against
DynamoDB Local, generating a CDK app and Python code). Your application code still talks to
DynamoDB with boto3 - that is what the numbered scripts here do.

| MCP tool | What it really does | Artifact in this folder |
|----------|---------------------|-------------------------|
| `dynamodb_data_modeling` | Returns a ~50 KB expert prompt (requirements → design workflow, design patterns) | `dynamodb_requirement.md`, `dynamodb_data_model.md` |
| `compute_performances_and_costs` | **Does math**: RCU/WCU per pattern, monthly $ incl. GSI write amplification; appends a report to the model file | "Cost Report" section at the end of `dynamodb_data_model.md` |
| `dynamodb_data_model_validation` | 1st call without JSON: returns the JSON generation guide. 2nd call: **starts DynamoDB Local in Docker, creates tables, loads items, executes every access pattern's AWS CLI command** | `dynamodb_data_model.json` (input), `dynamodb_model_validation.json` + `.md` (output) |
| `generate_resources` (cdk) | **Writes a CDK TypeScript app** (`TableV2` + GSIs) from `dynamodb_data_model.json`, runs `npm install` | `cdk/` |
| `dynamodb_data_model_schema_converter` | Returns the prompt for turning the model markdown into `schema.json` (+ `usage_data.json`) | `dynamodb_schema/schema.json`, `dynamodb_schema/usage_data.json` |
| `dynamodb_data_model_schema_validator` | **Validates** `schema.json` (+ usage data) structurally; warns about projection gaps | validator output (see "Gotchas") |
| `generate_data_access_layer` | **Generates** Pydantic entities + repository skeletons + runnable examples, then instructs Kiro to implement the TODO methods | `dynamodb_schema/generated_dal/` |
| `source_db_analyzer` | Extracts schema/query patterns from an existing MySQL/PostgreSQL/SQL Server/Oracle DB | not used here (no source DB) |

## Folder map

```
DynamoDB/
├── README.md                        <- you are here
├── dynamodb_requirement.md          Phase 1 of the modeling prompt: use case + 12 access patterns
├── dynamodb_data_model.md           Phase 2: table/GSI design, pattern mapping, + MCP cost report
├── dynamodb_data_model.json         Tables (boto3 create_table format), sample items, CLI per pattern
├── dynamodb_model_validation.json   Raw results of the MCP validation run against DynamoDB Local
├── dynamodb_model_validation.md     Human-readable validation report (12/12 patterns passed)
├── cdk/                             Generated CDK app (npx cdk synth verified)
├── dynamodb_schema/
│   ├── schema.json                  Code-generation schema (validated)
│   ├── usage_data.json              Sample values used by the generated examples
│   └── generated_dal/               entities.py, base_repository.py, repositories.py, usage_examples.py
├── common.py                        boto3 session (Local or AWS), loads dynamodb_data_model.json
├── 01_create_tables.py              CreateTable from the validated JSON, wait for ACTIVE
├── 02_populate.py                   batch_writer: sample items + a 25-item plant shift (pattern #12)
├── 03_read_write.py                 Patterns #1-#11 in boto3, with consumed capacity printed
├── 04_modify_table.py               UpdateTable (add GSI online), Query it, enable TTL, DescribeTable
├── 05_cleanup.py                    DeleteTable
├── run_local.sh                     Spins up DynamoDB Local and runs everything
└── requirements.txt
```

## The data model in one screen

**ScaniaComponents** - PK `serial_number`
- `ByVehicle` GSI (`vin`, `serial_number`) INCLUDE component_type, plant_code, batch_id, installed_at - **sparse**: only installed components have a `vin`
- `ByBatch` GSI (`batch_id`, `serial_number`) INCLUDE component_type, status, vin - the recall index

**ScaniaVehicles** - PK `vin`, SK `sk` (item collection)
- `PROFILE` - the vehicle master record
- `SERVICE#<ISO timestamp>#<event_id>` - one item per workshop visit, sorts chronologically

Twelve access patterns, no Scans. Full justification in `dynamodb_data_model.md`.

## Run it

### A. Locally (no AWS account needed)

```bash
cd DynamoDB
pip install -r requirements.txt     # boto3, pydantic
./run_local.sh                      # docker: amazon/dynamodb-local on :8001, then 01→04 + generated DAL
./run_local.sh cleanup              # 05_cleanup.py + remove the container
```

### B. Against your AWS account

```bash
unset AWS_ENDPOINT_URL_DYNAMODB     # common.py then uses your normal credentials/region
python3 01_create_tables.py
python3 02_populate.py
python3 03_read_write.py
python3 04_modify_table.py          # adding a GSI on AWS takes minutes; TTL enabling is async
python3 05_cleanup.py               # asks for confirmation
```

Or deploy the generated CDK app instead of step 01:

```bash
cd cdk && npx cdk bootstrap && npx cdk deploy
```

Note the CDK stack uses `TableV2` **without** an explicit `tableName`, so CloudFormation
generates physical names (see the stack outputs). The boto3 scripts expect
`ScaniaComponents` / `ScaniaVehicles` - either add `tableName:` in `cdk/lib/cdk-stack.ts`
or point the scripts at the output names. Good discussion point: generated names vs.
fixed names and why CDK defaults to generated.

## What each script teaches

| Script | DynamoDB API surface | Watch for |
|--------|---------------------|-----------|
| `01_create_tables.py` | `create_table(**definition)`, `describe_table`, waiting for table **and** GSI status | The definition is the very JSON the MCP tool validated - no duplicated key schema |
| `02_populate.py` | `Table.batch_writer()` (25-item chunking + UnprocessedItems retry for free), DynamoDB-JSON → Python via `TypeDeserializer` | The 25 PRODUCED gearboxes have no `vin` → they never enter the sparse `ByVehicle` GSI |
| `03_read_write.py` | `put_item` + `attribute_not_exists`, `get_item`, `update_item` with `ConditionExpression`, GSI `query`, pagination with `LastEvaluatedKey`, optimistic locking on `version`, `begins_with` + `ScanIndexForward=False` + `Limit` | `ReturnConsumedCapacity="INDEXES"`: installing a component costs 1 WCU on the table **plus** 1 per GSI - exactly what the cost report's footnote ¹ describes |
| `04_modify_table.py` | `update_table` (GSI create/delete), `update_time_to_live`, `describe_time_to_live`, sort-key `between` on the new index | Only one GSI change per `update_table` call; new key attributes must be declared in `AttributeDefinitions` |
| `05_cleanup.py` | `delete_table`, waiting for ResourceNotFound | On-demand tables cost nothing when idle, but tidy up between cohorts |
| `generated_dal/usage_examples.py --all` | Repository pattern: Pydantic entities, `create/update` with version checks, raw-dict results for INCLUDE-projected GSIs | The generator emits **skeletons with TODOs**; the repository methods here were implemented by hand (look at `repositories.py`) |

## Reproduce the MCP workflow yourself (student exercise)

Open this folder in Kiro with the DynamoDB MCP server enabled and work through these prompts.
Each one should make Kiro call the tool named in brackets - check the tool-call panel.

1. "I want to design a DynamoDB model for component traceability at a truck manufacturer.
   Use the DynamoDB data modeling tool." → `dynamodb_data_modeling`. Answer its questions;
   it writes `dynamodb_requirement.md`, then `dynamodb_data_model.md`.
2. "Compute the capacity and cost for this model." → `compute_performances_and_costs`.
   Try changing an RPS value in the Access Pattern Mapping table and re-run; watch the GSI lines.
3. "Validate my data model." → `dynamodb_data_model_validation` twice: first it hands Kiro the
   JSON guide, then (after `dynamodb_data_model.json` exists) it runs the CLI commands in Docker.
   Break something on purpose (e.g. filter on a key attribute in a Query) and see it fail.
4. "Generate a CDK app." → `generate_resources` with `resource_type="cdk"`.
5. "Convert the model to schema.json and generate the Python data access layer." →
   `dynamodb_data_model_schema_converter` → `dynamodb_data_model_schema_validator` →
   `generate_data_access_layer`.
6. Extension: run `04_modify_table.py`, then add the `ByPlant` GSI and pattern #13
   ("components produced at a plant in a date range") to `dynamodb_data_model.md` and
   `dynamodb_data_model.json`, and repeat steps 2-5. Every artefact should pick up the change.

## Gotchas we hit (worth telling students)

- **DynamoDB Local namespaces data by access key + region** unless started with `-sharedDb`.
  The MCP validation container (`dynamodb-local-setup-for-data-model-validation`, port 8000)
  runs *without* `-sharedDb`, so a script using your real AWS profile sees "non-existent
  table" there even though the tables exist. `run_local.sh` starts its own container on
  port 8001 with `-sharedDb` and fixed dummy credentials to avoid this.
- The validation harness **paginates every Query to completion**, so pattern #11 (`--limit 1`)
  shows all events in `dynamodb_model_validation.json`. The CLI command itself is correct.
- `dynamodb_data_model_validation` cleans up its tables after the run. Don't expect data to
  be left behind for your scripts - create your own with `01_create_tables.py`.
- `schema_validator` warns when an INCLUDE projection lacks fields the entity marks
  `required`; the generated GSI query methods then return `list[dict]` instead of typed
  entities. That is a deliberate trade-off here (smaller index items) - see
  `list_components_by_vehicle()`.
- `generate_data_access_layer` does not finish the job: it leaves `# TODO` + `pass` in
  `repositories.py` and instructs the agent to implement them method by method. Review that
  code like any other PR - e.g. the generator suggests an *unconditional* PutItem for
  pattern #1; we made it conditional because re-registering a serial must never overwrite an
  installed component.
- `generated_dal/usage_examples.py` refuses to run unless `AWS_ENDPOINT_URL_DYNAMODB` points
  at localhost - a sensible guard, since it creates and deletes items.
- `generate_resources` runs `cdk init`, which creates a nested `.git/` inside `cdk/`.
  Remove it if this folder lives in a parent repository.
- The cost report is for us-east-1 on-demand pricing (Jan 2026). Scania would run in
  eu-north-1 - same order of magnitude, but re-check before quoting numbers.
