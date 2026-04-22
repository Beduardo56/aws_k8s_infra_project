"""
Geradores de dados fake para medidores de energia.
"""

import random
import math
from datetime import datetime, timedelta
from typing import List, Optional, Generator, Callable
from dataclasses import dataclass

from .models import DeviceConfig, InstantaneousData, SyncParametersData, DeviceData, save_devices_to_csv


def generate_mac_address() -> str:
    """Gera um MAC address aleatorio."""
    return ':'.join([f'{random.randint(0, 255):02x}' for _ in range(6)])


def generate_ip_address() -> str:
    """Gera um IP address privado aleatorio."""
    return f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"


def generate_bssid() -> str:
    """Gera um BSSID aleatorio."""
    return generate_mac_address().upper()


def generate_serial(prefix: str = "TE") -> str:
    """Gera um serial number aleatorio."""
    return f"{prefix}{random.randint(100000, 999999)}"


class InstantaneousGenerator:
    """Gerador de dados de medicoes instantaneas."""

    def __init__(
        self,
        device_config: DeviceConfig,
        load_profile: Optional[Callable[[datetime], float]] = None,
    ):
        """
        Args:
            device_config: Configuracao do dispositivo.
            load_profile: Funcao opcional que retorna fator de carga (0-1)
                         baseado no horario. Se None, usa perfil padrao.
        """
        self.config = device_config
        self.load_profile = load_profile or self._default_load_profile

    def _default_load_profile(self, dt: datetime) -> float:
        """
        Perfil de carga padrao baseado na hora do dia.
        Simula consumo comercial/industrial tipico.
        """
        hour = dt.hour
        # Madrugada (0-6): carga baixa
        if 0 <= hour < 6:
            return 0.2 + random.uniform(-0.05, 0.05)
        # Manha (6-12): subindo
        elif 6 <= hour < 12:
            return 0.5 + (hour - 6) * 0.08 + random.uniform(-0.05, 0.05)
        # Tarde (12-18): pico
        elif 12 <= hour < 18:
            return 0.85 + random.uniform(-0.1, 0.1)
        # Noite (18-22): descendo
        elif 18 <= hour < 22:
            return 0.6 - (hour - 18) * 0.1 + random.uniform(-0.05, 0.05)
        # Noite tardia (22-24): baixo
        else:
            return 0.3 + random.uniform(-0.05, 0.05)

    def _generate_voltage(self, phase_offset: float = 0) -> float:
        """Gera tensao de fase com variacao realista."""
        nominal = self.config.nominal_voltage
        variation = self.config.voltage_variation
        return nominal * (1 + random.uniform(-variation, variation))

    def _generate_current(self, load_factor: float) -> float:
        """Gera corrente baseada no fator de carga."""
        nominal = self.config.nominal_current
        variation = self.config.current_variation
        base_current = nominal * load_factor
        return max(0, base_current * (1 + random.uniform(-variation, variation)))

    def _calculate_line_voltages(
        self, va: float, vb: float, vc: float
    ) -> tuple:
        """
        Calcula tensoes de linha usando fasores.
        Assume sistema trifasico equilibrado com defasagem de 120 graus.
        """
        # Fasores de tensao de fase
        v_a = complex(va, 0)
        v_b = complex(vb * -0.5, vb * (math.sqrt(3) / 2))
        v_c = complex(vc * -0.5, -vc * (math.sqrt(3) / 2))

        voltage_ab = abs(v_a - v_b)
        voltage_bc = abs(v_b - v_c)
        voltage_ca = abs(v_c - v_a)

        return voltage_ab, voltage_bc, voltage_ca

    def generate(self, measured_at: datetime) -> InstantaneousData:
        """
        Gera um registro de medicao instantanea.

        Args:
            measured_at: Timestamp da medicao.

        Returns:
            InstantaneousData com valores realistas.
        """
        load_factor = max(0, min(1, self.load_profile(measured_at)))

        # Tensoes de fase
        voltage_a = self._generate_voltage()
        voltage_b = self._generate_voltage()
        voltage_c = self._generate_voltage()

        # Tensoes de linha
        voltage_ab, voltage_bc, voltage_ca = self._calculate_line_voltages(
            voltage_a, voltage_b, voltage_c
        )

        # Correntes
        current_a = self._generate_current(load_factor)
        current_b = self._generate_current(load_factor)
        current_c = self._generate_current(load_factor)

        # Fator de potencia com pequena variacao
        pf_base = self.config.power_factor
        pf_a = min(1, max(0, pf_base + random.uniform(-0.05, 0.05)))
        pf_b = min(1, max(0, pf_base + random.uniform(-0.05, 0.05)))
        pf_c = min(1, max(0, pf_base + random.uniform(-0.05, 0.05)))

        # Potencia aparente (S = V * I)
        apparent_power_a = voltage_a * current_a
        apparent_power_b = voltage_b * current_b
        apparent_power_c = voltage_c * current_c
        threephase_apparent_power = apparent_power_a + apparent_power_b + apparent_power_c

        # Potencia ativa (P = S * pf)
        active_power_a = apparent_power_a * pf_a
        active_power_b = apparent_power_b * pf_b
        active_power_c = apparent_power_c * pf_c
        threephase_active_power = active_power_a + active_power_b + active_power_c

        # Potencia reativa (Q = sqrt(S^2 - P^2))
        reactive_power_a = math.sqrt(max(0, apparent_power_a**2 - active_power_a**2))
        reactive_power_b = math.sqrt(max(0, apparent_power_b**2 - active_power_b**2))
        reactive_power_c = math.sqrt(max(0, apparent_power_c**2 - active_power_c**2))
        threephase_reactive_power = reactive_power_a + reactive_power_b + reactive_power_c

        # Frequencia (60Hz no Brasil com pequena variacao)
        freq_base = 60.0
        frequency_a = freq_base + random.uniform(-0.1, 0.1)
        frequency_b = freq_base + random.uniform(-0.1, 0.1)
        frequency_c = freq_base + random.uniform(-0.1, 0.1)

        # Angulos de fase (defasagem de 120 graus)
        angle_a = 0.0 + random.uniform(-2, 2)
        angle_b = 120.0 + random.uniform(-2, 2)
        angle_c = 240.0 + random.uniform(-2, 2)

        # Temperatura do equipamento
        temperature = 35.0 + random.uniform(-5, 15)

        # Corrente de neutro (desequilibrio)
        neutral_current = abs(current_a - current_b) * random.uniform(0, 0.3)

        return InstantaneousData(
            device_id=self.config.device_id,
            measured_at=measured_at,
            mac_address=self.config.mac_address,
            voltage_a=round(voltage_a, 2),
            voltage_b=round(voltage_b, 2),
            voltage_c=round(voltage_c, 2),
            voltage_ab=round(voltage_ab, 2),
            voltage_bc=round(voltage_bc, 2),
            voltage_ca=round(voltage_ca, 2),
            current_a=round(current_a, 2),
            current_b=round(current_b, 2),
            current_c=round(current_c, 2),
            active_power_a=round(active_power_a, 2),
            active_power_b=round(active_power_b, 2),
            active_power_c=round(active_power_c, 2),
            threephase_active_power=round(threephase_active_power, 2),
            reactive_power_a=round(reactive_power_a, 2),
            reactive_power_b=round(reactive_power_b, 2),
            reactive_power_c=round(reactive_power_c, 2),
            threephase_reactive_power=round(threephase_reactive_power, 2),
            apparent_power_a=round(apparent_power_a, 2),
            apparent_power_b=round(apparent_power_b, 2),
            apparent_power_c=round(apparent_power_c, 2),
            threephase_apparent_power=round(threephase_apparent_power, 2),
            frequency_a=round(frequency_a, 2),
            frequency_b=round(frequency_b, 2),
            frequency_c=round(frequency_c, 2),
            power_factor_a=round(pf_a, 3),
            power_factor_b=round(pf_b, 3),
            power_factor_c=round(pf_c, 3),
            temperature=round(temperature, 1),
            angle_a=round(angle_a, 1),
            angle_b=round(angle_b, 1),
            angle_c=round(angle_c, 1),
            neutral_current=round(neutral_current, 2),
            timezone=-3,  # BRT
            daylight_saving_time=0,
        )

    def generate_range(
        self,
        start_time: datetime,
        end_time: datetime,
        interval_seconds: int = 60,
    ) -> Generator[InstantaneousData, None, None]:
        """
        Gera medicoes para um intervalo de tempo.

        Args:
            start_time: Inicio do periodo.
            end_time: Fim do periodo.
            interval_seconds: Intervalo entre medicoes em segundos.

        Yields:
            InstantaneousData para cada timestamp.
        """
        current = start_time
        while current <= end_time:
            yield self.generate(current)
            current += timedelta(seconds=interval_seconds)


class DeviceGenerator:
    """Gerador de dados de dispositivos."""

    def __init__(
        self,
        start_id: int = 1000,
        company_id: int = 1,
        product_id: int = 14,
    ):
        """
        Args:
            start_id: ID inicial para devices.
            company_id: ID da company para todos os devices.
            product_id: ID do produto (14 = medidor WiFi padrao).
        """
        self.start_id = start_id
        self.company_id = company_id
        self.product_id = product_id
        self._current_id = start_id

    def generate(self, device_id: Optional[int] = None) -> DeviceData:
        """
        Gera um device.

        Args:
            device_id: ID especifico. Se None, usa sequencial.

        Returns:
            DeviceData com dados fake.
        """
        if device_id is None:
            device_id = self._current_id
            self._current_id += 1

        mac = generate_mac_address()
        serial = generate_serial()
        now = datetime.now()

        return DeviceData(
            id=device_id,
            serial=serial,
            title=f"Medidor {device_id}",
            product_id=self.product_id,
            company_id=self.company_id,
            mac_address=mac,
            status=1,
            isVirtual=0,
            server_access_key=f"srv_{serial}_{random.randint(1000, 9999)}",
            device_local_access_key=f"dev_{serial}_{random.randint(1000, 9999)}",
            gps_x=str(round(-23.5 + random.uniform(-1, 1), 6)),
            gps_y=str(round(-46.6 + random.uniform(-1, 1), 6)),
            state="SP",
            local="Sala de Energia",
            installed_phase="ABC",
            installation_local="QD Principal",
            group=f"Grupo {random.randint(1, 5)}",
            phases_ordering="ABC",
            code=f"COD{device_id:05d}",
            category="Energia",
            softwareVer=f"1.{random.randint(0, 9)}.{random.randint(0, 99)}",
            hardwareVer=f"2.{random.randint(0, 5)}",
            firmware_app_ver=f"2.{random.randint(0, 9)}.{random.randint(0, 99)}",
            firmware_metrol_ver=f"1.{random.randint(0, 9)}.{random.randint(0, 99)}",
            timezone=-3,
            olson_timezone="America/Sao_Paulo",
            language="pt-BR",
            created_at=now - timedelta(days=random.randint(30, 365)),
            installation_date=now - timedelta(days=random.randint(1, 30)),
            commissioning_date=now - timedelta(days=random.randint(1, 30)),
            last_change=now,
            last_online=now - timedelta(minutes=random.randint(0, 60)),
            last_sync=int((now - timedelta(minutes=random.randint(0, 30))).timestamp()),
            installation_state=1,
            installation_status="em operacao",
            enable_bbd_home=1,
            enable_bbd_pro=0,
            enable_tseries_analytics=1,
            enable_gd_production=0,
            enable_advanced_monitoring=1,
            send_data=1,
            relacao_tp=1.0,
            data_unit="wh",
            data_type="ENERGY",
            esp32_mac_address=mac,
            extra_fields="{}",
            category_json="[]",
            generic_data_channels="[]",
        )

    def generate_multiple(self, count: int) -> List[DeviceData]:
        """
        Gera multiplos devices.

        Args:
            count: Quantidade de devices a gerar.

        Returns:
            Lista de DeviceData.
        """
        return [self.generate() for _ in range(count)]

    def generate_and_save_csv(self, count: int, filepath: str) -> str:
        """
        Gera devices e salva em CSV.

        Args:
            count: Quantidade de devices.
            filepath: Caminho do arquivo CSV.

        Returns:
            Caminho absoluto do arquivo salvo.
        """
        devices = self.generate_multiple(count)
        return save_devices_to_csv(devices, filepath)


class SyncParametersGenerator:
    """Gerador de dados de sync parameters."""

    def __init__(self, device_config: DeviceConfig):
        self.config = device_config
        self._uptime_start = datetime.now()

    def generate(self, measure_datetime: datetime) -> SyncParametersData:
        """
        Gera um registro de sync parameters.

        Args:
            measure_datetime: Timestamp da medicao.

        Returns:
            SyncParametersData com valores realistas.
        """
        # Calcula uptime desde inicio
        uptime_seconds = int((measure_datetime - self._uptime_start).total_seconds())
        if uptime_seconds < 0:
            uptime_seconds = random.randint(3600, 86400 * 30)

        # WiFi signal com variacao
        wifi_min, wifi_max = self.config.wifi_signal_range
        wifi_signal = random.uniform(wifi_min, wifi_max)

        return SyncParametersData(
            device_id=self.config.device_id,
            measure_datetime=measure_datetime,
            serial=self.config.serial,
            wifi_signal=round(wifi_signal, 1),
            wifi_ssid=self.config.wifi_ssid,
            wifi_bssid=generate_bssid(),
            wifi_ip_address=generate_ip_address(),
            wifi_noise=random.randint(-100, -70),
            uptime=uptime_seconds,
            mac_address=self.config.mac_address,
            product_id=self.config.product_id,
            meter_tc_polarity=1,
            meter_tc_ratio=1,
            firmware_metrol_ver=f"1.{random.randint(0, 9)}.{random.randint(0, 99)}",
            firmware_app_ver=f"2.{random.randint(0, 9)}.{random.randint(0, 99)}",
            enable_meter_energy_interruptions=True,
            enable_meter_instantaneous_values=True,
            enable_meter_load_packets=False,
            enable_meter_registers=True,
            enable_meter_harmonics=random.choice([True, False]),
            enable_meter_unified_load_packets=False,
            enable_meter_recording_memory_last_register=True,
            enable_meter_registers_aligned_recording_memory=True,
            meter_recording_memory_channels="1,2,3,4",
            meter_recording_memory_period=900,
            meter_recording_memory_records=96,
            full_sync_params={
                "version": "1.0",
                "device_id": self.config.device_id,
                "timestamp": measure_datetime.isoformat(),
            },
            timezone="-03:00",
            zonename="America/Sao_Paulo",
            amqp_host="broker.timeenergy.com.br",
            bringup_at=int(self._uptime_start.timestamp()),
            ntp_synced=True,
            created_at=datetime.now(),
        )

    def generate_range(
        self,
        start_time: datetime,
        end_time: datetime,
        interval_seconds: int = 300,  # sync params tipicamente a cada 5 min
    ) -> Generator[SyncParametersData, None, None]:
        """
        Gera sync parameters para um intervalo de tempo.

        Args:
            start_time: Inicio do periodo.
            end_time: Fim do periodo.
            interval_seconds: Intervalo entre registros em segundos.

        Yields:
            SyncParametersData para cada timestamp.
        """
        current = start_time
        while current <= end_time:
            yield self.generate(current)
            current += timedelta(seconds=interval_seconds)


class FakeDataOrchestrator:
    """
    Orquestrador para geracao de dados fake de multiplos dispositivos.
    """

    def __init__(
        self,
        num_devices: int = 4,
        instantaneous_frequency_seconds: int = 60,
        sync_params_frequency_seconds: int = 300,
        duration_minutes: int = 60,
        start_time: Optional[datetime] = None,
        device_configs: Optional[List[DeviceConfig]] = None,
        company_id: int = 1,
        product_id: int = 14,
        start_device_id: int = 1000,
    ):
        """
        Args:
            num_devices: Numero de dispositivos a simular.
            instantaneous_frequency_seconds: Intervalo entre medicoes instantaneas (padrao: 60s).
            sync_params_frequency_seconds: Intervalo entre sync parameters (padrao: 300s = 5min).
            duration_minutes: Duracao total da geracao em minutos.
            start_time: Timestamp inicial. Se None, usa agora.
            device_configs: Lista de configs customizadas. Se None, gera automaticamente.
            company_id: ID da company para devices gerados.
            product_id: ID do produto para devices gerados.
            start_device_id: ID inicial para devices.
        """
        self.num_devices = num_devices
        self.instantaneous_frequency_seconds = instantaneous_frequency_seconds
        self.sync_params_frequency_seconds = sync_params_frequency_seconds
        self.duration_minutes = duration_minutes
        self.start_time = start_time or datetime.now()
        self.end_time = self.start_time + timedelta(minutes=duration_minutes)
        self.company_id = company_id
        self.product_id = product_id
        self.start_device_id = start_device_id

        # Cria gerador de devices
        self.device_generator = DeviceGenerator(
            start_id=start_device_id,
            company_id=company_id,
            product_id=product_id,
        )

        # Cria ou usa configs de dispositivos
        if device_configs:
            self.device_configs = device_configs
            self.devices = None  # Nao gera DeviceData se configs customizadas
        else:
            self.devices = self.device_generator.generate_multiple(num_devices)
            self.device_configs = self._generate_device_configs_from_devices()

        # Cria geradores
        self.instantaneous_generators = [
            InstantaneousGenerator(config) for config in self.device_configs
        ]
        self.sync_generators = [
            SyncParametersGenerator(config) for config in self.device_configs
        ]

    def _generate_device_configs(self) -> List[DeviceConfig]:
        """Gera configs automaticas para os dispositivos (sem DeviceData)."""
        configs = []
        for i in range(self.num_devices):
            config = DeviceConfig(
                device_id=self.start_device_id + i,
                mac_address=generate_mac_address(),
                serial=generate_serial(),
                product_id=self.product_id,
                nominal_voltage=220.0 + random.uniform(-10, 10),
                nominal_current=30.0 + random.uniform(0, 70),
                power_factor=0.85 + random.uniform(0, 0.1),
            )
            configs.append(config)
        return configs

    def _generate_device_configs_from_devices(self) -> List[DeviceConfig]:
        """Gera configs a partir dos DeviceData gerados."""
        configs = []
        for device in self.devices:
            config = DeviceConfig(
                device_id=device.id,
                mac_address=device.mac_address,
                serial=device.serial,
                product_id=device.product_id,
                nominal_voltage=220.0 + random.uniform(-10, 10),
                nominal_current=30.0 + random.uniform(0, 70),
                power_factor=0.85 + random.uniform(0, 0.1),
            )
            configs.append(config)
        return configs

    def generate_devices(self) -> List[DeviceData]:
        """
        Retorna lista de devices gerados.

        Returns:
            Lista de DeviceData ou lista vazia se configs customizadas.
        """
        if self.devices is None:
            # Gera devices a partir das configs customizadas
            self.devices = []
            for config in self.device_configs:
                device = DeviceData(
                    id=config.device_id,
                    serial=config.serial,
                    title=f"Medidor {config.device_id}",
                    product_id=config.product_id,
                    company_id=self.company_id,
                    mac_address=config.mac_address,
                )
                self.devices.append(device)
        return self.devices

    def save_devices_csv(self, filepath: str = "devices.csv") -> str:
        """
        Salva devices em arquivo CSV.

        Args:
            filepath: Caminho do arquivo CSV.

        Returns:
            Caminho absoluto do arquivo salvo.
        """
        devices = self.generate_devices()
        return save_devices_to_csv(devices, filepath)

    def generate_instantaneous(
        self,
        interval_seconds: Optional[int] = None,
    ) -> List[InstantaneousData]:
        """
        Gera todos os dados de medicoes instantaneas.

        Args:
            interval_seconds: Intervalo customizado. Se None, usa o configurado.

        Returns:
            Lista com todos os registros de todos os dispositivos.
        """
        interval = interval_seconds or self.instantaneous_frequency_seconds
        all_data = []
        for generator in self.instantaneous_generators:
            data = list(generator.generate_range(
                self.start_time,
                self.end_time,
                interval,
            ))
            all_data.extend(data)
        return all_data

    def generate_sync_parameters(
        self,
        interval_seconds: Optional[int] = None,
    ) -> List[SyncParametersData]:
        """
        Gera todos os dados de sync parameters.

        Args:
            interval_seconds: Intervalo customizado. Se None, usa o configurado.

        Returns:
            Lista com todos os registros de todos os dispositivos.
        """
        interval = interval_seconds or self.sync_params_frequency_seconds
        all_data = []
        for generator in self.sync_generators:
            data = list(generator.generate_range(
                self.start_time,
                self.end_time,
                interval,
            ))
            all_data.extend(data)
        return all_data

    def generate_all(self) -> dict:
        """
        Gera todos os tipos de dados.

        Returns:
            Dict com 'devices', 'instantaneous' e 'sync_parameters'.
        """
        return {
            "devices": self.generate_devices(),
            "instantaneous": self.generate_instantaneous(),
            "sync_parameters": self.generate_sync_parameters(),
        }

    def stream_instantaneous(
        self,
        interval_seconds: Optional[int] = None,
    ) -> Generator[InstantaneousData, None, None]:
        """
        Gera dados de forma lazy (generator) para economia de memoria.

        Args:
            interval_seconds: Intervalo customizado. Se None, usa o configurado.

        Yields:
            InstantaneousData intercalando todos os dispositivos.
        """
        interval = interval_seconds or self.instantaneous_frequency_seconds
        current = self.start_time
        while current <= self.end_time:
            for generator in self.instantaneous_generators:
                yield generator.generate(current)
            current += timedelta(seconds=interval)

    def to_dataframe(self, data_type: str = "instantaneous"):
        """
        Converte dados para pandas DataFrame.

        Args:
            data_type: 'instantaneous' ou 'sync_parameters'

        Returns:
            pandas DataFrame
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas is required for to_dataframe()")

        if data_type == "instantaneous":
            data = self.generate_instantaneous()
        elif data_type == "sync_parameters":
            data = self.generate_sync_parameters()
        else:
            raise ValueError(f"Unknown data_type: {data_type}")

        return pd.DataFrame([d.to_dict() for d in data])
