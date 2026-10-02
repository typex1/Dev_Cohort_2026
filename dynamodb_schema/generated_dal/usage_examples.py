"""Generated usage examples for DynamoDB entities and repositories"""
from __future__ import annotations

import os
import sys
import time
from decimal import Decimal

# Import generated entities and repositories
from entities import Component, Vehicle, ServiceEvent
from repositories import ComponentRepository, VehicleRepository, ServiceEventRepository


class UsageExamples:
    """Examples of using the generated entities and repositories"""

    def __init__(self):
        """Initialize repositories with default table names from schema."""

        # Initialize repositories with their respective table names
        # ScaniaComponents table repositories
        try:
            self.component_repo = ComponentRepository("ScaniaComponents")
            print(f"✅ Initialized ComponentRepository for table 'ScaniaComponents'")
        except Exception as e:
            print(f"❌ Failed to initialize ComponentRepository: {e}")
            self.component_repo = None
        # ScaniaVehicles table repositories
        try:
            self.vehicle_repo = VehicleRepository("ScaniaVehicles")
            print(f"✅ Initialized VehicleRepository for table 'ScaniaVehicles'")
        except Exception as e:
            print(f"❌ Failed to initialize VehicleRepository: {e}")
            self.vehicle_repo = None
        try:
            self.serviceevent_repo = ServiceEventRepository("ScaniaVehicles")
            print(f"✅ Initialized ServiceEventRepository for table 'ScaniaVehicles'")
        except Exception as e:
            print(f"❌ Failed to initialize ServiceEventRepository: {e}")
            self.serviceevent_repo = None

    def run_examples(self, include_additional_access_patterns: bool = False):
        """Run CRUD examples for all entities"""
        # Dictionary to store created entities for access pattern testing
        created_entities = {}

        # Step 0: Cleanup any leftover entities from previous runs (makes tests idempotent)
        print("🧹 Pre-test Cleanup: Removing any leftover entities from previous runs")
        print("=" * 50)
        # Try to delete Component (serial_number)
        try:
            sample_component = Component(
                serial_number="GBX-TUC-007777",
                component_type="GEARBOX",
                plant_code="TUC",
                batch_id="GBX-2026-W41-H",
                produced_at="2026-10-05T07:12:00Z",
                status="PRODUCED",
                vin="sample_vin",
                installed_at="sample_installed_at",
                version=1
            )
            self.component_repo.delete_component(sample_component.serial_number)
            print(f"   🗑️  Deleted leftover component (if existed)")
        except Exception:
            pass  # Ignore errors - item might not exist
        # Try to delete Vehicle (vin)
        try:
            sample_vehicle = Vehicle(
                vin="YS2R4X20005409876",
                model="R 560",
                assembly_plant="SOD",
                build_date="2026-10-12"
            )
            self.vehicle_repo.delete_vehicle(sample_vehicle.vin)
            print(f"   🗑️  Deleted leftover vehicle (if existed)")
        except Exception:
            pass  # Ignore errors - item might not exist
        # Access pattern #7 uses a conditional PutItem (attribute_not_exists), so the
        # access_pattern_data vehicle must be removed too for the run to be idempotent
        try:
            self.vehicle_repo.delete_vehicle("XLER4X20005405432")
            print(f"   🗑️  Deleted leftover access-pattern vehicle (if existed)")
        except Exception:
            pass  # Ignore errors - item might not exist
        # Try to delete ServiceEvent (vin, service_date, event_id)
        try:
            sample_serviceevent = ServiceEvent(
                vin="YS2R4X20005409876",
                event_id="EVT-9876",
                service_date="2026-11-20T08:00:00Z",
                mileage_km=1500,
                workshop="Scania Kungens Kurva",
                description="Delivery inspection"
            )
            self.serviceevent_repo.delete_service_event(sample_serviceevent.vin, sample_serviceevent.service_date, sample_serviceevent.event_id)
            print(f"   🗑️  Deleted leftover serviceevent (if existed)")
        except Exception:
            pass  # Ignore errors - item might not exist
        print("✅ Pre-test cleanup completed\n")

        print("Running Repository Examples")
        print("=" * 50)
        print("\n=== ScaniaComponents Table Operations ===")

        # Component example
        print("\n--- Component ---")

        # 1. CREATE - Create sample component
        sample_component = Component(
            serial_number="GBX-TUC-007777",
            component_type="GEARBOX",
            plant_code="TUC",
            batch_id="GBX-2026-W41-H",
            produced_at="2026-10-05T07:12:00Z",
            status="PRODUCED",
            vin="sample_vin",
            installed_at="sample_installed_at",
            version=1
        )

        print(f"📝 Creating component...")
        print(f"📝 PK: {sample_component.pk()}, SK: {sample_component.sk()}")

        try:
            created_component = self.component_repo.create_component(sample_component)
            print(f"✅ Created: {created_component}")
            # Store created entity for access pattern testing
            created_entities["Component"] = created_component
        except Exception as e:
            # Check if the error is due to item already existing
            if "ConditionalCheckFailedException" in str(e) or "already exists" in str(e).lower():
                print(f"⚠️  component already exists, retrieving existing entity...")
                try:
                    existing_component = self.component_repo.get_component(sample_component.serial_number)

                    if existing_component:
                        print(f"✅ Retrieved existing: {existing_component}")
                        # Store existing entity for access pattern testing
                        created_entities["Component"] = existing_component
                    else:
                        print(f"❌ Failed to retrieve existing component")
                except Exception as get_error:
                    print(f"❌ Failed to retrieve existing component: {get_error}")
            else:
                print(f"❌ Failed to create component: {e}")
        # 2. UPDATE - Update non-key field (component_type)
        if "Component" in created_entities:
            print(f"\n🔄 Updating component_type field...")
            try:
                # Refresh entity to get latest version (handles optimistic locking)
                entity_for_refresh = created_entities["Component"]
                refreshed_entity = self.component_repo.get_component(entity_for_refresh.serial_number)

                if refreshed_entity:
                    original_value = refreshed_entity.component_type
                    refreshed_entity.component_type = "GEARBOX"

                    updated_component = self.component_repo.update_component(refreshed_entity)
                    print(f"✅ Updated component_type: {original_value} → {updated_component.component_type}")

                    # Update stored entity with updated values
                    created_entities["Component"] = updated_component
                else:
                    print(f"❌ Could not refresh component for update")
            except Exception as e:
                if "version" in str(e).lower() or "modified by another process" in str(e).lower():
                    print(f"⚠️  component was modified by another process (optimistic locking): {e}")
                    print("💡 This is expected behavior in concurrent environments")
                else:
                    print(f"❌ Failed to update component: {e}")

        # 3. GET - Retrieve and print the entity
        if "Component" in created_entities:
            print(f"\n🔍 Retrieving component...")
            try:
                entity_for_get = created_entities["Component"]
                retrieved_component = self.component_repo.get_component(entity_for_get.serial_number)

                if retrieved_component:
                    print(f"✅ Retrieved: {retrieved_component}")
                else:
                    print("❌ Failed to retrieve component")
            except Exception as e:
                print(f"❌ Failed to retrieve component: {e}")

        print(f"🎯 Component CRUD cycle completed!")
        print("\n=== ScaniaVehicles Table Operations ===")

        # Vehicle example
        print("\n--- Vehicle ---")

        # 1. CREATE - Create sample vehicle
        sample_vehicle = Vehicle(
            vin="YS2R4X20005409876",
            model="R 560",
            assembly_plant="SOD",
            build_date="2026-10-12"
        )

        print(f"📝 Creating vehicle...")
        print(f"📝 PK: {sample_vehicle.pk()}, SK: {sample_vehicle.sk()}")

        try:
            created_vehicle = self.vehicle_repo.create_vehicle(sample_vehicle)
            print(f"✅ Created: {created_vehicle}")
            # Store created entity for access pattern testing
            created_entities["Vehicle"] = created_vehicle
        except Exception as e:
            # Check if the error is due to item already existing
            if "ConditionalCheckFailedException" in str(e) or "already exists" in str(e).lower():
                print(f"⚠️  vehicle already exists, retrieving existing entity...")
                try:
                    existing_vehicle = self.vehicle_repo.get_vehicle(sample_vehicle.vin)

                    if existing_vehicle:
                        print(f"✅ Retrieved existing: {existing_vehicle}")
                        # Store existing entity for access pattern testing
                        created_entities["Vehicle"] = existing_vehicle
                    else:
                        print(f"❌ Failed to retrieve existing vehicle")
                except Exception as get_error:
                    print(f"❌ Failed to retrieve existing vehicle: {get_error}")
            else:
                print(f"❌ Failed to create vehicle: {e}")
        # 2. UPDATE - Update non-key field (model)
        if "Vehicle" in created_entities:
            print(f"\n🔄 Updating model field...")
            try:
                # Refresh entity to get latest version (handles optimistic locking)
                entity_for_refresh = created_entities["Vehicle"]
                refreshed_entity = self.vehicle_repo.get_vehicle(entity_for_refresh.vin)

                if refreshed_entity:
                    original_value = refreshed_entity.model
                    refreshed_entity.model = "R 560 XT"

                    updated_vehicle = self.vehicle_repo.update_vehicle(refreshed_entity)
                    print(f"✅ Updated model: {original_value} → {updated_vehicle.model}")

                    # Update stored entity with updated values
                    created_entities["Vehicle"] = updated_vehicle
                else:
                    print(f"❌ Could not refresh vehicle for update")
            except Exception as e:
                if "version" in str(e).lower() or "modified by another process" in str(e).lower():
                    print(f"⚠️  vehicle was modified by another process (optimistic locking): {e}")
                    print("💡 This is expected behavior in concurrent environments")
                else:
                    print(f"❌ Failed to update vehicle: {e}")

        # 3. GET - Retrieve and print the entity
        if "Vehicle" in created_entities:
            print(f"\n🔍 Retrieving vehicle...")
            try:
                entity_for_get = created_entities["Vehicle"]
                retrieved_vehicle = self.vehicle_repo.get_vehicle(entity_for_get.vin)

                if retrieved_vehicle:
                    print(f"✅ Retrieved: {retrieved_vehicle}")
                else:
                    print("❌ Failed to retrieve vehicle")
            except Exception as e:
                print(f"❌ Failed to retrieve vehicle: {e}")

        print(f"🎯 Vehicle CRUD cycle completed!")

        # ServiceEvent example
        print("\n--- ServiceEvent ---")

        # 1. CREATE - Create sample serviceevent
        sample_serviceevent = ServiceEvent(
            vin="YS2R4X20005409876",
            event_id="EVT-9876",
            service_date="2026-11-20T08:00:00Z",
            mileage_km=1500,
            workshop="Scania Kungens Kurva",
            description="Delivery inspection"
        )

        print(f"📝 Creating serviceevent...")
        print(f"📝 PK: {sample_serviceevent.pk()}, SK: {sample_serviceevent.sk()}")

        try:
            created_serviceevent = self.serviceevent_repo.create_service_event(sample_serviceevent)
            print(f"✅ Created: {created_serviceevent}")
            # Store created entity for access pattern testing
            created_entities["ServiceEvent"] = created_serviceevent
        except Exception as e:
            # Check if the error is due to item already existing
            if "ConditionalCheckFailedException" in str(e) or "already exists" in str(e).lower():
                print(f"⚠️  serviceevent already exists, retrieving existing entity...")
                try:
                    existing_serviceevent = self.serviceevent_repo.get_service_event(sample_serviceevent.vin, sample_serviceevent.service_date, sample_serviceevent.event_id)

                    if existing_serviceevent:
                        print(f"✅ Retrieved existing: {existing_serviceevent}")
                        # Store existing entity for access pattern testing
                        created_entities["ServiceEvent"] = existing_serviceevent
                    else:
                        print(f"❌ Failed to retrieve existing serviceevent")
                except Exception as get_error:
                    print(f"❌ Failed to retrieve existing serviceevent: {get_error}")
            else:
                print(f"❌ Failed to create serviceevent: {e}")
        # 2. UPDATE - Update non-key field (mileage_km)
        if "ServiceEvent" in created_entities:
            print(f"\n🔄 Updating mileage_km field...")
            try:
                # Refresh entity to get latest version (handles optimistic locking)
                entity_for_refresh = created_entities["ServiceEvent"]
                refreshed_entity = self.serviceevent_repo.get_service_event(entity_for_refresh.vin, entity_for_refresh.service_date, entity_for_refresh.event_id)

                if refreshed_entity:
                    original_value = refreshed_entity.mileage_km
                    refreshed_entity.mileage_km = 1620

                    updated_serviceevent = self.serviceevent_repo.update_service_event(refreshed_entity)
                    print(f"✅ Updated mileage_km: {original_value} → {updated_serviceevent.mileage_km}")

                    # Update stored entity with updated values
                    created_entities["ServiceEvent"] = updated_serviceevent
                else:
                    print(f"❌ Could not refresh serviceevent for update")
            except Exception as e:
                if "version" in str(e).lower() or "modified by another process" in str(e).lower():
                    print(f"⚠️  serviceevent was modified by another process (optimistic locking): {e}")
                    print("💡 This is expected behavior in concurrent environments")
                else:
                    print(f"❌ Failed to update serviceevent: {e}")

        # 3. GET - Retrieve and print the entity
        if "ServiceEvent" in created_entities:
            print(f"\n🔍 Retrieving serviceevent...")
            try:
                entity_for_get = created_entities["ServiceEvent"]
                retrieved_serviceevent = self.serviceevent_repo.get_service_event(entity_for_get.vin, entity_for_get.service_date, entity_for_get.event_id)

                if retrieved_serviceevent:
                    print(f"✅ Retrieved: {retrieved_serviceevent}")
                else:
                    print("❌ Failed to retrieve serviceevent")
            except Exception as e:
                print(f"❌ Failed to retrieve serviceevent: {e}")

        print(f"🎯 ServiceEvent CRUD cycle completed!")

        print("\n" + "=" * 50)
        print("🎉 Basic CRUD examples completed!")

        # Additional Access Pattern Testing Section (before cleanup)
        if include_additional_access_patterns:
            self._test_additional_access_patterns(created_entities)

        # Cleanup - Delete all created entities
        print("\n" + "=" * 50)
        print("🗑️  Cleanup: Deleting all created entities")
        print("=" * 50)

        # Delete Component
        if "Component" in created_entities:
            print(f"\n🗑️  Deleting component...")
            try:
                deleted = self.component_repo.delete_component(created_entities["Component"].serial_number)

                if deleted:
                    print(f"✅ Deleted component successfully")
                else:
                    print("❌ Failed to delete component (not found or already deleted)")
            except Exception as e:
                print(f"❌ Failed to delete component: {e}")

        # Delete Vehicle
        if "Vehicle" in created_entities:
            print(f"\n🗑️  Deleting vehicle...")
            try:
                deleted = self.vehicle_repo.delete_vehicle(created_entities["Vehicle"].vin)

                if deleted:
                    print(f"✅ Deleted vehicle successfully")
                else:
                    print("❌ Failed to delete vehicle (not found or already deleted)")
            except Exception as e:
                print(f"❌ Failed to delete vehicle: {e}")

        # Delete ServiceEvent
        if "ServiceEvent" in created_entities:
            print(f"\n🗑️  Deleting serviceevent...")
            try:
                deleted = self.serviceevent_repo.delete_service_event(created_entities["ServiceEvent"].vin, created_entities["ServiceEvent"].service_date, created_entities["ServiceEvent"].event_id)

                if deleted:
                    print(f"✅ Deleted serviceevent successfully")
                else:
                    print("❌ Failed to delete serviceevent (not found or already deleted)")
            except Exception as e:
                print(f"❌ Failed to delete serviceevent: {e}")
        print('\n💡 Requirements:')
        print("   - DynamoDB table 'ScaniaComponents' must exist")
        print("   - DynamoDB table 'ScaniaVehicles' must exist")
        print('   - DynamoDB permissions: GetItem, PutItem, UpdateItem, DeleteItem')

    def _test_additional_access_patterns(self, created_entities: dict):
        """Test additional access patterns beyond basic CRUD"""
        print("\n" + "=" * 60)
        print("🔍 Additional Access Pattern Testing")
        print("=" * 60)
        print()

        # Component
        # Access Pattern #1: Register a produced component (status PRODUCED, version 1)
        # Index: Main Table
        try:
            print("🔍 Testing Access Pattern #1: Register a produced component (status PRODUCED, version 1)")
            print("   Using Main Table")
            test_entity = Component(
                serial_number="ENG-SOD-008888",
                component_type="ENGINE",
                plant_code="SOD",
                batch_id="ENG-2026-W41-J",
                produced_at="2026-10-06T09:30:00Z",
                status="INSTALLED",
                vin="YS2R4X20005409876",
                installed_at="2026-10-12T10:15:00Z",
                version=2
            )
            result = self.component_repo.register_component(test_entity)
            print(f"   ✅ Register a produced component (status PRODUCED, version 1) completed")
            print(f"   📊 Result: {result}")
        except Exception as e:
            print(f"❌ Error testing Access Pattern #1: {e}")



        # Access Pattern #2: Get component by serial number
        # Index: Main Table
        try:
            print("🔍 Testing Access Pattern #2: Get component by serial number")
            print("   Using Main Table")
            result = self.component_repo.get_component(
                created_entities["Component"].serial_number
            )
            print(f"   ✅ Get component by serial number completed")
            print(f"   📊 Result: {result}")
        except Exception as e:
            print(f"❌ Error testing Access Pattern #2: {e}")



        # Access Pattern #3: Install component into a vehicle: set vin, installed_at and status=INSTALLED
        # Index: Main Table
        try:
            print("🔍 Testing Access Pattern #3: Install component into a vehicle: set vin, installed_at and status=INSTALLED")
            print("   Using Main Table")
            result = self.component_repo.install_component(
                created_entities["Component"].serial_number,
                created_entities["Component"].vin,
                created_entities["Component"].installed_at,
                created_entities["Component"].status
            )
            print(f"   ✅ Install component into a vehicle: set vin, installed_at and status=INSTALLED completed")
            print(f"   📊 Result: {result}")
        except Exception as e:
            print(f"❌ Error testing Access Pattern #3: {e}")



        # Access Pattern #4: List all components installed in a vehicle (sparse GSI on vin)
        # GSI: ByVehicle
        try:
            print("🔍 Testing Access Pattern #4: List all components installed in a vehicle (sparse GSI on vin)")
            print("   Using GSI: ByVehicle")
            result = self.component_repo.list_components_by_vehicle(
                created_entities["Component"].vin
            )
            print(f"   ✅ List all components installed in a vehicle (sparse GSI on vin) completed")
            print(f"   📊 Result: {result}")
        except Exception as e:
            print(f"❌ Error testing Access Pattern #4: {e}")



        # Access Pattern #5: Recall lookup: all components of a production batch with their VINs
        # GSI: ByBatch
        try:
            print("🔍 Testing Access Pattern #5: Recall lookup: all components of a production batch with their VINs")
            print("   Using GSI: ByBatch")
            result = self.component_repo.list_components_by_batch(
                created_entities["Component"].batch_id
            )
            print(f"   ✅ Recall lookup: all components of a production batch with their VINs completed")
            print(f"   📊 Result: {result}")
        except Exception as e:
            print(f"❌ Error testing Access Pattern #5: {e}")



        # Access Pattern #6: Set a component's status to QUARANTINED
        # Index: Main Table
        try:
            print("🔍 Testing Access Pattern #6: Set a component's status to QUARANTINED")
            print("   Using Main Table")
            result = self.component_repo.quarantine_component(
                created_entities["Component"].serial_number,
                created_entities["Component"].status
            )
            print(f"   ✅ Set a component's status to QUARANTINED completed")
            print(f"   📊 Result: {result}")
        except Exception as e:
            print(f"❌ Error testing Access Pattern #6: {e}")



        # Access Pattern #12: Bulk-register a plant shift's components (up to 25 per request)
        # Index: Main Table
        try:
            print("🔍 Testing Access Pattern #12: Bulk-register a plant shift's components (up to 25 per request)")
            print("   Using Main Table")
            test_entity = Component(
                serial_number="ENG-SOD-008888",
                component_type="ENGINE",
                plant_code="SOD",
                batch_id="ENG-2026-W41-J",
                produced_at="2026-10-06T09:30:00Z",
                status="INSTALLED",
                vin="YS2R4X20005409876",
                installed_at="2026-10-12T10:15:00Z",
                version=2
            )
            result = self.component_repo.batch_register_components([test_entity])
            print(f"   ✅ Bulk-register a plant shift's components (up to 25 per request) completed")
            print(f"   📊 Result: {result}")
        except Exception as e:
            print(f"❌ Error testing Access Pattern #12: {e}")


        # Vehicle
        # Access Pattern #7: Create a vehicle profile when a VIN is allocated
        # Index: Main Table
        try:
            print("🔍 Testing Access Pattern #7: Create a vehicle profile when a VIN is allocated")
            print("   Using Main Table")
            test_entity = Vehicle(
                vin="XLER4X20005405432",
                model="S 500",
                assembly_plant="ZWO",
                build_date="2026-10-13"
            )
            result = self.vehicle_repo.put_vehicle(test_entity)
            print(f"   ✅ Create a vehicle profile when a VIN is allocated completed")
            print(f"   📊 Result: {result}")
        except Exception as e:
            print(f"❌ Error testing Access Pattern #7: {e}")



        # Access Pattern #8: Get vehicle profile by VIN
        # Index: Main Table
        try:
            print("🔍 Testing Access Pattern #8: Get vehicle profile by VIN")
            print("   Using Main Table")
            result = self.vehicle_repo.get_vehicle(
                created_entities["Vehicle"].vin
            )
            print(f"   ✅ Get vehicle profile by VIN completed")
            print(f"   📊 Result: {result}")
        except Exception as e:
            print(f"❌ Error testing Access Pattern #8: {e}")


        # ServiceEvent
        # Access Pattern #9: Record a workshop service event for a vehicle
        # Index: Main Table
        try:
            print("🔍 Testing Access Pattern #9: Record a workshop service event for a vehicle")
            print("   Using Main Table")
            test_entity = ServiceEvent(
                vin="XLER4X20005405432",
                event_id="EVT-6543",
                service_date="2026-11-22T13:30:00Z",
                mileage_km=950,
                workshop="Scania Rotterdam",
                description="Delivery inspection"
            )
            result = self.serviceevent_repo.record_service_event(test_entity)
            print(f"   ✅ Record a workshop service event for a vehicle completed")
            print(f"   📊 Result: {result}")
        except Exception as e:
            print(f"❌ Error testing Access Pattern #9: {e}")



        # Access Pattern #10: Vehicle service history (all SERVICE# items for a VIN; caller sorts newest first / limits to 20)
        # Index: Main Table
        # Range Condition: begins_with
        try:
            print("🔍 Testing Access Pattern #10: Vehicle service history (all SERVICE# items for a VIN; caller sorts newest first / limits to 20)")
            print("   Using Main Table")
            print("   Range Condition: begins_with")
            result = self.serviceevent_repo.get_service_history(
                created_entities["ServiceEvent"].vin,
                "sk_prefix_value"
            )
            print(f"   ✅ Vehicle service history (all SERVICE# items for a VIN; caller sorts newest first / limits to 20) completed")
            print(f"   📊 Result: {result}")
        except Exception as e:
            print(f"❌ Error testing Access Pattern #10: {e}")



        # Access Pattern #11: Latest service event for a vehicle (same Query as #10 with Limit=1, ScanIndexForward=False)
        # Index: Main Table
        # Range Condition: begins_with
        try:
            print("🔍 Testing Access Pattern #11: Latest service event for a vehicle (same Query as #10 with Limit=1, ScanIndexForward=False)")
            print("   Using Main Table")
            print("   Range Condition: begins_with")
            result = self.serviceevent_repo.get_latest_service_event(
                created_entities["ServiceEvent"].vin,
                "sk_prefix_value"
            )
            print(f"   ✅ Latest service event for a vehicle (same Query as #10 with Limit=1, ScanIndexForward=False) completed")
            print(f"   📊 Result: {result}")
        except Exception as e:
            print(f"❌ Error testing Access Pattern #11: {e}")


        print("\n💡 Access Pattern Implementation Notes:")
        print("   - Main Table queries use partition key and sort key")
        print("   - GSI queries use different key structures and may have range conditions")
        print("   - Range conditions (begins_with, between, >, <, >=, <=) require additional parameters")
        print("   - Implement the access pattern methods in your repository classes")


def main():
    """Main function to run examples"""

    # 🚨 SAFETY CHECK: Prevent accidental execution against production DynamoDB
    endpoint_url = os.getenv("AWS_ENDPOINT_URL_DYNAMODB", "")

    # Check if running against DynamoDB Local
    is_local = (
        "localhost" in endpoint_url.lower() or
        "127.0.0.1" in endpoint_url
    )

    if not is_local:
        print("=" * 80)
        print("🚨 SAFETY WARNING: NOT RUNNING AGAINST DYNAMODB LOCAL")
        print("=" * 80)
        print()
        print(f"Current endpoint: {endpoint_url or 'AWS DynamoDB (production)'}")
        print()
        print("⚠️  This script performs CREATE, UPDATE, and DELETE operations that could")
        print("   affect your production data!")
        print()
        print("To run against production DynamoDB:")
        print("  1. Review the code carefully to understand what data will be modified")
        print("  2. Search for 'SAFETY CHECK' in this file")
        print("  3. Comment out the 'raise RuntimeError' line below the safety check")
        print("  4. Understand the risks before proceeding")
        print()
        print("To run safely against DynamoDB Local:")
        print("  export AWS_ENDPOINT_URL_DYNAMODB=http://localhost:8000")
        print()
        print("=" * 80)

        # 🛑 SAFETY CHECK: Comment out this line to run against production
        raise RuntimeError("Safety check: Refusing to run against production DynamoDB. See warning above.")

    # Parse command line arguments
    include_additional_access_patterns = "--all" in sys.argv

    # Check if we're running against DynamoDB Local
    if endpoint_url:
        print(f"🔗 Using DynamoDB endpoint: {endpoint_url}")
        print(f"🌍 Using region: {os.getenv('AWS_DEFAULT_REGION', 'us-east-1')}")
    else:
        print("🌐 Using AWS DynamoDB (no local endpoint specified)")

    print("📊 Using multiple tables:")
    print(f"   - ScaniaComponents")
    print(f"   - ScaniaVehicles")

    if include_additional_access_patterns:
        print("🔍 Including additional access pattern examples")

    examples = UsageExamples()
    examples.run_examples(include_additional_access_patterns=include_additional_access_patterns)


if __name__ == "__main__":
    main()
