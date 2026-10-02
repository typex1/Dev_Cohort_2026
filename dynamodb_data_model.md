# DynamoDB Data Model

> Final deliverable of the `dynamodb_data_modeling` MCP tool workflow (Phase 2).
> The `compute_performances_and_costs` tool appends its capacity/cost analysis to the end
> of this file, and the `dynamodb_data_model_schema_converter` tool reads it to produce
> `schema.json`.

## Design Philosophy & Approach

Multi-table, aggregate-oriented design. Each table holds one aggregate whose items are
read together: a **vehicle and its service history**, and a **serialised component**.
Natural keys (`vin`, `serial_number`) replace generated IDs; GSIs exist only where an
access pattern genuinely needs a second lookup dimension (by VIN, by batch). No Scans.

## Aggregate Design Decisions

- **Vehicle aggregate** (`ScaniaVehicles`): profile + service events share the `vin`
  partition. Service events are only ever read in the context of a vehicle (identifying
  relationship, ~100 % access correlation), so co-locating them turns "get history" into a
  single bounded Query.
- **Component aggregate** (`ScaniaComponents`): components live before they are installed
  and are addressed by serial number at the assembly station. They are therefore a separate
  aggregate keyed by `serial_number`; the link to a vehicle is a plain attribute (`vin`)
  that a sparse GSI exposes for "components in this vehicle" and a second GSI exposes
  `batch_id` for recalls.

## Table Designs

### ScaniaComponents Table

| serial_number | component_type | plant_code | batch_id | produced_at | status | vin | installed_at |
| ------------- | -------------- | ---------- | -------- | ----------- | ------ | --- | ------------ |
| GBX-TUC-000101 | GEARBOX | TUC | GBX-2026-W38-A | 2026-09-14T06:12:00Z | INSTALLED | YS2R4X20005399401 | 2026-09-28T09:40:00Z |
| GBX-TUC-000102 | GEARBOX | TUC | GBX-2026-W38-A | 2026-09-14T06:15:00Z | PRODUCED | | |
| CAB-OSK-000201 | CAB | OSK | CAB-2026-W39-B | 2026-09-22T11:02:00Z | INSTALLED | YS2R4X20005399401 | 2026-09-28T08:05:00Z |
| FRM-LUL-000301 | FRAME | LUL | FRM-2026-W37-C | 2026-09-10T13:30:00Z | INSTALLED | YS2R4X20005399401 | 2026-09-28T07:15:00Z |
| ENG-SOD-000401 | ENGINE | SOD | ENG-2026-W38-D | 2026-09-16T15:45:00Z | INSTALLED | XLER4X20005399402 | 2026-09-29T10:00:00Z |
| GBX-TUC-000103 | GEARBOX | TUC | GBX-2026-W38-A | 2026-09-14T06:18:00Z | INSTALLED | XLER4X20005399402 | 2026-09-29T10:30:00Z |
| GBX-TUC-000104 | GEARBOX | TUC | GBX-2026-W38-A | 2026-09-14T06:21:00Z | QUARANTINED | | |

- **Purpose**: one item per serialised component, from production through installation and
  quality status. Chosen so the assembly scanner can resolve a serial in one GetItem.
- **Aggregate Boundary**: the component itself (type, origin plant, batch, timestamps,
  status, optional link to a VIN). Nothing else is co-located.
- **Partition Key**: `serial_number` (String) - globally unique, high cardinality, evenly
  distributed across plants. Not an identifying relationship: the component exists before
  any vehicle does.
- **Sort Key**: none - one item per component, no item collection needed.
- **SK Taxonomy**: n/a.
- **Attributes**: `serial_number` S, `component_type` S, `plant_code` S, `batch_id` S,
  `produced_at` S (ISO-8601), `status` S (PRODUCED | INSTALLED | QUARANTINED),
  `vin` S (absent until installed), `installed_at` S (absent until installed),
  `version` N (optimistic locking counter).
- **Bounded Read Strategy**: single-item reads only on the base table; bounded Queries on
  the GSIs (≤ 12 items per VIN, ≤ ~200 items per batch, paginate with LastEvaluatedKey).
- **Access Patterns Served**: #1, #2, #3, #6, #12 (base table); #4 (ByVehicle GSI);
  #5 (ByBatch GSI).
- **Capacity Planning**: ~1.2 M items × 500 B ≈ 600 MB. Reads 50 RPS, writes ~42 RPS.
  On-demand billing; traffic is bursty around shift ends.

| vin | serial_number | component_type | plant_code | batch_id | installed_at |
| --- | ------------- | -------------- | ---------- | -------- | ------------ |
| YS2R4X20005399401 | GBX-TUC-000101 | GEARBOX | TUC | GBX-2026-W38-A | 2026-09-28T09:40:00Z |
| YS2R4X20005399401 | CAB-OSK-000201 | CAB | OSK | CAB-2026-W39-B | 2026-09-28T08:05:00Z |
| YS2R4X20005399401 | FRM-LUL-000301 | FRAME | LUL | FRM-2026-W37-C | 2026-09-28T07:15:00Z |
| XLER4X20005399402 | ENG-SOD-000401 | ENGINE | SOD | ENG-2026-W38-D | 2026-09-29T10:00:00Z |
| XLER4X20005399402 | GBX-TUC-000103 | GEARBOX | TUC | GBX-2026-W38-A | 2026-09-29T10:30:00Z |

### ByVehicle GSI

- **Purpose**: "which components are installed in this VIN" (#4). Needed because the base
  table is keyed by serial, not by VIN.
- **Partition Key**: `vin` (String) - ~12 items per VIN, perfectly distributed.
- **Sort Key**: `serial_number` (String) - deterministic ordering; also makes the index key
  unique per component.
- **Multi-Attribute Key Decision**: single attributes suffice; no composite needed.
- **Projection**: INCLUDE `component_type`, `plant_code`, `batch_id`, `installed_at` -
  exactly what the bill-of-materials screen shows; keeps index items small.
  - **Per-Pattern Projected Attributes**: #4 → component_type, plant_code, batch_id,
    installed_at.
- **Sparse**: `vin` - only installed components carry a `vin`, so PRODUCED and
  QUARANTINED-before-install items never enter the index.
- **Access Patterns Served**: #4.
- **Capacity Planning**: 30 RPS Query, ~12 items × 300 B each.

| batch_id | serial_number | component_type | status | vin |
| -------- | ------------- | -------------- | ------ | --- |
| GBX-2026-W38-A | GBX-TUC-000101 | GEARBOX | INSTALLED | YS2R4X20005399401 |
| GBX-2026-W38-A | GBX-TUC-000102 | GEARBOX | PRODUCED | |
| GBX-2026-W38-A | GBX-TUC-000103 | GEARBOX | INSTALLED | XLER4X20005399402 |
| GBX-2026-W38-A | GBX-TUC-000104 | GEARBOX | QUARANTINED | |
| CAB-2026-W39-B | CAB-OSK-000201 | CAB | INSTALLED | YS2R4X20005399401 |

### ByBatch GSI

- **Purpose**: recall lookup - every component of a batch and, where installed, its VIN
  (#5).
- **Partition Key**: `batch_id` (String) - ~200 items per batch; thousands of batches per
  year, so distribution is fine and a single recall Query returns the whole batch in one or
  two pages.
- **Sort Key**: `serial_number` (String) - stable ordering for the recall report.
- **Multi-Attribute Key Decision**: single attributes; the batch ID already encodes
  type + week.
- **Projection**: INCLUDE `component_type`, `status`, `vin` - the recall report needs
  only these.
  - **Per-Pattern Projected Attributes**: #5 → component_type, status, vin.
- **Sparse**: not sparse - every component has a batch.
- **Access Patterns Served**: #5.
- **Capacity Planning**: 1 RPS, 200 items × 250 B. Negligible cost; worth it for recall speed.

### ScaniaVehicles Table

| vin | sk | model | assembly_plant | build_date | event_id | service_date | mileage_km | workshop | description |
| --- | -- | ----- | -------------- | ---------- | -------- | ------------ | ---------- | -------- | ----------- |
| YS2R4X20005399401 | PROFILE | R 560 | SOD | 2026-09-28 | | | | | |
| YS2R4X20005399401 | SERVICE#2026-10-01T08:00:00Z#EVT-0001 | | | | EVT-0001 | 2026-10-01T08:00:00Z | 1200 | Scania Kungens Kurva | Delivery inspection |
| YS2R4X20005399401 | SERVICE#2026-11-15T09:30:00Z#EVT-0002 | | | | EVT-0002 | 2026-11-15T09:30:00Z | 18450 | Scania Jönköping | First oil service |
| XLER4X20005399402 | PROFILE | S 500 | ZWO | 2026-09-29 | | | | | |
| XLER4X20005399402 | SERVICE#2026-10-03T10:00:00Z#EVT-0003 | | | | EVT-0003 | 2026-10-03T10:00:00Z | 800 | Scania Rotterdam | Delivery inspection |

- **Purpose**: vehicle master data plus its workshop history, readable with a single
  bounded Query per VIN.
- **Aggregate Boundary**: one VIN = one item collection containing exactly one `PROFILE`
  item and 0..n `SERVICE#...` items. Components are *not* here (see ScaniaComponents).
- **Partition Key**: `vin` (String) - natural key, 17 chars, globally unique; 100 k new
  partitions a year, no hot keys. Identifying relationship for service events.
- **Sort Key**: `sk` (String) - `PROFILE` or `SERVICE#<ISO timestamp>#<event_id>`;
  timestamps sort lexicographically, so `ScanIndexForward=False` gives newest first.
- **SK Taxonomy**: `PROFILE` (vehicle master record), `SERVICE#<ts>#<event_id>` (one per
  workshop visit).
- **Attributes**: `vin` S, `sk` S, `model` S, `assembly_plant` S, `build_date` S,
  `event_id` S, `service_date` S, `mileage_km` N, `workshop` S, `description` S.
- **Bounded Read Strategy**: `begins_with(sk, "SERVICE#")` with `Limit=20` newest first
  for history; `Limit=1` for latest event; profile via GetItem(vin, "PROFILE").
- **Access Patterns Served**: #7, #8, #9, #10, #11.
- **Capacity Planning**: ~1 M items (100 k profiles × 1 KB + 900 k events × 800 B)
  ≈ 820 MB. Reads 100 RPS, writes 15 RPS. On-demand billing.

## Access Pattern Mapping

### Solved Patterns

All 12 patterns are solved with GetItem/PutItem/UpdateItem/Query/BatchWriteItem; no Scans.

| Pattern # | Description | Type | Peak RPS | Items Returned | Avg Item Size | Table/GSI Used | DynamoDB Operations | Implementation Notes |
|-----------|-------------|------|----------|----------------|---------------|----------------|---------------------|----------------------|
| 1 | Register a produced component | PutItem | 20 | - | 0.5 KB | ScaniaComponents | PutItem(serial_number) with `attribute_not_exists(serial_number)` | Idempotent registration; status=PRODUCED, version=1 |
| 2 | Get component by serial number | GetItem | 50 | 1 | 0.5 KB | ScaniaComponents | GetItem(PK=serial_number) | Scanner lookup |
| 3 | Install component into vehicle | UpdateItem | 20 | - | 0.5 KB | ScaniaComponents | UpdateItem SET vin, installed_at, status=INSTALLED, version+1 with condition status=PRODUCED | Writes to both GSIs (item enters ByVehicle) |
| 4 | List components installed in a vehicle | Query | 30 | 12 | 0.3 KB | ByVehicle GSI | Query(PK=vin) | Sparse GSI; paginate if > 1 MB |
| 5 | Recall: all components of a batch | Query | 1 | 200 | 0.25 KB | ByBatch GSI | Query(PK=batch_id) | Filter on status is a non-key attribute; VIN present only for installed items |
| 6 | Quarantine a component | UpdateItem | 1 | - | 0.5 KB | ScaniaComponents | UpdateItem SET status=QUARANTINED, version+1 | Condition on expected version (optimistic locking) |
| 7 | Create vehicle profile | PutItem | 5 | - | 1 KB | ScaniaVehicles | PutItem(vin, sk=PROFILE) with `attribute_not_exists(vin)` | |
| 8 | Get vehicle profile | GetItem | 50 | 1 | 1 KB | ScaniaVehicles | GetItem(vin, sk=PROFILE) | |
| 9 | Record service event | PutItem | 10 | - | 0.8 KB | ScaniaVehicles | PutItem(vin, sk=SERVICE#ts#event_id) | |
| 10 | Service history newest first | Query | 30 | 20 | 0.8 KB | ScaniaVehicles | Query(PK=vin, begins_with(sk,"SERVICE#")), ScanIndexForward=False, Limit=20 | |
| 11 | Latest service event | Query | 20 | 1 | 0.8 KB | ScaniaVehicles | Query(PK=vin, begins_with(sk,"SERVICE#")), ScanIndexForward=False, Limit=1 | |
| 12 | Bulk-register a shift's components | BatchWriteItem | 1 | 25 | 0.5 KB | ScaniaComponents | BatchWriteItem (25 PutRequests) | Retry UnprocessedItems with backoff |

## Hot Partition Analysis

- **ScaniaComponents**: #2 at 50 RPS across 1.2 M serials → effectively 0 RPS per partition. ✅
- **ByVehicle GSI**: writes concentrate on the ~12 VINs currently on the assembly line, but
  each VIN receives at most 12 writes over several hours. ✅
- **ByBatch GSI**: a batch of 200 components is registered within one shift → ~200 writes
  spread over 8 h per partition key. Far below the 1 000 WCU/s partition limit. ✅
- **ScaniaVehicles**: #8/#10 at 80 RPS across 100 k+ VINs. ✅

## Trade-offs and Optimizations

- **Aggregate Design**: service events co-located with the vehicle profile (100 % access
  correlation) - trades a slightly more complex sort key for one-Query history reads.
- **Normalization**: components kept separate from vehicles because they exist before any
  VIN and are addressed by serial - avoids a serial-number GSI on the vehicles table.
- **Sparse GSI**: `ByVehicle` only indexes installed components - roughly a third of the
  component lifecycle writes never touch this index.
- **GSI Projection**: INCLUDE on both GSIs; ALL would roughly double index storage for
  attributes the recall report and BOM screen never display.
- **Natural Keys**: `vin` and `serial_number` as partition keys - no ID lookup hop.
- **Optimistic locking**: `version` attribute on components so the quality team's
  quarantine cannot silently overwrite a concurrent installation.

## Validation Results 🔴

- [x] Reasoned step-by-step through design decisions, applying Important DynamoDB Context, Core Design Philosophy, and optimizing using Design Patterns ✅
- [x] Aggregate boundaries clearly defined based on access pattern analysis ✅
- [x] Every access pattern solved or alternative provided ✅
- [x] Unnecessary GSIs are removed and solved with an identifying relationship ✅
- [x] Multi-attribute keys used for GSI instead of composite string keys where applicable ✅ (not needed)
- [x] Base table keys use single attributes or composite strings (NOT multi-attribute keys) ✅
- [x] All tables and GSIs documented with full justification ✅
- [x] Hot partition analysis completed ✅
- [x] Trade-offs explicitly documented and justified ✅
- [x] Integration patterns detailed for non-DynamoDB functionality ✅ (none required)
- [x] No Scans used to solve access patterns ✅
- [x] Cross-referenced against `dynamodb_requirement.md` for accuracy ✅
- [x] Capacity and cost analysis completed using `compute_performances_and_costs` tool ✅ (see appendix below)


## Cost Report

> **Disclaimer:** This estimate covers **read/write request costs** and **storage costs** only,
> based on DynamoDB Standard table class on-demand pricing for the **US East (N. Virginia) /
> us-east-1** region. Prices were last verified in **January 2026**. Additional features such as
> Point-in-Time Recovery (PITR), backups, streams, and data transfer may incur additional costs.
> Actual costs may also vary based on your AWS region, pricing model (on-demand vs. provisioned),
> reserved capacity, and real-world traffic patterns. This report assumes constant RPS and average
> item sizes. For the most current pricing, refer to the
> [Amazon DynamoDB Pricing](https://aws.amazon.com/dynamodb/pricing/) page.

**Total Monthly Cost: $322.27**

| Source                  | Monthly Cost |
| ----------------------- | ------------ |
| Storage                 | $0.61        |
| Read and write requests | $321.66      |

### Storage Costs

**Monthly Cost:** $0.61

| Resource         | Type  | Storage (GB) | Monthly Cost |
| ---------------- | ----- | ------------ | ------------ |
| ScaniaComponents | Table | 0.68         | $0.17        |
| ByVehicle        | GSI   | 0.30         | $0.07        |
| ByBatch          | GSI   | 0.40         | $0.10        |
| ScaniaVehicles   | Table | 1.05         | $0.26        |

### Read and Write Request Costs

**Monthly Cost:** $321.66

| Resource         | Type  | Monthly Cost |
| ---------------- | ----- | ------------ |
| ScaniaComponents | Table | $116.94      |
| ByVehicle        | GSI   | $37.88       |
| ByBatch          | GSI   | $110.84      |
| ScaniaVehicles   | Table | $56.00       |

#### ScaniaComponents Table

**Monthly Cost:** $116.94

| Pattern | Operation      | RPS  | RRU / WRU | Monthly Cost |
| ------- | -------------- | ---- | --------- | ------------ |
| 1       | PutItem        | 20.0 | 1.00      | $32.94       |
| 2       | GetItem        | 50.0 | 0.50      | $8.23        |
| 3       | UpdateItem     | 20.0 | 1.00      | $32.94       |
| 6       | UpdateItem     | 1.0  | 1.00      | $1.65        |
| 12      | BatchWriteItem | 1.0  | 25.00     | $41.18       |

#### ScaniaComponents Table / ByVehicle GSI

**Monthly Cost:** $37.88

| Pattern | Operation  | RPS  | RRU / WRU | Monthly Cost |
| ------- | ---------- | ---- | --------- | ------------ |
| 4       | Query      | 30.0 | 0.50      | $4.94        |
| 3¹      | UpdateItem | 20.0 | 1.00      | $32.94       |

#### ScaniaComponents Table / ByBatch GSI

**Monthly Cost:** $110.84

| Pattern | Operation      | RPS  | RRU / WRU | Monthly Cost |
| ------- | -------------- | ---- | --------- | ------------ |
| 5       | Query          | 1.0  | 6.50      | $2.14        |
| 1¹      | PutItem        | 20.0 | 1.00      | $32.94       |
| 3¹      | UpdateItem     | 20.0 | 1.00      | $32.94       |
| 6¹      | UpdateItem     | 1.0  | 1.00      | $1.65        |
| 12¹     | BatchWriteItem | 1.0  | 25.00     | $41.18       |

#### ScaniaVehicles Table

**Monthly Cost:** $56.00

| Pattern | Operation | RPS  | RRU / WRU | Monthly Cost |
| ------- | --------- | ---- | --------- | ------------ |
| 7       | PutItem   | 5.0  | 1.00      | $8.24        |
| 8       | GetItem   | 50.0 | 0.50      | $8.23        |
| 9       | PutItem   | 10.0 | 1.00      | $16.47       |
| 10      | Query     | 30.0 | 2.00      | $19.76       |
| 11      | Query     | 20.0 | 0.50      | $3.29        |

¹ **GSI additional writes** - When a table write changes attributes projected into a GSI,
DynamoDB performs an additional write to that index, incurring extra WRUs. If the GSI partition
key value changes, the cost doubles (delete + insert) - this estimate assumes single writes only.
[Learn more](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html#GSI.ThroughputConsiderations.Writes)

<!-- end-cost-report -->