# BRAINSTORM: AWS Data Lakehouse (Personal Portfolio Project)

> Exploratory session to clarify intent and approach before requirements capture

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | aws-data-lakehouse |
| **Date** | 2026-04-20 |
| **Author** | brainstorm-agent |
| **Status** | Ready for Define |

---

## Initial Idea

**Raw Input:** Construct a data lakehouse on AWS using the existing `fake_data_generator` (energy-meter instantaneous measurements, 1 record/min/device). Flow: local producer → Firehose buffer → S3 landing → EMR/Spark/Glue ETL → Silver bucket (Iceberg + Glue Catalog) → Gold Athena views. Terraform for IaC. Personal project for AWS skill demonstration and GitHub portfolio. Hard budget ceiling **$10 USD total**. Must be fully destroyable on-demand.

**Context Gathered:**
- `fake_data_generator/` produces three record types via dataclasses: `InstantaneousData` (per-minute voltage/current/power/frequency/power-factor per phase), `SyncParametersData` (every 5 min), `DeviceData` (static metadata). All serializable to JSON via `to_dict()` / `to_json()`.
- Project is on feature branch `001-aws-data-lake`; `docs/SPEC_data_aws_architecture.md` exists but is empty (awaiting this brainstorm).
- CLAUDE.md active technologies: HCL (Terraform ≥ 1.0), Python 3.11, Terraform AWS Provider ≥ 5.0, AWS CLI ≥ 2.0.
- `docs/current-architecture.md` describes an existing private-cloud (CL9) stack with Kubernetes, Spark, Trino, TimescaleDB — valuable domain context but out of scope for this lakehouse project.

**Technical Context Observed (for Define):**

| Aspect | Observation | Implication |
|--------|-------------|-------------|
| Likely Location | `terraform/`, `glue_jobs/`, `producer/` at repo root | New top-level dirs alongside existing `fake_data_generator/` |
| Relevant KB Domains | lakehouse (Iceberg), pipeline (batch), AWS services | Consult for Iceberg partitioning, Glue Job patterns |
| IaC Patterns | No existing Terraform; greenfield | Establish module layout from scratch |
| Existing Code | `fake_data_generator` reusable as-is for the local producer | Producer imports it; no fork needed |

---

## Discovery Questions & Answers

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | ETL compute choice: EMR / EMR Serverless / Glue Jobs / EMR-on-EC2? | **(a) AWS Glue Jobs (PySpark)** | Zero idle cost; fits $10 budget; strong resume signal; serverless so no cluster lifecycle |
| 2 | Producer runtime: Lambda / ECS / EC2 / Local? | **(d) Local Python script** (outside AWS) | Mirrors real IoT (devices outside cloud); $0 producer cost; only needs IAM user with `firehose:PutRecordBatch` |
| 3 | Which Gold-layer business questions? | **(a) G1 hourly energy + G2 daily device summary + G3 fleet rollup** | Drives Silver partitioning (by `measured_date` + `device_id` bucket) and schema; complete energy-analytics story |
| 4 | Glue Job trigger / orchestration? | **(a) EventBridge schedule → Glue Job**, Athena views for Gold | Simplest, cheapest, zero idle cost; hourly confirmed then reduced to every-3h after budget math |
| 5 | Budget safety + GitHub presentation scope? | **(a) Full: Budgets + Glue guardrails + S3 lifecycle + portfolio repo with GH Actions** | Operational maturity visible in repo; budget-protected by design |

**Minimum Questions:** 5 asked (exceeds 3-minimum)

---

## Sample Data Inventory

> Samples improve LLM accuracy through in-context learning and few-shot prompting.

| Type | Location | Count | Notes |
|------|----------|-------|-------|
| Input files | `fake_data_generator/models.py` + `generators.py` | 3 dataclasses | Ground-truth schema: `InstantaneousData` (29 float cols + timestamp), `SyncParametersData`, `DeviceData` |
| Output examples | Generated at runtime via `to_json()` | Unbounded | JSON string per record — directly shippable to Firehose |
| Ground truth | `fake_data_generator/example.py` | Reference implementation | Shows orchestrator usage, streaming API, load profiles |
| Related code | `fake_data_generator/__init__.py` | 1 module | Public API exports (`FakeDataOrchestrator`, `DeviceConfig`, etc.) |

**How samples will be used:**

- **Silver Iceberg schema** derived directly from `InstantaneousData` dataclass fields (one-to-one mapping, with type refinement: `Optional[float]` → `DOUBLE`, `datetime` → `TIMESTAMP`)
- **Producer** imports `fake_data_generator` directly — no schema drift possible between generator and pipeline
- **Glue Job** unit tests can use `InstantaneousGenerator` to produce fixture data
- **Athena Gold views** grounded by known columns (`threephase_active_power`, `voltage_a`, `power_factor_a`, etc.)

---

## Approaches Explored

### Approach A: Serverless Glue + Iceberg + Athena ⭐ Recommended (SELECTED)

**Description:** Local Python producer → Firehose Direct PUT → S3 landing → EventBridge cron → AWS Glue Job (PySpark, Iceberg connector) writes Silver → Athena views read Silver for Gold. Entirely serverless; zero idle cost.

**Pros:**
- Every compute service is pay-per-use with $0 idle → safe for $10 budget
- `terraform destroy` removes every resource cleanly (nothing to "turn off")
- Modern stack: Iceberg + Glue Catalog + Athena is what senior DE roles ask about
- Small Terraform surface — fits one clean `terraform/modules/` layout
- No cluster operations / no cluster tuning / no cluster cost surprises

**Cons:**
- Glue cold starts (~30–60 s) — irrelevant at hourly cadence
- Iceberg-on-Glue has some quirks (Glue 4.0/5.0 bundled connector) — mitigated by pinning version
- 2-DPU minimum per Glue run = ~$0.08/run floor

**Why Recommended:** Only stack that simultaneously satisfies (a) $10 budget, (b) destroy-on-demand, (c) strong portfolio signal, (d) small enough to finish in a weekend.

---

### Approach B: EMR Serverless + Iceberg + Athena

**Description:** Same architecture but swap Glue Jobs for EMR Serverless.

**Pros:**
- Full Spark tuning (custom configs, Spark UI)
- Slightly cheaper per DPU-equivalent at scale
- Stronger "Spark expertise" signal

**Cons:**
- More Terraform surface (application + job run + execution role)
- Harder to demonstrate in a short README
- Minimal cost difference at this volume (both ≈$0.10/run)

**Why not recommended:** Added complexity for minimal budget or portfolio-signal gain at this scale.

---

### Approach C: EMR on EC2

**Description:** Classic EMR cluster running Spark with Iceberg, triggered manually or by scheduler.

**Pros:**
- "Classic big data" pattern
- Full control over cluster sizing

**Cons:**
- **Minimum ~$0.30/hr with master + core nodes running** — consumes $10 in ~33 hours
- Requires manual cluster stop/terminate discipline — one forgotten cluster = blown budget
- Heavier Terraform footprint (VPC, security groups, cluster config)
- Pattern is being displaced in industry — weaker forward-looking signal

**Why not recommended:** Budget risk and operational overhead outweigh educational value for a portfolio project.

---

## Data Engineering Context

### Source Systems

| Source | Type | Volume Estimate | Current Freshness |
|--------|------|-----------------|-------------------|
| Local `fake_data_generator` | Python process, local | ~1 record/min × N devices → ~1.4 MB/day per 10 devices (JSON) | Near-real-time (producer runs continuously while demoing) |

### Data Flow Sketch

```text
[local producer] ──PutRecordBatch──► [Firehose] ──buffer 128MB/300s──►
  [S3 landing (Bronze)] ──EventBridge cron(every 3h)──► [Glue Job PySpark]
    ──MERGE INTO──► [S3 Silver (Iceberg, Glue Catalog)]
      ──Athena views──► [Gold: G1 hourly_energy, G2 daily_device_summary, G3 fleet_daily_rollup]
```

### Key Data Questions Explored

| # | Question | Answer | Impact |
|---|----------|--------|--------|
| 1 | Expected data volume? | ~10 devices × 1440 records/day = 14.4k rows/day (~15 MB JSON) | Small — single-node Spark, 2 DPU cap is plenty |
| 2 | Freshness SLA? | "Demo-grade" — 3-hour batch is fine | Confirms EventBridge cron over streaming |
| 3 | Who consumes the output? | Analyst persona running Athena ad-hoc | Gold as views, not materialized tables; zero storage cost |
| 4 | Partition strategy for Silver? | `measured_date` (daily) + `bucket(device_id, 8)` | Prune on time, distribute on device for parallel writes |
| 5 | Idempotency? | Iceberg `MERGE INTO` on `(device_id, measured_at)` | Reprocessable if Glue job retries |
| 6 | Schema evolution? | Iceberg handles column adds; versioned by default | Future-proofs Silver against generator changes |

---

## Selected Approach

| Attribute | Value |
|-----------|-------|
| **Chosen** | Approach A — Serverless Glue + Iceberg + Athena |
| **User Confirmation** | 2026-04-20 (all 5 discovery questions + both validations answered affirmatively) |
| **Reasoning** | Only option that fits $10 budget with destroy-on-demand safety and strong portfolio signal. Validated architecture and repo layout accepted by user. |

---

## Key Decisions Made

| # | Decision | Rationale | Alternative Rejected |
|---|----------|-----------|----------------------|
| 1 | **AWS Glue Jobs (PySpark) for Bronze→Silver** | Zero idle cost; Iceberg connector included; Terraform-native | EMR (budget risk), EMR Serverless (extra complexity) |
| 2 | **Local producer using boto3 + `fake_data_generator`** | Mirrors real IoT edge devices; $0 cost; no AWS-side producer infra to destroy | Lambda/EventBridge (small but avoidable cost + infra surface), ECS (overkill), EC2 (manual stop risk) |
| 3 | **Firehose Direct PUT with 128 MB / 300 s buffer** | Documented — at low volume, time buffer (300 s) will usually trigger, which is the expected pattern | Kinesis Data Streams (added complexity without benefit at this volume) |
| 4 | **Silver = Iceberg on S3 + Glue Catalog** | ACID, schema evolution, time travel; canonical lakehouse format; queryable by Athena/Spark/Trino | Raw Parquet + Hive partitions (no ACID/evolution) |
| 5 | **Silver partition: `measured_date` + `bucket(device_id, 8)`** | Time pruning for date-filtered queries; device bucket for parallel writes | Partition by `device_id` directly (too many small partitions) |
| 6 | **Gold = Athena views (not materialized)** | $0 storage; query-on-demand; scan volume small enough that cost is negligible | CTAS materialized tables (extra storage, staleness management) |
| 7 | **EventBridge cron every 3 hours** | Fits $10 budget with 7-day running room; sufficient for demo cadence | Hourly (~$0.60/day — would blow budget over a week), S3-event-driven (noisy at 1-record-per-minute arrival) |
| 8 | **Glue job: `max_capacity = 2 DPU`, `timeout = 5 min`** | Hard cap on any single-run cost (~$0.073 worst case); prevents runaway jobs | Unlimited capacity/timeout (budget risk) |
| 9 | **AWS Budgets alerts at $5 / $8 / $10 via SNS email** | Defense-in-depth for budget; reactive safety net | No alerts (silent bill shock) |
| 10 | **S3 lifecycle: delete landing bucket objects > 7 days** | Bronze is reprocessable from producer; no need to retain raw beyond short window | Retain indefinitely (storage creep) |
| 11 | **`force_destroy = true` on all S3 buckets** | `terraform destroy` must work reliably without manual bucket emptying | Default (blocks destroy when objects exist) |
| 12 | **Local Terraform state backend** | Personal single-dev project; no team collaboration need | Remote S3+DynamoDB backend (over-engineered) |
| 13 | **Portfolio-grade GitHub repo with module structure + GH Actions (fmt/validate/plan)** | Demonstrates Terraform hygiene and CI awareness to reviewers | Monolithic single `main.tf` (weaker signal) |

---

## Features Removed (YAGNI)

| Feature Suggested | Reason Removed | Can Add Later? |
|-------------------|----------------|----------------|
| `SyncParametersData` Silver table | Not needed by G1/G2/G3; adds a 2nd pipeline path | **Yes** (Silver `sync_parameters` table + optional Gold view) |
| `DeviceData` dimension table | Gold views operate on `device_id` alone; no enrichment needed for MVP | **Yes** (SCD-1 dimension for device name/location/nominal_voltage) |
| EMR / EMR Serverless | Glue chosen (budget + simplicity) | **No** (by design) |
| Lambda / ECS / EC2 producer | Local producer selected | **Yes** (trivial swap — same boto3 logic in Lambda handler) |
| Kinesis Data Streams (instead of Firehose Direct PUT) | Firehose alone is enough at this volume | **Yes** (add upstream if multi-consumer fan-out is needed) |
| Step Functions orchestration | EventBridge cron is enough for single job | **Yes** (wrap Bronze→Silver→Gold refresh when adding more steps) |
| Data-quality framework (Glue Data Quality, Deequ, Great Expectations) | Over-scope for MVP; Iceberg schema is the contract | **Yes** (add Glue DQ ruleset as a post-load task) |
| Glue Crawler | Iceberg table DDL is declared in Terraform; no need to crawl | **Yes** (if you add non-Iceberg sources later) |
| `tfsec` / `checkov` / `infracost` | Slow first shipment; not MVP | **Yes** (add to GH Actions post-MVP) |
| Pre-commit hooks (`terraform fmt`, `tflint`) | Not MVP | **Yes** |
| Remote Terraform state (S3 + DynamoDB) | Personal single-dev project | **Yes** (when collaborating or adding environments) |
| Multi-environment (dev/stg/prod) | One `terraform apply`/`destroy` pair is enough | **Yes** (workspaces or folder-per-env) |
| CloudWatch dashboards | Budgets SNS alerts are sufficient for $10 project | **Yes** |
| Cost Anomaly Detection | Budgets + tight scope makes anomalies unlikely | **Yes** |
| VPC / private networking | Glue Job, Athena, Firehose, S3 all work via AWS-managed endpoints; no VPC needed | **Yes** (if producer ever moves inside AWS) |
| Slack / PagerDuty alerts | Email via SNS is enough | **Yes** |

---

## Incremental Validations

| Section | Presented | User Feedback | Adjusted? |
|---------|-----------|---------------|-----------|
| Architecture concept + data flow diagram + budget math | ✅ | Approved with Glue cadence reduced from hourly to every-3h to respect $10 ceiling | **Yes** — cadence lowered to `cron(0 */3 * * ? *)` |
| Repo layout + Terraform module structure + YAGNI cuts | ✅ | Approved as-is | No |

**Minimum Validations:** 2 completed (meets minimum)

---

## Suggested Requirements for /define

Based on this brainstorm session, the following should be captured in the DEFINE phase:

### Problem Statement (Draft)

> Build a personal-portfolio, fully destroyable, serverless data lakehouse on AWS that ingests simulated energy-meter telemetry from a local producer, lands it via Firehose in S3 Bronze, transforms it with an AWS Glue PySpark job into an Iceberg-backed Silver table, and exposes three business-question Gold views via Athena — all provisioned with Terraform, guarded by AWS Budgets, and kept under **$10 USD total cost**.

### Target Users (Draft)

| User | Pain Point |
|------|------------|
| **Bruno (author)** | Wants hands-on AWS data-lakehouse reps + a GitHub showcase without burning personal cash |
| **Portfolio reviewers (recruiters / interviewers)** | Need to quickly see the author's grasp of Iceberg, Glue, Athena, Firehose, IAM, Terraform modules — in one repo |
| **Future Bruno (forking the repo)** | Needs `terraform apply` → working lakehouse → `terraform destroy` → $0 resources left, repeatable |

### Success Criteria (Draft)

- [ ] `terraform apply` provisions the entire stack without errors
- [ ] Running `python producer/producer.py` puts records to Firehose; files appear in S3 landing within 5 min
- [ ] After first scheduled Glue run, Iceberg Silver table has rows matching producer output (row count within 1%)
- [ ] Athena query on `te_lake_gold.v_hourly_energy` returns at least one row per device-hour for periods covered by the producer
- [ ] Athena query on `te_lake_gold.v_daily_device_summary` returns min/avg/max voltage, peak power, total kWh, measurement count per device-day
- [ ] Athena query on `te_lake_gold.v_fleet_daily_rollup` returns a single row per day with fleet-total kWh
- [ ] `terraform destroy` completes cleanly with zero manual S3 emptying
- [ ] AWS Budgets alert at $5 threshold is configured and wired to an SNS email topic
- [ ] Total AWS spend for a 3–7 day demo window stays **under $10**
- [ ] GitHub repo renders with README + Mermaid architecture diagram + 3 sample Athena queries + GH Actions workflow that runs `terraform fmt -check && terraform validate && terraform plan` on PRs

### Constraints Identified

- **Hard budget:** $10 USD lifetime; favor $0-idle services
- **Destroy-on-demand:** every resource must be removable via `terraform destroy` (all S3 buckets `force_destroy = true`)
- **Single-dev personal project:** no remote state, no multi-env, no Slack/PagerDuty
- **Producer runs outside AWS:** only IAM user + `firehose:PutRecordBatch` needed inbound
- **Terraform AWS Provider ≥ 5.0** and **Terraform ≥ 1.0** (per CLAUDE.md)
- **Python 3.11** for producer + any Glue job scripts (Glue 4.0 / 5.0 runtime)
- **Region:** Default to **us-east-1** (cheapest, widest service availability); expose as Terraform variable
- **Security:** IAM least-privilege per role (producer, glue-job, athena-user); no wildcard resources in policies
- **Public GitHub repo:** no secrets, no account IDs, no real credentials; `.gitignore` must cover `*.tfstate*`, `.terraform/`, `*.tfvars` (except `.example`)

### Out of Scope (Confirmed)

- `SyncParametersData` and `DeviceData` Silver tables (deferred)
- EMR / EMR Serverless / self-hosted Spark
- Real-time / sub-minute freshness
- Data quality framework (Glue DQ, Deequ, Great Expectations)
- Glue Crawler / schema inference
- VPC / private networking
- `tfsec` / `checkov` / `infracost` / pre-commit hooks
- Remote Terraform state
- Multi-environment (dev/stg/prod) layouts
- CloudWatch dashboards beyond Glue + Firehose log groups
- Slack / PagerDuty / any non-email alert channel
- Any non-AWS cloud (strictly AWS-only)
- Cost Anomaly Detection
- Step Functions orchestration

---

## Session Summary

| Metric | Value |
|--------|-------|
| Questions Asked | 5 |
| Approaches Explored | 3 (Glue selected; EMR Serverless and EMR on EC2 rejected) |
| Features Removed (YAGNI) | 16 |
| Validations Completed | 2 |
| Duration | ~single session |

---

## Next Step

**Ready for:** `/define .claude/sdd/features/BRAINSTORM_aws-data-lakehouse.md`
