# Fake Data Generator

Gerador de dados fake para medidores de energia. Gera dados realistas de:

- **InstantaneousValues**: medições instantâneas (tensão, corrente, potência, etc.)
- **DeviceSyncParameters**: parâmetros de sincronização de dispositivos

## Instalação

Copie a pasta `fake_data_generator` para seu projeto. Dependências:

```bash
pip install dataclasses  # Python < 3.7 apenas
pip install pandas       # opcional, para export DataFrame
```

## Uso Básico

```python
from fake_data_generator import FakeDataOrchestrator

# Gera dados para 4 dispositivos por 1 hora
orchestrator = FakeDataOrchestrator(
    num_devices=4,
    instantaneous_frequency_seconds=60,   # medição instantânea a cada 1 minuto
    sync_params_frequency_seconds=300,    # sync params a cada 5 minutos
    duration_minutes=60,
)

# Gera todos os dados (devices + instantaneous + sync_params)
all_data = orchestrator.generate_all()
devices = all_data['devices']
instantaneous = all_data['instantaneous']
sync_params = all_data['sync_parameters']

# Ou gera separadamente
devices = orchestrator.generate_devices()
instantaneous = orchestrator.generate_instantaneous()
sync_params = orchestrator.generate_sync_parameters()

# Salva devices em CSV
csv_path = orchestrator.save_devices_csv("devices.csv")
```

## Gerando Devices e Exportando CSV

```python
from fake_data_generator import DeviceGenerator, FakeDataOrchestrator

# Usando DeviceGenerator diretamente
generator = DeviceGenerator(
    start_id=1000,
    company_id=5,
    product_id=14,
)

# Gera 4 devices
devices = generator.generate_multiple(4)

# Gera e salva direto em CSV
csv_path = generator.generate_and_save_csv(4, "devices.csv")

# Ou usando o Orchestrator
orchestrator = FakeDataOrchestrator(
    num_devices=4,
    company_id=10,
    start_device_id=2000,
)
csv_path = orchestrator.save_devices_csv("devices.csv")
```

## Configuração de Dispositivos

```python
from fake_data_generator import DeviceConfig, FakeDataOrchestrator

devices = [
    DeviceConfig(
        device_id=101,
        mac_address="aa:bb:cc:dd:ee:01",
        serial="TE123001",
        nominal_voltage=220,
        nominal_current=100,
        power_factor=0.95,
    ),
    DeviceConfig(
        device_id=102,
        mac_address="aa:bb:cc:dd:ee:02",
        serial="TE123002",
        nominal_voltage=380,
        nominal_current=200,
        power_factor=0.88,
    ),
]

orchestrator = FakeDataOrchestrator(
    num_devices=2,
    frequency_seconds=30,
    duration_minutes=60,
    device_configs=devices,
)
```

## Perfil de Carga Customizado

```python
from datetime import datetime
from fake_data_generator import InstantaneousGenerator, DeviceConfig

# Perfil para comércio
def comercial_profile(dt: datetime) -> float:
    hour = dt.hour
    if 9 <= hour <= 18:
        return 0.9   # 90% no horário comercial
    elif 6 <= hour < 9 or 18 < hour <= 21:
        return 0.5   # 50% transição
    else:
        return 0.1   # 10% fechado

config = DeviceConfig(device_id=1, mac_address="...", serial="...")
generator = InstantaneousGenerator(config, load_profile=comercial_profile)
```

## Streaming (economia de memória)

```python
orchestrator = FakeDataOrchestrator(num_devices=10, duration_minutes=1440)

# Processa sem carregar tudo em memória
for record in orchestrator.stream_instantaneous():
    process(record)  # processa um registro por vez
```

## Export

### JSON
```python
import json

data = orchestrator.generate_instantaneous()
json_data = [r.to_dict() for r in data]
json.dumps(json_data)
```

### DataFrame (pandas)
```python
df = orchestrator.to_dataframe("instantaneous")
df_sync = orchestrator.to_dataframe("sync_parameters")
```

## Estrutura de Dados

### DeviceData

Baseado em `systemmodel.models.Device`. Campos principais:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | int | ID do dispositivo |
| serial | str | Número de série |
| title | str | Nome/título do device |
| product_id | int | ID do produto |
| company_id | int | ID da empresa |
| mac_address | str | Endereço MAC |
| status | int | Status (1=ativo) |
| firmware_app_ver | str | Versão do firmware app |
| olson_timezone | str | Timezone (ex: America/Sao_Paulo) |
| installation_status | str | Status de instalação |
| ... | ... | + 50 outros campos |

### InstantaneousData

| Campo | Tipo | Descrição |
|-------|------|-----------|
| device_id | int | ID do dispositivo |
| measured_at | datetime | Timestamp da medição |
| voltage_a/b/c | float | Tensão de fase (V) |
| voltage_ab/bc/ca | float | Tensão de linha (V) |
| current_a/b/c | float | Corrente (A) |
| active_power_a/b/c | float | Potência ativa (W) |
| threephase_active_power | float | Potência ativa trifásica (W) |
| reactive_power_* | float | Potência reativa (VAr) |
| apparent_power_* | float | Potência aparente (VA) |
| frequency_a/b/c | float | Frequência (Hz) |
| power_factor_a/b/c | float | Fator de potência |
| temperature | float | Temperatura (°C) |
| angle_a/b/c | float | Ângulo de fase (°) |
| neutral_current | float | Corrente de neutro (A) |

### SyncParametersData

| Campo | Tipo | Descrição |
|-------|------|-----------|
| device_id | int | ID do dispositivo |
| measure_datetime | datetime | Timestamp |
| serial | str | Número de série |
| wifi_signal | float | Sinal WiFi (dBm) |
| wifi_ssid/bssid | str | SSID e BSSID |
| wifi_ip_address | str | Endereço IP |
| uptime | int | Tempo ligado (segundos) |
| firmware_*_ver | str | Versões de firmware |
| enable_meter_* | bool | Flags de features |
| timezone/zonename | str | Fuso horário |

## Executar Exemplos

```bash
cd fake_data_generator
python example.py
```
