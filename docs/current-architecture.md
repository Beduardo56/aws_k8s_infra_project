# Arquitetura Atual - Nuvem Privada CL9

**Documento**: Arquitetura de Referência
**Versão**: 1.0
**Data**: 2026-03-06
**Propósito**: Documentar a infraestrutura atual para servir como base do projeto de DR na AWS

---

## 1. Visão Geral

A infraestrutura atual opera em uma nuvem privada (CL9) com os seguintes componentes principais:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            ┌───────────┐   ┌───────────┐   ┌───────────┐
            │ Hostgator │   │  GoDaddy  │   │   AWS     │
            │   (DNS)   │   │(DNS+Cert) │   │(Route53)  │
            └───────────┘   └───────────┘   └───────────┘
                    │               │               │
                    └───────────────┼───────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           pfSense (Firewall/Router)                          │
│                                                                              │
│  ┌─────────────────────────────┐    ┌─────────────────────────────────────┐ │
│  │   Subnet Administração      │    │      Subnet Dispositivos            │ │
│  │      10.11.144.0/24         │    │         10.12.0.0/16                │ │
│  │                             │    │                                      │ │
│  │  ┌─────────────────────┐   │    │   (IoT devices, endpoints, etc.)    │ │
│  │  │    Kubernetes       │   │    │                                      │ │
│  │  │  ┌─────────────┐    │   │    └─────────────────────────────────────┘ │
│  │  │  │  Ingress    │◄───┼───┼────── Frontend/Backend traffic             │
│  │  │  └─────────────┘    │   │                                            │
│  │  │  ┌─────────────┐    │   │                                            │
│  │  │  │   ArgoCD    │    │   │                                            │
│  │  │  │   Spark     │    │   │                                            │
│  │  │  │   Trino     │    │   │                                            │
│  │  │  │   Airbyte   │    │   │                                            │
│  │  │  │   Velero    │    │   │                                            │
│  │  │  │   (apps)    │    │   │                                            │
│  │  │  └─────────────┘    │   │                                            │
│  │  └─────────────────────┘   │                                            │
│  │                             │                                            │
│  │  ┌──────────┐ ┌──────────┐ │                                            │
│  │  │ RabbitMQ │ │  MinIO   │◄┼────── IP Público                           │
│  │  │ (público)│ │(público) │ │                                            │
│  │  └──────────┘ └──────────┘ │                                            │
│  │                             │                                            │
│  │  ┌──────────┐ ┌──────────┐ │                                            │
│  │  │  MySQL   │ │Timescale │ │                                            │
│  │  └──────────┘ └──────────┘ │                                            │
│  │                             │                                            │
│  │  ┌──────────┐ ┌──────────┐ │                                            │
│  │  │  Redis   │ │ OpenVPN  │◄┼────── Acesso VPN (devs/admins)             │
│  │  └──────────┘ └──────────┘ │                                            │
│  │                             │                                            │
│  └─────────────────────────────┘                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Gestão de DNS e Certificados

### 2.1 Provedores de DNS

| Provedor   | Domínio Principal      | Função                    |
|------------|------------------------|---------------------------|
| Hostgator  | timeenergy.com.br      | DNS primário              |
| GoDaddy    | timeenergy.com.br      | DNS + Certificados SSL    |
| AWS Route53| neras.io               | DNS (frontend em S3)      |

### 2.2 Domínios e Endpoints

| Domínio                              | Serviço           | Ambiente   | Observações                |
|--------------------------------------|-------------------|------------|----------------------------|
| broker.timeenergy.com.br             | RabbitMQ          | Produção   | Acesso via IP público      |
| broker2.timeenergy.com.br            | RabbitMQ          | Staging    | Acesso via IP público      |
| services.backend.timeenergy.com.br   | Backend API       | Produção   | Via Ingress K8s            |
| beta.services.backend.timeenergy.com.br | Backend API    | Beta       | Via Ingress K8s            |
| [5º endpoint - a definir]            | ?                 | ?          | Necessita esclarecimento   |
| neras.io                             | Frontend          | Produção   | Hospedado no AWS S3        |

---

## 3. Topologia de Rede

### 3.1 VPC Principal (pfSense)

A rede é gerenciada pelo pfSense, que atua como firewall e roteador principal.

#### Subnet de Administração
- **CIDR**: `10.11.144.0/24`
- **Capacidade**: 254 hosts
- **Propósito**: Serviços de infraestrutura e aplicações
- **Componentes**:
  - Cluster Kubernetes
  - Bancos de dados (MySQL, TimescaleDB, Redis)
  - Message broker (RabbitMQ)
  - Object storage (MinIO)
  - VPN Server (OpenVPN)

#### Subnet de Dispositivos
- **CIDR**: `10.12.0.0/16`
- **Capacidade**: 65.534 hosts
- **Propósito**: Dispositivos IoT e endpoints de campo
- **Comunicação**: Acessa serviços na subnet de administração

---

## 4. Serviços de Infraestrutura

### 4.1 Bancos de Dados

| Serviço     | Tipo            | Acesso          | Propósito                      |
|-------------|-----------------|-----------------|--------------------------------|
| MySQL       | Relacional      | Interno (VPN)   | Dados transacionais            |
| TimescaleDB | Time-series     | Interno (VPN)   | Métricas e séries temporais    |
| Redis       | Key-Value/Cache | Interno (VPN)   | Cache e sessões                |

### 4.2 Message Broker

| Serviço   | Protocolo | Acesso          | Propósito                          |
|-----------|-----------|-----------------|-------------------------------------|
| RabbitMQ  | AMQP      | IP Público      | Mensageria entre serviços e devices |

**Endpoints**:
- Produção: `broker.timeenergy.com.br`
- Staging: `broker2.timeenergy.com.br`

### 4.3 Object Storage

| Serviço | Protocolo | Acesso     | Propósito                    |
|---------|-----------|------------|------------------------------|
| MinIO   | S3-compat | IP Público | Armazenamento de objetos     |

---

## 5. Cluster Kubernetes

### 5.1 Visão Geral

O Kubernetes é o orquestrador principal de containers, hospedando tanto aplicações próprias quanto ferramentas open source.

### 5.2 Componentes do Cluster

#### Ingress Controller
- **Função**: Roteamento de tráfego HTTP/HTTPS externo
- **Endpoints expostos**: Backend API (prod e beta)

#### GitOps e CI/CD
| Ferramenta | Propósito                                |
|------------|------------------------------------------|
| ArgoCD     | Continuous Deployment (GitOps)           |

#### Data Platform
| Ferramenta | Propósito                                |
|------------|------------------------------------------|
| Spark      | Processamento distribuído de dados       |
| Trino      | Query engine SQL federado                |
| Airbyte    | ETL e integração de dados                |

#### Backup e DR
| Ferramenta | Propósito                                |
|------------|------------------------------------------|
| Velero     | Backup de recursos e volumes K8s         |

#### Aplicações Próprias
- Serviços de backend
- APIs internas
- Workers e jobs

---

## 6. Acesso e Segurança

### 6.1 VPN (OpenVPN)

| Aspecto           | Configuração                              |
|-------------------|-------------------------------------------|
| Tipo              | OpenVPN                                   |
| Acesso            | Subnet de administração (10.11.144.0/24)  |
| Internet          | Permitido através do túnel                |
| Usuários          | Desenvolvedores e administradores         |

### 6.2 Pontos de Entrada Públicos

```
Internet ──► RabbitMQ     (broker.timeenergy.com.br, broker2.timeenergy.com.br)
         ──► MinIO        (endpoint a confirmar)
         ──► Backend API  (services.backend.timeenergy.com.br) via Ingress
         ──► Frontend     (neras.io) via AWS S3/CloudFront
```

---

## 7. Fluxos de Comunicação

### 7.1 Fluxo de Dados - Dispositivos IoT

```
[Dispositivos IoT] ──AMQP──► [RabbitMQ] ──► [Workers K8s] ──► [TimescaleDB]
     (10.12.x.x)               (público)        (interno)        (interno)
```

### 7.2 Fluxo de Dados - Usuários

```
[Usuário Web] ──HTTPS──► [Frontend S3] ──API──► [Backend K8s] ──► [MySQL/Redis]
                          (neras.io)            (services.backend)
```

### 7.3 Fluxo de Dados - Desenvolvedores

```
[Dev] ──VPN──► [OpenVPN] ──► [Subnet Admin] ──► [Todos os serviços]
                              (10.11.144.x)
```

---

## 8. Questões em Aberto

| Item | Descrição                                          | Status         |
|------|----------------------------------------------------|----------------|
| Q-01 | Qual é o 5º domínio/endpoint?                      | Aguardando     |
| Q-02 | MinIO tem domínio público ou apenas IP?            | Aguardando     |
| Q-03 | Existe replicação entre bancos de dados?           | Aguardando     |
| Q-04 | Qual a política de backup atual (RPO/RTO)?         | Aguardando     |
| Q-05 | Existem dependências externas além das listadas?   | Aguardando     |
| Q-06 | Qual o volume de dados em cada banco?              | Aguardando     |
| Q-07 | Quantos nodes no cluster Kubernetes?               | Aguardando     |

---

## 9. Próximos Passos

Este documento serve como base para:
1. **Especificação do DR** - Definir quais componentes precisam de réplica na AWS
2. **Plano de Implementação** - Mapear cada serviço para equivalente AWS
3. **Estratégia de Failover** - Definir RTO/RPO e procedimentos de switchover
