#!/usr/bin/env python3
"""
Exemplo de uso do Fake Data Generator.

Execute este arquivo para ver exemplos de geracao de dados.
"""

from datetime import datetime, timedelta
from fake_data_generator import (
    FakeDataOrchestrator,
    InstantaneousGenerator,
    SyncParametersGenerator,
    DeviceGenerator,
    DeviceConfig,
)


def exemplo_basico():
    """Exemplo basico: gerar dados para 4 dispositivos por 1 hora."""
    print("=" * 60)
    print("EXEMPLO BASICO")
    print("=" * 60)

    orchestrator = FakeDataOrchestrator(
        num_devices=4,
        instantaneous_frequency_seconds=60,   # 1 medicao instantanea por minuto
        sync_params_frequency_seconds=300,    # sync params a cada 5 minutos
        duration_minutes=60,                  # 1 hora de dados
        company_id=1,                         # ID da company
        start_device_id=1000,                 # ID inicial dos devices
    )

    # Gera todos os dados
    all_data = orchestrator.generate_all()

    print(f"Devices gerados: {len(all_data['devices'])}")
    print(f"Instantaneous records: {len(all_data['instantaneous'])}")
    print(f"Sync parameters records: {len(all_data['sync_parameters'])}")

    # Mostra devices
    for device in all_data['devices']:
        print(f"  Device {device.id}: {device.serial} - {device.mac_address}")

    # Mostra primeiro registro
    if all_data['instantaneous']:
        first = all_data['instantaneous'][0]
        print(f"\nPrimeiro registro instantaneous:")
        print(f"  Device: {first.device_id}")
        print(f"  Time: {first.measured_at}")
        print(f"  Voltage A: {first.voltage_a}V")
        print(f"  Current A: {first.current_a}A")
        print(f"  Active Power: {first.threephase_active_power}W")


def exemplo_devices_csv():
    """Exemplo gerando devices e salvando em CSV."""
    print("\n" + "=" * 60)
    print("EXEMPLO DEVICES + CSV")
    print("=" * 60)

    # Usando DeviceGenerator diretamente
    generator = DeviceGenerator(
        start_id=2000,
        company_id=5,
        product_id=14,
    )

    # Gera 3 devices
    devices = generator.generate_multiple(3)
    for d in devices:
        print(f"Device {d.id}: {d.serial} | {d.mac_address} | {d.title}")

    # Salva em CSV
    csv_path = generator.generate_and_save_csv(3, "/tmp/devices_example.csv")
    print(f"\nCSV salvo em: {csv_path}")

    # Usando FakeDataOrchestrator
    orchestrator = FakeDataOrchestrator(
        num_devices=2,
        instantaneous_frequency_seconds=60,
        sync_params_frequency_seconds=300,
        duration_minutes=5,
        company_id=10,
        start_device_id=5000,
    )

    # Salva devices do orchestrator
    csv_path2 = orchestrator.save_devices_csv("/tmp/orchestrator_devices.csv")
    print(f"CSV do orchestrator salvo em: {csv_path2}")

    # Mostra conteudo do CSV
    print("\nConteudo do CSV (primeiras 5 colunas):")
    with open(csv_path2, 'r') as f:
        import csv
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i < 4:  # header + 2 devices
                print(f"  {row[:5]}...")


def exemplo_customizado():
    """Exemplo com configuracao customizada de dispositivos."""
    print("\n" + "=" * 60)
    print("EXEMPLO COM CONFIGURACAO CUSTOMIZADA")
    print("=" * 60)

    # Define dispositivos com caracteristicas especificas
    devices = [
        DeviceConfig(
            device_id=101,
            mac_address="aa:bb:cc:dd:ee:01",
            serial="TE123001",
            nominal_voltage=220,
            nominal_current=100,  # Alta carga
            power_factor=0.95,
        ),
        DeviceConfig(
            device_id=102,
            mac_address="aa:bb:cc:dd:ee:02",
            serial="TE123002",
            nominal_voltage=380,  # Trifasico industrial
            nominal_current=200,
            power_factor=0.88,
        ),
    ]

    orchestrator = FakeDataOrchestrator(
        num_devices=2,
        instantaneous_frequency_seconds=30,   # Medicao a cada 30 segundos
        sync_params_frequency_seconds=60,     # Sync a cada 1 minuto
        duration_minutes=5,
        device_configs=devices,
    )

    instantaneous = orchestrator.generate_instantaneous()
    print(f"Registros gerados: {len(instantaneous)}")

    # Agrupa por device
    by_device = {}
    for record in instantaneous:
        if record.device_id not in by_device:
            by_device[record.device_id] = []
        by_device[record.device_id].append(record)

    for device_id, records in by_device.items():
        avg_power = sum(r.threephase_active_power for r in records) / len(records)
        print(f"Device {device_id}: {len(records)} registros, potencia media: {avg_power:.2f}W")


def exemplo_streaming():
    """Exemplo usando generator para economia de memoria."""
    print("\n" + "=" * 60)
    print("EXEMPLO STREAMING (GENERATOR)")
    print("=" * 60)

    orchestrator = FakeDataOrchestrator(
        num_devices=2,
        instantaneous_frequency_seconds=60,
        sync_params_frequency_seconds=120,
        duration_minutes=10,
    )

    # Processa dados sem carregar tudo em memoria
    count = 0
    total_power = 0
    for record in orchestrator.stream_instantaneous():
        count += 1
        total_power += record.threephase_active_power

        # Processa em batches
        if count % 10 == 0:
            print(f"Processados {count} registros...")

    print(f"Total: {count} registros")
    print(f"Potencia media geral: {total_power / count:.2f}W")


def exemplo_perfil_carga_customizado():
    """Exemplo com perfil de carga customizado."""
    print("\n" + "=" * 60)
    print("EXEMPLO COM PERFIL DE CARGA CUSTOMIZADO")
    print("=" * 60)

    # Perfil de carga para data center (carga constante)
    def datacenter_profile(dt: datetime) -> float:
        return 0.85  # 85% constante

    # Perfil de carga para comercio (pico no horario comercial)
    def comercial_profile(dt: datetime) -> float:
        hour = dt.hour
        if 9 <= hour <= 18:
            return 0.9
        elif 6 <= hour < 9 or 18 < hour <= 21:
            return 0.5
        else:
            return 0.1

    config = DeviceConfig(
        device_id=200,
        mac_address="00:11:22:33:44:55",
        serial="TE200001",
        nominal_voltage=220,
        nominal_current=50,
    )

    # Gerador com perfil de data center
    generator = InstantaneousGenerator(config, load_profile=datacenter_profile)

    start = datetime(2024, 1, 15, 0, 0)
    end = datetime(2024, 1, 15, 23, 59)

    records = list(generator.generate_range(start, end, interval_seconds=3600))

    print("Perfil Data Center (carga constante):")
    for r in records[:6]:
        print(f"  {r.measured_at.strftime('%H:%M')} - {r.threephase_active_power:.0f}W")


def exemplo_export_json():
    """Exemplo exportando para JSON."""
    print("\n" + "=" * 60)
    print("EXEMPLO EXPORT JSON")
    print("=" * 60)

    orchestrator = FakeDataOrchestrator(
        num_devices=1,
        instantaneous_frequency_seconds=300,
        sync_params_frequency_seconds=300,
        duration_minutes=15,
    )

    instantaneous = orchestrator.generate_instantaneous()
    sync_params = orchestrator.generate_sync_parameters()

    # Exporta para JSON
    import json

    instantaneous_json = [r.to_dict() for r in instantaneous]
    sync_params_json = [r.to_dict() for r in sync_params]

    print(f"Instantaneous (primeiros 2 registros):")
    print(json.dumps(instantaneous_json[:2], indent=2, default=str))

    print(f"\nSync Parameters (primeiro registro):")
    print(json.dumps(sync_params_json[:1], indent=2, default=str))


def exemplo_pandas():
    """Exemplo convertendo para pandas DataFrame."""
    print("\n" + "=" * 60)
    print("EXEMPLO PANDAS DATAFRAME")
    print("=" * 60)

    try:
        import pandas as pd
    except ImportError:
        print("pandas nao instalado, pulando exemplo...")
        return

    orchestrator = FakeDataOrchestrator(
        num_devices=2,
        instantaneous_frequency_seconds=60,
        sync_params_frequency_seconds=300,
        duration_minutes=30,
    )

    df = orchestrator.to_dataframe("instantaneous")

    print(f"DataFrame shape: {df.shape}")
    print(f"\nColunas: {list(df.columns)[:10]}...")
    print(f"\nEstatisticas de potencia ativa trifasica:")
    print(df['threephase_active_power'].describe())

    # Agrupa por dispositivo
    print(f"\nMedia por dispositivo:")
    print(df.groupby('device_id')['threephase_active_power'].mean())


if __name__ == "__main__":
    exemplo_basico()
    exemplo_devices_csv()
    exemplo_customizado()
    exemplo_streaming()
    exemplo_perfil_carga_customizado()
    exemplo_export_json()
    exemplo_pandas()

    print("\n" + "=" * 60)
    print("TODOS OS EXEMPLOS EXECUTADOS COM SUCESSO!")
    print("=" * 60)
