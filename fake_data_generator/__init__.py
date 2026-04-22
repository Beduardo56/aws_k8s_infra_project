"""
Fake Data Generator for Energy Meter Data

Gera dados fake para:
- InstantaneousValues: medições instantâneas de energia
- DeviceSyncParameters: parâmetros de sincronização de dispositivos

Exemplo de uso:
    from fake_data_generator import FakeDataOrchestrator

    orchestrator = FakeDataOrchestrator(
        num_devices=4,
        instantaneous_frequency_seconds=60,   # medição a cada 1 minuto
        sync_params_frequency_seconds=300,    # sync params a cada 5 minutos
        duration_minutes=60
    )

    instantaneous_data = orchestrator.generate_instantaneous()
    sync_params_data = orchestrator.generate_sync_parameters()
"""

from .generators import (
    InstantaneousGenerator,
    SyncParametersGenerator,
    DeviceGenerator,
    FakeDataOrchestrator,
)
from .models import (
    InstantaneousData,
    SyncParametersData,
    DeviceConfig,
    DeviceData,
    save_devices_to_csv,
)

__all__ = [
    "InstantaneousGenerator",
    "SyncParametersGenerator",
    "DeviceGenerator",
    "FakeDataOrchestrator",
    "InstantaneousData",
    "SyncParametersData",
    "DeviceConfig",
    "DeviceData",
    "save_devices_to_csv",
]
