# Auto-generated repositories
from __future__ import annotations

from decimal import Decimal
from typing import Any

from boto3.dynamodb.conditions import Attr, Key

from base_repository import BaseRepository, KeyType, OptimisticLockException
from entities import Component, ServiceEvent, Vehicle

class ComponentRepository(BaseRepository[Component]):
    """Repository for Component entity operations"""

    def __init__(self, table_name: str = "ScaniaComponents"):
        super().__init__(Component, table_name, "serial_number", None)

    # Basic CRUD Operations (Generated)
    def create_component(self, component: Component) -> Component:
        """Create a new component"""
        return self.create(component)

    def get_component(self, serial_number: str) -> Component | None:
        """Get a component by key"""
        pk = Component.build_pk_for_lookup(serial_number)
        
        return self.get(pk, None)

    def update_component(self, component: Component) -> Component:
        """Update an existing component"""
        return self.update(component)

    def delete_component(self, serial_number: str) -> bool:
        """Delete a component"""
        pk = Component.build_pk_for_lookup(serial_number)
        return self.delete(pk, None)

    def register_component(self, component: Component) -> Component | None:
        """Register a produced component (status PRODUCED, version 1)

        Access Pattern #1 - PutItem with attribute_not_exists(serial_number) so a
        plant MES can safely retry the registration without overwriting a
        component that was already installed in a vehicle.
        """
        component.status = "PRODUCED"
        component.version = 1
        # exclude_none keeps vin/installed_at absent -> item stays out of the sparse ByVehicle GSI
        item = component.model_dump(exclude_none=True)
        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(#sn)",
                ExpressionAttributeNames={"#sn": "serial_number"},
            )
        except self.table.meta.client.exceptions.ConditionalCheckFailedException:
            # Already registered: idempotent no-op, return the stored item
            return self.get_component(component.serial_number)
        return component

    def install_component(self, serial_number: str, vin: str, installed_at: str, status: str) -> Component | None:
        """Install component into a vehicle: set vin, installed_at and status=INSTALLED

        Access Pattern #3 - UpdateItem guarded by the business rule
        "only a PRODUCED component can be installed". Setting ``vin`` makes the
        item appear in the sparse ByVehicle GSI.
        """
        pk = Component.build_pk_for_lookup(serial_number)
        try:
            response = self.table.update_item(
                Key={"serial_number": pk},
                UpdateExpression=(
                    "SET #vin = :vin, #installed_at = :installed_at, "
                    "#status = :status, #version = #version + :one"
                ),
                ConditionExpression="#status = :produced",
                ExpressionAttributeNames={
                    "#vin": "vin",
                    "#installed_at": "installed_at",
                    "#status": "status",
                    "#version": "version",
                },
                ExpressionAttributeValues={
                    ":vin": vin,
                    ":installed_at": installed_at,
                    ":status": status,
                    ":produced": "PRODUCED",
                    ":one": 1,
                },
                ReturnValues="ALL_NEW",
            )
        except self.table.meta.client.exceptions.ConditionalCheckFailedException as e:
            raise RuntimeError(
                f"Component {serial_number} is not in status PRODUCED and cannot be installed"
            ) from e
        return Component(**response["Attributes"])

    def list_components_by_vehicle(self, vin: str, limit: int = 100, exclusive_start_key: dict | None = None, skip_invalid_items: bool = True) -> tuple[list[dict[str, Any]], dict | None]:
        """List all components installed in a vehicle (sparse GSI on vin)

        Projection: INCLUDE
        Projected Attributes: component_type, plant_code, batch_id, installed_at

        Returns dict because required fields not in projection: produced_at, status, version
        Use dict keys to access values: result[0]['component_type']

        To return typed Component entities, either:
          1. Add these fields to included_attributes: ['produced_at', 'status', 'version']
          2. Make these fields optional (required: false)

        Args:
            vin: Vin
            limit: Maximum items per page (default: 100)
            exclusive_start_key: Continuation token from previous page
            skip_invalid_items: If True, skip items that fail deserialization and continue. If False, raise exception on validation errors.

        Returns:
            tuple: (items, last_evaluated_key)
        """
        # Access Pattern #4 - Query the sparse ByVehicle GSI (INCLUDE projection -> raw dicts)
        gsi_pk = Component.build_gsi_pk_for_lookup_by_vehicle(vin)
        query_params: dict[str, Any] = {
            "IndexName": "ByVehicle",
            "KeyConditionExpression": Key("vin").eq(gsi_pk),
            "Limit": limit,
        }
        if exclusive_start_key:
            query_params["ExclusiveStartKey"] = exclusive_start_key
        response = self.table.query(**query_params)
        return self._parse_query_response_raw(response)

    def list_components_by_batch(self, batch_id: str, limit: int = 100, exclusive_start_key: dict | None = None, skip_invalid_items: bool = True) -> tuple[list[dict[str, Any]], dict | None]:
        """Recall lookup: all components of a production batch with their VINs

        Projection: INCLUDE
        Projected Attributes: component_type, status, vin

        Returns dict because required fields not in projection: plant_code, produced_at, version
        Use dict keys to access values: result[0]['component_type']

        To return typed Component entities, either:
          1. Add these fields to included_attributes: ['plant_code', 'produced_at', 'version']
          2. Make these fields optional (required: false)

        Args:
            batch_id: Batch id
            limit: Maximum items per page (default: 100)
            exclusive_start_key: Continuation token from previous page
            skip_invalid_items: If True, skip items that fail deserialization and continue. If False, raise exception on validation errors.

        Returns:
            tuple: (items, last_evaluated_key)
        """
        # Access Pattern #5 - Query the ByBatch GSI for a recall report
        gsi_pk = Component.build_gsi_pk_for_lookup_by_batch(batch_id)
        query_params: dict[str, Any] = {
            "IndexName": "ByBatch",
            "KeyConditionExpression": Key("batch_id").eq(gsi_pk),
            "Limit": limit,
        }
        if exclusive_start_key:
            query_params["ExclusiveStartKey"] = exclusive_start_key
        response = self.table.query(**query_params)
        return self._parse_query_response_raw(response)

    def quarantine_component(self, serial_number: str, status: str) -> Component | None:
        """Set a component's status (normally QUARANTINED)

        Access Pattern #6 - read-then-UpdateItem with optimistic locking on
        ``version`` so the quality team never overwrites a concurrent change.
        """
        pk = Component.build_pk_for_lookup(serial_number)
        current_item = self.get(pk, None)
        if not current_item:
            raise RuntimeError(f"Component {serial_number} not found")
        current_version = current_item.version
        try:
            response = self.table.update_item(
                Key={"serial_number": pk},
                UpdateExpression="SET #status = :status, #version = :new_version",
                ConditionExpression="#version = :current_version",
                ExpressionAttributeNames={"#status": "status", "#version": "version"},
                ExpressionAttributeValues={
                    ":status": status,
                    ":current_version": current_version,
                    ":new_version": current_version + 1,
                },
                ReturnValues="ALL_NEW",
            )
        except self.table.meta.client.exceptions.ConditionalCheckFailedException as e:
            raise OptimisticLockException(
                "Component", f"version changed while quarantining {serial_number}"
            ) from e
        return Component(**response["Attributes"])

    def batch_register_components(self, components: Component | list[Component]) -> Component | None:
        """Bulk-register a plant shift's components (up to 25 per request)

        WARNING: BatchWriteItem does NOT support optimistic locking.
        DynamoDB does not allow condition expressions in batch operations.
        Use individual create/update operations if version checking is required.

        Access Pattern #12 - the boto3 resource ``batch_writer`` chunks into 25-item
        requests and retries UnprocessedItems automatically.
        """
        if isinstance(components, Component):
            components = [components]
        with self.table.batch_writer() as batch:
            for component in components:
                component.status = "PRODUCED"
                component.version = 1
                batch.put_item(Item=component.model_dump(exclude_none=True))
        return components[0] if components else None

class VehicleRepository(BaseRepository[Vehicle]):
    """Repository for Vehicle entity operations"""

    def __init__(self, table_name: str = "ScaniaVehicles"):
        super().__init__(Vehicle, table_name, "vin", "sk")

    # Basic CRUD Operations (Generated)
    def create_vehicle(self, vehicle: Vehicle) -> Vehicle:
        """Create a new vehicle"""
        return self.create(vehicle)

    def get_vehicle(self, vin: str) -> Vehicle | None:
        """Get a vehicle by key"""
        pk = Vehicle.build_pk_for_lookup(vin)
        sk = Vehicle.build_sk_for_lookup()
        return self.get(pk, sk)

    def update_vehicle(self, vehicle: Vehicle) -> Vehicle:
        """Update an existing vehicle"""
        return self.update(vehicle)

    def delete_vehicle(self, vin: str) -> bool:
        """Delete a vehicle"""
        pk = Vehicle.build_pk_for_lookup(vin)
        sk = Vehicle.build_sk_for_lookup()
        return self.delete(pk, sk)

    def put_vehicle(self, vehicle: Vehicle) -> Vehicle | None:
        """Put a vehicle profile when a VIN is allocated

        Access Pattern #7 - PutItem with attribute_not_exists(vin): a VIN is
        allocated exactly once, so a duplicate allocation is an error.
        """
        item = vehicle.model_dump(exclude_none=True)
        item["vin"] = vehicle.pk()
        item["sk"] = vehicle.sk()
        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(#vin)",
                ExpressionAttributeNames={"#vin": "vin"},
            )
        except self.table.meta.client.exceptions.ConditionalCheckFailedException as e:
            raise OptimisticLockException(
                "Vehicle", f"profile for VIN {vehicle.vin} already exists"
            ) from e
        return vehicle

class ServiceEventRepository(BaseRepository[ServiceEvent]):
    """Repository for ServiceEvent entity operations"""

    def __init__(self, table_name: str = "ScaniaVehicles"):
        super().__init__(ServiceEvent, table_name, "vin", "sk")

    # Basic CRUD Operations (Generated)
    def create_service_event(self, service_event: ServiceEvent) -> ServiceEvent:
        """Create a new service_event"""
        return self.create(service_event)

    def get_service_event(self, vin: str, service_date: str, event_id: str) -> ServiceEvent | None:
        """Get a service_event by key"""
        pk = ServiceEvent.build_pk_for_lookup(vin)
        sk = ServiceEvent.build_sk_for_lookup(service_date, event_id)
        return self.get(pk, sk)

    def update_service_event(self, service_event: ServiceEvent) -> ServiceEvent:
        """Update an existing service_event"""
        return self.update(service_event)

    def delete_service_event(self, vin: str, service_date: str, event_id: str) -> bool:
        """Delete a service_event"""
        pk = ServiceEvent.build_pk_for_lookup(vin)
        sk = ServiceEvent.build_sk_for_lookup(service_date, event_id)
        return self.delete(pk, sk)

    def record_service_event(self, service_event: ServiceEvent) -> ServiceEvent | None:
        """Record a workshop service event for a vehicle

        Access Pattern #9 - plain PutItem into the vehicle's item collection.
        The SK ``SERVICE#<service_date>#<event_id>`` is built by the entity.
        """
        item = service_event.model_dump(exclude_none=True)
        item["vin"] = service_event.pk()
        item["sk"] = service_event.sk()
        self.table.put_item(Item=item)
        return service_event

    def get_service_history(self, vin: str, sk_prefix: str, limit: int = 100, exclusive_start_key: dict | None = None, skip_invalid_items: bool = True) -> tuple[list[ServiceEvent], dict | None]:
        """Vehicle service history (all SERVICE# items for a VIN; caller sorts newest first / limits to 20)

        Args:
            vin: Vin
            sk_prefix: Sk prefix
            limit: Maximum items per page (default: 100)
            exclusive_start_key: Continuation token from previous page
            skip_invalid_items: If True, skip items that fail deserialization and continue. If False, raise exception on validation errors.

        Returns:
            tuple: (items, last_evaluated_key)
        """
        # Access Pattern #10 - item-collection Query, newest first (SK sorts by ISO timestamp)
        pk = ServiceEvent.build_pk_for_lookup(vin)
        query_params: dict[str, Any] = {
            "KeyConditionExpression": Key("vin").eq(pk) & Key("sk").begins_with(sk_prefix),
            "ScanIndexForward": False,
            "Limit": limit,
            "ConsistentRead": False,
        }
        if exclusive_start_key:
            query_params["ExclusiveStartKey"] = exclusive_start_key
        response = self.table.query(**query_params)
        return self._parse_query_response(response, skip_invalid_items)

    def get_latest_service_event(self, vin: str, sk_prefix: str, limit: int = 100, exclusive_start_key: dict | None = None, skip_invalid_items: bool = True) -> tuple[list[ServiceEvent], dict | None]:
        """Latest service event for a vehicle (same Query as #10 with Limit=1, ScanIndexForward=False)

        Args:
            vin: Vin
            sk_prefix: Sk prefix
            limit: Maximum items per page (default: 100)
            exclusive_start_key: Continuation token from previous page
            skip_invalid_items: If True, skip items that fail deserialization and continue. If False, raise exception on validation errors.

        Returns:
            tuple: (items, last_evaluated_key)
        """
        # Access Pattern #11 - same Query as #10 but Limit=1 (the generated `limit`
        # argument is ignored on purpose: "latest" means exactly one item)
        pk = ServiceEvent.build_pk_for_lookup(vin)
        query_params: dict[str, Any] = {
            "KeyConditionExpression": Key("vin").eq(pk) & Key("sk").begins_with(sk_prefix),
            "ScanIndexForward": False,
            "Limit": 1,
            "ConsistentRead": False,
        }
        if exclusive_start_key:
            query_params["ExclusiveStartKey"] = exclusive_start_key
        response = self.table.query(**query_params)
        return self._parse_query_response(response, skip_invalid_items)
