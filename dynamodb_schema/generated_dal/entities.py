# Auto-generated entities
from __future__ import annotations

from decimal import Decimal
from typing import Any

from base_repository import ConfigurableEntity, EntityConfig, KeyType
from pydantic import BaseModel

# Component Entity Configuration
COMPONENT_CONFIG = EntityConfig(
    entity_type="COMPONENT",
    pk_builder=lambda entity: f"{entity.serial_number}",
    pk_lookup_builder=lambda serial_number: f"{serial_number}",
    sk_builder=None,  # No sort key for this entity
    sk_lookup_builder=None,  # No sort key for this entity
    prefix_builder=None  # No sort key prefix for this entity
)

class Component(ConfigurableEntity):
    serial_number: str
    component_type: str
    plant_code: str
    batch_id: str
    produced_at: str
    status: str
    vin: str = None
    installed_at: str = None
    version: int

    @classmethod
    def get_config(cls) -> EntityConfig:
        return COMPONENT_CONFIG

    # GSI Key Builder Class Methods

    @classmethod
    def build_gsi_pk_for_lookup_by_vehicle(cls, vin) -> KeyType:
        """Build GSI partition key for ByVehicle lookup operations"""
        return f"{vin}"

    @classmethod
    def build_gsi_sk_for_lookup_by_vehicle(cls, serial_number) -> KeyType:
        """Build GSI sort key for ByVehicle lookup operations"""
        return f"{serial_number}"

    @classmethod
    def build_gsi_pk_for_lookup_by_batch(cls, batch_id) -> KeyType:
        """Build GSI partition key for ByBatch lookup operations"""
        return f"{batch_id}"

    @classmethod
    def build_gsi_sk_for_lookup_by_batch(cls, serial_number) -> KeyType:
        """Build GSI sort key for ByBatch lookup operations"""
        return f"{serial_number}"

    # GSI Key Builder Instance Methods

    def build_gsi_pk_by_vehicle(self) -> KeyType:
        """Build GSI partition key for ByVehicle from entity instance"""
        return f"{self.vin}"

    def build_gsi_sk_by_vehicle(self) -> KeyType:
        """Build GSI sort key for ByVehicle from entity instance"""
        return f"{self.serial_number}"

    def build_gsi_pk_by_batch(self) -> KeyType:
        """Build GSI partition key for ByBatch from entity instance"""
        return f"{self.batch_id}"

    def build_gsi_sk_by_batch(self) -> KeyType:
        """Build GSI sort key for ByBatch from entity instance"""
        return f"{self.serial_number}"

    # GSI Prefix Helper Methods

    @classmethod
    def get_gsi_pk_prefix_by_vehicle(cls) -> str:
        """Get GSI partition key prefix for ByVehicle query operations"""
        return ""

    @classmethod
    def get_gsi_sk_prefix_by_vehicle(cls) -> str:
        """Get GSI sort key prefix for ByVehicle query operations"""
        return ""

    @classmethod
    def get_gsi_pk_prefix_by_batch(cls) -> str:
        """Get GSI partition key prefix for ByBatch query operations"""
        return ""

    @classmethod
    def get_gsi_sk_prefix_by_batch(cls) -> str:
        """Get GSI sort key prefix for ByBatch query operations"""
        return ""

# Vehicle Entity Configuration
VEHICLE_CONFIG = EntityConfig(
    entity_type="PROFILE",
    pk_builder=lambda entity: f"{entity.vin}",
    pk_lookup_builder=lambda vin: f"{vin}",
    sk_builder=lambda entity: f"PROFILE",
    sk_lookup_builder=lambda: f"PROFILE",
    prefix_builder=lambda **kwargs: "PROFILE#"
)

class Vehicle(ConfigurableEntity):
    vin: str
    model: str
    assembly_plant: str
    build_date: str

    @classmethod
    def get_config(cls) -> EntityConfig:
        return VEHICLE_CONFIG

# ServiceEvent Entity Configuration
SERVICEEVENT_CONFIG = EntityConfig(
    entity_type="SERVICE",
    pk_builder=lambda entity: f"{entity.vin}",
    pk_lookup_builder=lambda vin: f"{vin}",
    sk_builder=lambda entity: f"SERVICE#{entity.service_date}#{entity.event_id}",
    sk_lookup_builder=lambda service_date, event_id: f"SERVICE#{service_date}#{event_id}",
    prefix_builder=lambda **kwargs: "SERVICE#"
)

class ServiceEvent(ConfigurableEntity):
    vin: str
    event_id: str
    service_date: str
    mileage_km: int
    workshop: str
    description: str

    @classmethod
    def get_config(cls) -> EntityConfig:
        return SERVICEEVENT_CONFIG
