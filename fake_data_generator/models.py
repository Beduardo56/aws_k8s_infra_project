"""
Dataclasses representando os modelos de dados.
Independente de Django/ORM para portabilidade.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List
import json
import csv
from pathlib import Path


@dataclass
class DeviceConfig:
    """Configuracao de um dispositivo fake."""
    device_id: int
    mac_address: str
    serial: str
    product_id: int = 14

    # Parametros de medicao
    nominal_voltage: float = 220.0  # Tensao nominal (V)
    nominal_current: float = 50.0   # Corrente nominal (A)
    power_factor: float = 0.92      # Fator de potencia tipico

    # Variacao aleatoria (%)
    voltage_variation: float = 0.05
    current_variation: float = 0.30

    # WiFi
    wifi_ssid: str = "TimeEnergy_Network"
    wifi_signal_range: tuple = (-70, -30)  # dBm


@dataclass
class InstantaneousData:
    """Dados de medicao instantanea."""
    device_id: int
    measured_at: datetime
    mac_address: Optional[str] = None

    # Voltage measurements
    voltage_a: Optional[float] = None
    voltage_b: Optional[float] = None
    voltage_c: Optional[float] = None
    voltage_ab: Optional[float] = None
    voltage_bc: Optional[float] = None
    voltage_ca: Optional[float] = None

    # Current measurements
    current_a: Optional[float] = None
    current_b: Optional[float] = None
    current_c: Optional[float] = None

    # Active power measurements (W)
    active_power_a: Optional[float] = None
    active_power_b: Optional[float] = None
    active_power_c: Optional[float] = None
    threephase_active_power: Optional[float] = None

    # Reactive power measurements (VAr)
    reactive_power_a: Optional[float] = None
    reactive_power_b: Optional[float] = None
    reactive_power_c: Optional[float] = None
    threephase_reactive_power: Optional[float] = None

    # Apparent power measurements (VA)
    apparent_power_a: Optional[float] = None
    apparent_power_b: Optional[float] = None
    apparent_power_c: Optional[float] = None
    threephase_apparent_power: Optional[float] = None

    # Frequency measurements (Hz)
    frequency_a: Optional[float] = None
    frequency_b: Optional[float] = None
    frequency_c: Optional[float] = None

    # Power factor
    power_factor_a: Optional[float] = None
    power_factor_b: Optional[float] = None
    power_factor_c: Optional[float] = None

    # Additional measurements
    temperature: Optional[float] = None
    angle_a: Optional[float] = None
    angle_b: Optional[float] = None
    angle_c: Optional[float] = None
    neutral_current: Optional[float] = None

    # Timezone info
    timezone: Optional[int] = None
    daylight_saving_time: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionario."""
        data = asdict(self)
        if isinstance(data['measured_at'], datetime):
            data['measured_at'] = data['measured_at'].isoformat()
        return data

    def to_json(self) -> str:
        """Converte para JSON."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class SyncParametersData:
    """Dados de sincronizacao de dispositivo."""
    device_id: int
    measure_datetime: datetime
    serial: str

    # WiFi info
    wifi_signal: float = -50.0
    wifi_ssid: Optional[str] = None
    wifi_bssid: Optional[str] = None
    wifi_ip_address: Optional[str] = None
    wifi_noise: Optional[int] = None

    # Device info
    uptime: Optional[int] = None
    mac_address: Optional[str] = None
    product_id: Optional[int] = None

    # Meter configuration
    meter_tc_polarity: Optional[int] = None
    meter_tc_ratio: Optional[int] = None

    # Firmware versions
    firmware_metrol_ver: Optional[str] = None
    firmware_app_ver: Optional[str] = None

    # Feature flags
    enable_meter_energy_interruptions: bool = False
    enable_meter_instantaneous_values: bool = True
    enable_meter_load_packets: bool = False
    enable_meter_registers: bool = True
    enable_meter_harmonics: bool = False
    enable_meter_unified_load_packets: bool = False
    enable_meter_recording_memory_last_register: bool = False
    enable_meter_registers_aligned_recording_memory: bool = False

    # Recording memory config
    meter_recording_memory_channels: Optional[str] = None
    meter_recording_memory_period: Optional[int] = None
    meter_recording_memory_records: Optional[int] = None

    # Full sync params JSON
    full_sync_params: Optional[Dict[str, Any]] = None

    # Timezone
    timezone: Optional[str] = None
    zonename: Optional[str] = None

    # Connection info
    amqp_host: Optional[str] = None
    bringup_at: Optional[int] = None
    ntp_synced: bool = True

    # Metadata
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionario."""
        data = asdict(self)
        for key in ['measure_datetime', 'created_at']:
            if isinstance(data.get(key), datetime):
                data[key] = data[key].isoformat()
        return data

    def to_json(self) -> str:
        """Converte para JSON."""
        return json.dumps(self.to_dict(), default=str)


@dataclass
class DeviceData:
    """
    Dados de um dispositivo (baseado em systemmodel.models.Device).
    """
    id: int
    serial: str
    title: str
    product_id: int
    company_id: int
    mac_address: str

    # Status
    status: int = 1  # 1 = ativo
    isVirtual: int = 0

    # Keys
    server_access_key: Optional[str] = None
    device_local_access_key: Optional[str] = None

    # Location
    gps_x: Optional[str] = None
    gps_y: Optional[str] = None
    state: Optional[str] = None
    local: Optional[str] = None

    # Configuration
    profile_id: Optional[int] = None
    card_profile_id: Optional[int] = None
    owner_device_id: Optional[int] = None
    connected_equipament: Optional[str] = None
    installed_phase: str = "ABC"
    installation_local: Optional[str] = None
    group: Optional[str] = None
    phases_ordering: str = "ABC"
    code: Optional[str] = None
    category: Optional[str] = None

    # Firmware
    softwareVer: Optional[str] = None
    hardwareVer: Optional[str] = None
    firmware_app_ver: Optional[str] = None
    firmware_metrol_ver: Optional[str] = None

    # Timezone
    timezone: int = -3
    olson_timezone: str = "America/Sao_Paulo"
    language: str = "pt-BR"

    # Dates
    created_at: Optional[datetime] = None
    installation_date: Optional[datetime] = None
    commissioning_date: Optional[datetime] = None
    descommissioning_date: Optional[datetime] = None
    last_change: Optional[datetime] = None
    last_online: Optional[datetime] = None
    last_sync: Optional[int] = None

    # States
    relay_state: Optional[int] = None
    installation_state: int = 1
    installation_status: str = "em operacao"

    # Features
    enable_bbd_home: int = 1
    enable_bbd_pro: int = 0
    enable_tseries_analytics: int = 0
    enable_gd_production: int = 0
    enable_advanced_monitoring: int = 1
    send_data: int = 1

    # Meter config
    relacao_tp: float = 1.0
    area_square_meters: Optional[float] = None

    # Data config
    data_source: Optional[str] = None
    pulse_multiplier: Optional[float] = None
    data_unit: str = "wh"
    data_type: str = "ENERGY"

    # LoRa/Sigmais
    lora_deveui: Optional[str] = None
    esp32_mac_address: Optional[str] = None
    sigmais_deveui: Optional[str] = None

    # Misc
    temperature_offset: float = 0.0
    is_vulnerable: bool = False
    is_critical: bool = False
    brand: Optional[str] = None
    reference_kwh: Optional[str] = None
    reference_number_of_days: Optional[str] = None
    generic_data: bool = False
    comments: Optional[str] = None

    # JSON fields (stored as string for CSV compatibility)
    extra_fields: str = "{}"
    category_json: str = "[]"
    generic_data_channels: str = "[]"

    # Account
    end_user_account: Optional[str] = None
    end_user_password: Optional[str] = None
    contrato_id: Optional[int] = None

    # FKs opcionais
    water_level_config_id: Optional[int] = None
    temperature_device_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionario."""
        data = asdict(self)
        for key in ['created_at', 'installation_date', 'commissioning_date',
                    'descommissioning_date', 'last_change', 'last_online']:
            if isinstance(data.get(key), datetime):
                data[key] = data[key].isoformat()
        return data

    def to_json(self) -> str:
        """Converte para JSON."""
        return json.dumps(self.to_dict(), default=str)

    @staticmethod
    def get_csv_headers() -> List[str]:
        """Retorna headers para CSV."""
        return [
            'id', 'serial', 'title', 'product_id', 'company_id', 'mac_address',
            'status', 'isVirtual', 'server_access_key', 'device_local_access_key',
            'gps_x', 'gps_y', 'state', 'local', 'profile_id', 'card_profile_id',
            'owner_device_id', 'connected_equipament', 'installed_phase',
            'installation_local', 'group', 'phases_ordering', 'code', 'category',
            'softwareVer', 'hardwareVer', 'firmware_app_ver', 'firmware_metrol_ver',
            'timezone', 'olson_timezone', 'language', 'created_at', 'installation_date',
            'commissioning_date', 'descommissioning_date', 'last_change', 'last_online',
            'last_sync', 'relay_state', 'installation_state', 'installation_status',
            'enable_bbd_home', 'enable_bbd_pro', 'enable_tseries_analytics',
            'enable_gd_production', 'enable_advanced_monitoring', 'send_data',
            'relacao_tp', 'area_square_meters', 'data_source', 'pulse_multiplier',
            'data_unit', 'data_type', 'lora_deveui', 'esp32_mac_address', 'sigmais_deveui',
            'temperature_offset', 'is_vulnerable', 'is_critical', 'brand',
            'reference_kwh', 'reference_number_of_days', 'generic_data', 'comments',
            'extra_fields', 'category_json', 'generic_data_channels',
            'end_user_account', 'end_user_password', 'contrato_id',
            'water_level_config_id', 'temperature_device_id'
        ]

    def to_csv_row(self) -> List[Any]:
        """Retorna valores para uma linha CSV."""
        data = self.to_dict()
        return [data.get(h) for h in self.get_csv_headers()]


def save_devices_to_csv(devices: List['DeviceData'], filepath: str) -> str:
    """
    Salva lista de devices em arquivo CSV.

    Args:
        devices: Lista de DeviceData
        filepath: Caminho do arquivo CSV

    Returns:
        Caminho absoluto do arquivo salvo
    """
    path = Path(filepath)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(DeviceData.get_csv_headers())
        for device in devices:
            writer.writerow(device.to_csv_row())
    return str(path.absolute())
