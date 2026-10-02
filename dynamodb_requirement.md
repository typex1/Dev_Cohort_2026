# DynamoDB Modeling Session

> Working file produced in **Phase 1** of the `dynamodb_data_modeling` MCP tool workflow.
> The tool's expert prompt asks the agent to capture application context and access
> patterns here *before* designing anything. Students: this is the file you iterate on with Kiro.

## Application Overview

**Domain**: Component traceability for Scania's modular production system.

Scania builds trucks from modules produced in specialised plants (cabs in Oskarshamn,
frames in Luleå, gearboxes in Tucumán, engines in Södertälje) and assembles them in
Södertälje, Zwolle, Angers, Rugao and São Bernardo do Campo. Every serialised component
must be traceable: *which plant produced it, in which batch, and in which vehicle (VIN)
it ended up*. When a supplier batch turns out to be faulty, the quality team needs to find
every affected vehicle within seconds. Workshops additionally log service events per VIN.

- **Users**: plant MES systems (writes), assembly line scanners (writes), quality/recall
  team (reads), workshops (read + write).
- **Scale (planning numbers)**: ~100 000 vehicles/year, ~12 serialised components per
  vehicle, ~9 service events per vehicle over its life.
- **Consistency**: installation records must be strongly consistent for the recall query
  (eventually consistent GSIs are acceptable - a few hundred milliseconds of lag is fine).

## Access Patterns Analysis

| # | Access Pattern | Type | Peak RPS | Notes |
|---|----------------|------|----------|-------|
| 1 | Register a produced component by serial number | Write | 20 | From plant MES at end of line |
| 2 | Look up a component by serial number | Read | 50 | Scanner at assembly station |
| 3 | Install a component into a vehicle (VIN) | Write | 20 | Sets `vin`, `installed_at`, `status=INSTALLED` |
| 4 | List all components installed in a vehicle | Read | 30 | Avg 12 items |
| 5 | Recall: find all components (and their VINs) from a batch | Read | 1 | Avg 200 items, rare but critical |
| 6 | Quarantine a component (status change) | Write | 1 | Quality team |
| 7 | Create a vehicle profile when a VIN is allocated | Write | 5 | Model, assembly plant, build date |
| 8 | Get vehicle profile by VIN | Read | 50 | Workshop app |
| 9 | Record a workshop service event for a vehicle | Write | 10 | Mileage, workshop, description |
| 10 | Vehicle service history, newest first | Read | 30 | Last 20 events |
| 11 | Latest service event for a vehicle | Read | 20 | Limit 1 |
| 12 | Bulk-register a plant shift's output (25 components) | Write | 1 | BatchWriteItem |

## Entity Relationships Deep Dive

- **Component (1) → Vehicle (0..1)**: a component is installed in at most one vehicle;
  a vehicle has ~12 components. Not an identifying relationship (a component exists,
  and is queried, before it has a VIN).
- **Batch (1) → Component (many)**: ~200 components per batch; batch is only ever used
  as a *lookup dimension* for recalls, it carries no attributes of its own.
- **Vehicle (1) → ServiceEvent (many)**: service events only make sense in the context
  of a vehicle - identifying relationship, 100 % of reads go through the VIN.

## Enhanced Aggregate Analysis

### Vehicle + ServiceEvent Item Collection Analysis

- Access correlation: ~100 % of service reads are "for this VIN" -> same item collection.
- Profile is 1 KB, events ~800 B, ≤ 50 events per vehicle -> collection stays far below
  the 10 GB partition limit and reads are bounded with `begins_with(SK, "SERVICE#")`.
- Decision: **co-locate** profile and service events in one `ScaniaVehicles` table.

### Vehicle + Component Item Collection Analysis

- A component is created *before* it is installed (patterns 1, 2) and must be found by
  its serial number alone (pattern 2). Putting it under the VIN partition would force a
  GSI on serial anyway, and recall (pattern 5) needs a batch GSI regardless.
- Decision: **separate** `ScaniaComponents` table keyed by serial number, with a *sparse*
  GSI on `vin` for pattern 4 and a GSI on `batch_id` for pattern 5.

## Table Consolidation Analysis

Two tables, two aggregates. Consolidating into a single table would only add key-prefix
complexity without removing any GSI. Keep them separate.

## Design Considerations (Scratchpad)

- `vin` is absent on un-installed components -> `ByVehicle` GSI is naturally sparse.
- Recall queries are rare (1 RPS) but return many items -> INCLUDE projection on
  `ByBatch` with only the attributes the recall report prints.
- Service event SK: `SERVICE#<ISO-8601 timestamp>#<event_id>` sorts chronologically;
  "newest first" = `ScanIndexForward=False`.
