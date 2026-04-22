# DESIGN: AWS Data Lakehouse (Personal Portfolio Project)

> Technical design for a serverless, destroyable, sub-$10 AWS lakehouse: local producer → Firehose → S3 Bronze → Glue/PySpark → Iceberg Silver → Athena Gold, provisioned by Terraform.

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | aws-data-lakehouse |
| **Date** | 2026-04-20 |
| **Author** | design-agent |
| **DEFINE** | [DEFINE_aws-data-lakehouse.md](./DEFINE_aws-data-lakehouse.md) |
| **Status** | ✅ Shipped 2026-04-21 |
| **Region default** | `us-east-1` |
| **AWS Provider** | `hashicorp/aws ~> 5.80` |
| **Terraform** | `>= 1.6` |
| **Glue runtime** | `Glue 5.0` (Spark 3.5 + Python 3.11 + Iceberg 1.6 bundled) |

---

## Assumption Validation (from DEFINE)

| ID | Assumption | Verdict | Design Impact |
|----|------------|---------|---------------|
| A-001 | Glue 5.0 supports Iceberg 1.6 natively with Spark SQL `MERGE INTO` | ✅ Confirmed — Glue 5.0 ships Iceberg 1.6 as a bundled connector; activated via `--datalake-formats iceberg` job parameter and `spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog` configuration | No custom JARs; pass via `default_arguments` on the Glue job |
| A-002 | Firehose delivers to S3 with event-time-aware prefixes | ⚠ Adjusted — default prefix uses **delivery time**, not event time. True event-time partitioning needs **Dynamic Partitioning** (requires inline JSON parser + Parquet conversion OR Lambda transform) | **Decision: skip dynamic partitioning for MVP.** Use delivery-time prefix `year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/`. Glue job re-partitions Silver by `measured_date` derived from record `measured_at`. Bronze partition skew is acceptable — Glue reads full last-N-hours every run |
| A-003 | Athena engine v3 reads Glue-registered Iceberg tables | ✅ Confirmed — Athena v3 has native Iceberg support; Glue creates the table via `CREATE TABLE ... USING iceberg`, Athena sees it immediately | Views defined via Athena DDL work against the same table |
| A-006 | Personal AWS account has no SCPs blocking Glue/Firehose/Athena | ⚠ User must verify pre-apply | Documented in README "Prerequisites" |
| A-008 | `terraform destroy` on Glue database with Iceberg tables works without pre-delete | ⚠ Partially — `aws_glue_catalog_database` destroy succeeds only if tables are destroyed first; with Iceberg tables declared inline in Terraform, dependency order is correct. **But** tables created inside the Glue Job via `CREATE TABLE` (not Terraform-managed) must be dropped first | **Decision: create the Silver Iceberg table via Terraform `aws_glue_catalog_table` resource** (declarative) rather than inside the Glue job, so `terraform destroy` manages the full lifecycle. Gold views created via `null_resource` + `local-exec` with a matching destroy-time provisioner |

---

## Architecture Overview

```text
                                    ╔══════════════════════════════════╗
                                    ║    LOCAL DEVELOPER MACHINE       ║
                                    ║                                  ║
                                    ║  producer/producer.py            ║
                                    ║  ┌────────────────────────────┐  ║
                                    ║  │ fake_data_generator        │  ║
                                    ║  │ ↓ InstantaneousData.to_dict│  ║
                                    ║  │ boto3.client("firehose")   │  ║
                                    ║  │ put_record_batch (≤500/req)│  ║
                                    ║  └──────────────┬─────────────┘  ║
                                    ╚═════════════════│════════════════╝
                                                      │ HTTPS (IAM user creds in ~/.aws)
                                                      │ firehose:PutRecordBatch
                                    ══════════════════│═══════════════════════ AWS BOUNDARY
                                                      ▼
                                    ┌──────────────────────────────────┐
                                    │  Kinesis Data Firehose           │
                                    │  stream: te-lake-instant-stream  │
                                    │  - buffer: 128 MB OR 300 s       │
                                    │  - compression: GZIP             │
                                    │  - cloudwatch logs on failure    │
                                    └──────────────┬───────────────────┘
                                                   │ writes *.json.gz
                                                   ▼
                                    ┌──────────────────────────────────┐
                                    │  S3 Bucket — BRONZE (landing)    │
                                    │  s3://te-lake-landing-<uid>/     │
                                    │    instantaneous/                │
                                    │      year=.../month=.../day=.../ │
                                    │      hour=.../                   │
                                    │    errors/                       │
                                    │  lifecycle: delete > 7 days      │
                                    │  force_destroy: true             │
                                    └──────────────┬───────────────────┘
                                                   │
                      ┌────────────────────────────┘
                      │  cron(0 */3 * * ? *)   (EventBridge)
                      ▼
                 ┌──────────────────────────────────┐
                 │  AWS Glue Job (Glue 5.0, PySpark)│
                 │  te-lake-bronze-to-silver        │
                 │  - script_location: s3://…/      │
                 │    bronze_to_silver.py           │
                 │  - max_capacity: 2 DPU           │
                 │  - timeout: 5 min                │
                 │  - --datalake-formats iceberg    │
                 │  - args: --bronze_path,          │
                 │          --silver_table,         │
                 │          --watermark_hours=6     │
                 └──────────────┬───────────────────┘
                                │ spark.read("json.gz") →
                                │ filter null PKs →
                                │ cast types →
                                │ add _ingested_at →
                                │ MERGE INTO iceberg (device_id, measured_at)
                                ▼
                 ┌──────────────────────────────────┐
                 │  S3 Bucket — SILVER (Iceberg)    │
                 │  s3://te-lake-silver-<uid>/      │
                 │    instantaneous/                │
                 │      data/…  metadata/…          │
                 │  Glue Catalog DB: te_lake_silver │
                 │  Glue Catalog Table:             │
                 │    instantaneous_measurements    │
                 │    (TableType=ICEBERG)           │
                 │  Partitioned by:                 │
                 │    measured_date,                │
                 │    bucket(8, device_id)          │
                 └──────────────┬───────────────────┘
                                │ (no copy — views)
                                ▼
                 ┌──────────────────────────────────┐
                 │  Athena Workgroup                │
                 │  te-lake-analytics-wg            │
                 │  - engine v3                     │
                 │  - query results →               │
                 │    s3://te-lake-athena-<uid>/    │
                 │  - scan limit: 1 GB/query        │
                 │                                  │
                 │  Glue Catalog DB: te_lake_gold   │
                 │    v_hourly_energy         (G1)  │
                 │    v_daily_device_summary  (G2)  │
                 │    v_fleet_daily_rollup    (G3)  │
                 └──────────────────────────────────┘

  ╔═══════════════════ OBSERVABILITY / GUARDRAILS (cross-cutting) ════════════════════╗
  ║  AWS Budgets: te-lake-budget @ $5/$8/$10 → SNS topic → email subscription         ║
  ║  CloudWatch Log Groups: /aws-glue/jobs/output, /aws/kinesisfirehose/te-lake-stream║
  ║  IAM Roles: firehose-delivery, glue-job-execution                                 ║
  ║  IAM User:  te-lake-producer (programmatic-only, firehose:PutRecordBatch)         ║
  ╚═══════════════════════════════════════════════════════════════════════════════════╝
```

---

## Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Producer** | Local Python script simulating 10 IoT energy meters; batches records and PUTs to Firehose every 60 s | Python 3.11, `boto3`, reuses `fake_data_generator` |
| **Firehose Delivery Stream** | Managed buffer from producer → S3; GZIP compression; CW logs on failure | Kinesis Data Firehose, destination `extended_s3` |
| **S3 Bronze bucket** | Raw JSON-gzip landing zone with 7-day lifecycle; delivery-time partitioned | S3, lifecycle rule, `force_destroy=true` |
| **S3 Silver bucket** | Iceberg data + metadata files | S3, `force_destroy=true` |
| **S3 Athena results bucket** | Athena query results + CTAS staging (auto-cleaned) | S3, 3-day lifecycle, `force_destroy=true` |
| **Glue Catalog DB — silver** | Namespace for the single Iceberg Silver table | AWS Glue Data Catalog |
| **Glue Catalog Table — silver.instantaneous_measurements** | Declarative Iceberg table (schema + partition spec) | `aws_glue_catalog_table` with `TableType=ICEBERG` |
| **Glue Job — bronze_to_silver** | PySpark on Glue 5.0: reads Bronze, MERGEs into Iceberg | AWS Glue Job, Spark 3.5, Iceberg 1.6 |
| **EventBridge Rule** | Triggers Glue job every 3 h | `aws_cloudwatch_event_rule` + target |
| **Glue Catalog DB — gold** | Namespace for Athena views (G1 / G2 / G3) | AWS Glue Data Catalog |
| **Athena Workgroup** | Scoped workgroup with 1 GB/query scan limit for cost safety | `aws_athena_workgroup` |
| **Athena Views (3)** | G1 hourly energy, G2 daily device summary, G3 fleet rollup | Created by `null_resource` running `aws athena start-query-execution` |
| **Budgets + SNS** | Alerts at $5/$8/$10 to subscribed email | `aws_budgets_budget`, `aws_sns_topic`, `aws_sns_topic_subscription` |
| **IAM: producer user** | External programmatic-only user limited to `firehose:PutRecordBatch` on one stream | `aws_iam_user`, `aws_iam_user_policy`, `aws_iam_access_key` (output sensitively) |
| **IAM: firehose role** | Firehose-assumable role with S3 write + CW logs | `aws_iam_role`, two inline policies |
| **IAM: glue role** | Glue-assumable role with S3 read/write on Bronze+Silver, Glue Catalog r/w on both DBs, CW logs | `aws_iam_role`, inline + managed policies |
| **IAM: eventbridge role** | Invokes Glue job | `aws_iam_role`, inline policy |

---

## Key Decisions

### Decision 1: Glue 5.0 + Iceberg 1.6 bundled connector over custom JARs

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-20 |

**Context:** Glue jobs can run Iceberg via (a) Glue 5.0 bundled connector activated by a job parameter, or (b) Glue 4.0 + `--extra-jars` pointing to a custom Iceberg JAR on S3, or (c) Glue 5.0 `--additional-python-modules`.

**Choice:** Use **Glue 5.0** with `--datalake-formats iceberg` job parameter and Spark catalog configuration passed via `--conf` arguments.

**Rationale:** Zero JAR management; faster startup; one-line activation; Glue 5.0 is the current default and ships Spark 3.5 which has mature Iceberg DML (`MERGE INTO`, `DELETE FROM`, `UPDATE`).

**Alternatives Rejected:**
1. **Glue 4.0 + custom JAR** — requires hosting the JAR, keeping it in sync, extra IAM S3 permission; no upside
2. **EMR Serverless + Iceberg** — rejected in brainstorm for complexity/budget

**Consequences:**
- (+) Simplest Terraform (no `aws_s3_object` for JAR)
- (+) Python 3.11 matches producer version
- (−) Locked to Glue 5.0 feature parity (no concerns for this workload)

---

### Decision 2: Delivery-time partitioning in Firehose, event-time re-partitioning in Silver

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-20 |

**Context:** True event-time partitioning in Firehose requires Dynamic Partitioning with JSON parser + Parquet conversion, or a Lambda transformation. Both add cost and Terraform surface.

**Choice:** Firehose uses **delivery-time** prefix `instantaneous/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/`. The Glue job reads the **last 6 hours** of Bronze per run (watermark via S3 `LastModified`) and re-partitions by `measured_date` (derived from payload `measured_at`) when writing Silver.

**Rationale:** Firehose delivery time drifts from event time by only the buffer interval (≤300 s). A 6-hour read window at every-3-hour cadence gives a 3-hour overlap that absorbs out-of-order delivery and producer restarts. MERGE on `(device_id, measured_at)` is idempotent, so overlap is safe.

**Alternatives Rejected:**
1. **Dynamic Partitioning** — adds cost ($0.02/GB processed), requires inline JSON parser + format conversion, doubles Terraform config
2. **Lambda transformation to add `partitionKeys`** — small cost but extra moving part and IAM role
3. **Full Bronze scan every run** — wasteful after a few days of data; doesn't scale even for this demo

**Consequences:**
- (+) Zero Firehose add-ons; minimal Terraform
- (+) Absorbs producer/delivery clock drift naturally
- (−) Silver job scans up to 6 hours of Bronze each run (still <10 MB — trivial)
- (−) Possible drift between Bronze partition folder and event date near midnight (cosmetic — Silver is the source of truth for `measured_date`)

---

### Decision 3: Declarative Iceberg table via `aws_glue_catalog_table` (not DDL-in-job)

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-20 |

**Context:** Iceberg tables can be created (a) by Spark SQL `CREATE TABLE` inside the Glue job on first run, (b) by `aws_glue_catalog_table` with `TableType = "EXTERNAL_TABLE"` + Iceberg parameters, or (c) by `aws athena start-query-execution` via `null_resource`.

**Choice:** Declare the Silver table via **`aws_glue_catalog_table`** with:
```hcl
table_type = "EXTERNAL_TABLE"
parameters = {
  "table_type"        = "ICEBERG"
  "metadata_location" = "<written by glue job on first run>"
}
storage_descriptor { ... columns ... }
```
The Glue job's first run calls `CREATE TABLE IF NOT EXISTS` to write Iceberg metadata to S3 (no-op if already exists). Terraform owns the catalog entry; Glue owns the data files. `terraform destroy` removes the catalog registration; `force_destroy` on Silver bucket removes the files.

**Rationale:** Single source of truth for schema is Terraform (visible in git blame). Destroy order is clean: EventBridge → Glue Job → Glue Table → Glue DB → S3 bucket (empties on destroy). No imperative `null_resource` for the main fact table.

**Alternatives Rejected:**
1. **Spark-only `CREATE TABLE`** — schema hidden inside Python file; `terraform destroy` fails when Glue table exists but has no Terraform record
2. **All via `null_resource`** — imperative, harder to review, breaks `terraform plan` diffs

**Consequences:**
- (+) Schema changes reviewed in Terraform PRs
- (+) Clean destroy order
- (−) Glue job must handle the "table metadata not initialized yet" case gracefully on first run (uses `CREATE TABLE IF NOT EXISTS` before `MERGE INTO`)

---

### Decision 4: Gold views via `null_resource` + Athena DDL (not Glue view tables)

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-20 |

**Context:** Athena views can be declared as (a) special Glue `TableType = "VIRTUAL_VIEW"` tables (brittle — requires base64-encoded `presto-view` JSON and exact encoding), (b) Athena-native DDL via `CREATE OR REPLACE VIEW`, stored in Glue Catalog automatically, or (c) Athena `aws_athena_named_query` "saved queries" (users must manually run to create view).

**Choice:** Use a **`null_resource`** per view with `local-exec` provisioner running `aws athena start-query-execution`, plus a destroy-time provisioner running `DROP VIEW IF EXISTS`. View SQL lives in `terraform/modules/query/views/*.sql` (versioned), interpolated with database names.

**Rationale:** Truly one-command `terraform apply` while keeping view SQL readable. The DDL `CREATE OR REPLACE VIEW` + `DROP VIEW` pair is idempotent and survives re-applies.

**Alternatives Rejected:**
1. **Glue `VIRTUAL_VIEW`** — encoding traps; AWS rarely uses it outside Athena's own console; future maintenance burden
2. **`aws_athena_named_query`** — doesn't create the view, just stores the SQL; breaks "one-command apply"
3. **Put view DDL in Glue job script** — views aren't a Spark thing; wrong tool

**Consequences:**
- (+) One-command lifecycle
- (+) View SQL is first-class, diff-able, reviewable
- (−) Requires AWS CLI installed on `terraform apply` machine (acceptable — we use it anyway for producer)
- (−) `null_resource` doesn't show nice diff in `plan` (acceptable — views are small, re-apply is safe)

---

### Decision 5: Single Athena workgroup with 1 GB scan cap

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-20 |

**Context:** Athena charges $5/TB scanned. A forgotten `SELECT *` over a large table could blow the budget. Workgroup `bytes_scanned_cutoff_per_query` provides a hard cap.

**Choice:** Workgroup `te-lake-analytics-wg` with `bytes_scanned_cutoff_per_query = 1_073_741_824` (1 GB) and `enforce_workgroup_configuration = true`. All view DDL and sample queries use this workgroup.

**Rationale:** 1 GB scan = $0.005 per query maximum; this dataset will never produce more than a few MB/query. The cutoff is a safety net, not a functional limit.

**Alternatives Rejected:**
1. **No cutoff** — budget risk
2. **Primary workgroup modification** — polluting the default workgroup in a personal account is bad hygiene
3. **Data usage controls (per-query)** — more Terraform; 1 GB cutoff is sufficient

**Consequences:**
- (+) Hard protection against runaway queries
- (−) Must remember to select `te-lake-analytics-wg` when running queries in console

---

### Decision 6: Silver partition spec — `measured_date` + `bucket(8, device_id)`

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-20 |

**Context:** Iceberg supports partition transforms (`days`, `bucket`, `truncate`). Poor partitioning causes small-file problems or full-scan queries. Queries are time-bounded and per-device-or-fleet.

**Choice:** `PARTITIONED BY (measured_date, bucket(8, device_id))`. `measured_date` is a derived `DATE` column (`CAST(measured_at AS DATE)`) stored explicitly; `bucket(8, device_id)` distributes devices across 8 buckets for parallel writes without creating thousands of per-device partitions.

**Rationale:**
- **Time pruning:** every Gold query filters by date — `measured_date` partition prunes immediately
- **Device distribution:** at 10 devices × 1440 rows/day = 14.4k rows/day; without bucketing, writes contend on one file. 8 buckets = 8 parallel writers
- **Bucket count 8:** rule of thumb is `ceil(devices / 10)` bumped to power of 2 for hash quality; 8 fits 10–80 devices well

**Alternatives Rejected:**
1. **Partition by `device_id`** directly — creates 10+ partitions/day; as device count grows produces the classic small-file problem
2. **Partition only by `measured_date`** — fine for this volume but doesn't scale; less "senior signal" for portfolio
3. **`hours(measured_at)` transform** — over-partitioned for daily Gold queries

**Consequences:**
- (+) Queries `WHERE measured_date = ...` scan only that day's files
- (+) Writes parallelize across buckets
- (−) Per-device queries still scan all 8 buckets (negligible at this size)

---

### Decision 7: Local Terraform state

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-20 |

**Context:** Remote state (S3 + DynamoDB lock) adds bootstrap complexity and its own non-destroyable resources.

**Choice:** Default to **local state** (`terraform.tfstate` in `terraform/`). `.gitignore` covers `*.tfstate*`, `.terraform/`. Document in README that state is local and collaborators should not share the state file.

**Rationale:** Single-dev personal project. The `terraform init` → `apply` → `destroy` cycle is straightforward. Remote state would contradict the "fully destroyable" goal (you'd leave an S3 state bucket behind).

**Alternatives Rejected:**
1. **S3 + DynamoDB backend** — adds 2 orphan resources; contradicts full-teardown goal
2. **Terraform Cloud** — external dependency, credentials, account signup

**Consequences:**
- (+) Pure local lifecycle; nothing survives `terraform destroy`
- (−) Not collaboration-ready (acceptable per DEFINE constraints)

---

### Decision 8: IAM user for producer with access keys (no STS)

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-20 |

**Context:** Producer runs locally outside AWS. Options: (a) IAM user with static access keys, (b) IAM role assumed via STS with external MFA, (c) IAM Identity Center SSO.

**Choice:** **IAM user `te-lake-producer`** with programmatic access key, scoped only to `firehose:PutRecordBatch` and `firehose:DescribeDeliveryStream` on one stream ARN. Access key is a Terraform resource output as `sensitive`; user exports it to `~/.aws/credentials` under a dedicated profile `[te-lake-producer]`.

**Rationale:** Simplest path that still demonstrates IAM least-privilege. The user exists only while the stack is applied; `terraform destroy` rotates it away. Scope is tight: one action, one resource.

**Alternatives Rejected:**
1. **STS AssumeRole** — requires the producer to have *another* set of credentials to assume from; doesn't save anything locally
2. **IAM Identity Center / SSO** — overkill for a personal project; requires org setup
3. **Long-lived access key in ENV var** (not via Terraform) — loses the "everything in IaC" story

**Consequences:**
- (+) Secret key is auto-generated and auto-rotated on `destroy`/`apply`
- (+) One-liner `aws configure --profile te-lake-producer` setup
- (−) Static credentials exist on the developer machine — acceptable for personal account with tight scope; documented in README

---

### Decision 9: Firehose buffer 128 MB / 300 s, GZIP compression

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-20 |

**Context:** Firehose uses whichever buffer fires first (size or time). At 10 devices × 1/min × ~1 KB = ~600 KB/hour, size buffer never fires — time buffer always does, every 300 s.

**Choice:** Keep size buffer = 128 MB (aspirational per original user spec), interval = 300 s (maximum allowed), GZIP compression.

**Rationale:**
- **Time = 300 s:** matches producer cadence; records reach S3 within 5 min, meeting AT-002
- **Size = 128 MB:** user's original preference; documented as "will not fire at this volume"
- **GZIP:** ~80% reduction on JSON; ~$0.007 vs $0.03 S3 storage per GB-month

**Alternatives Rejected:**
1. **Interval = 60 s** — 5× more files → 5× more S3 PUTs → tiny cost bump, noisier Bronze
2. **Snappy compression** — better for Spark reads but not natively supported by Firehose; GZIP reads fine in Spark
3. **Format conversion to Parquet** — needs a Glue table schema upfront and adds cost; Glue job reads JSON-gz perfectly well

**Consequences:**
- (+) Simple config; Spark handles `*.json.gz` natively
- (+) Compression saves real money even at low volume
- (−) Slightly more CPU on Glue reader (trivial)

---

### Decision 10: Runtime-agnostic Terraform module boundaries

| Attribute | Value |
|-----------|-------|
| **Status** | Accepted |
| **Date** | 2026-04-20 |

**Context:** Module boundaries affect reusability and destroy order. Too fine = many cross-module references; too coarse = monolith.

**Choice:** Six modules (`storage`, `ingestion`, `catalog`, `etl`, `query`, `observability`) each owning a *capability*, not a *service*. Example: `etl` owns the Glue job IAM role, the Glue job resource, the EventBridge rule, and the script upload — everything needed to "run the ETL job" — not just the Glue resource.

**Rationale:** Capability boundaries match how the system is reasoned about ("the ETL runs, the catalog stores metadata, the query layer exposes data"). Cross-module references are few: bucket ARNs (storage → ingestion/etl/query), database names (catalog → etl/query).

**Alternatives Rejected:**
1. **Single root module** — no reuse story, poor portfolio signal
2. **Per-AWS-service module** (`s3/`, `glue/`, `iam/`, `athena/`) — fragments IAM across all modules; hard to reason about
3. **Layer-per-medallion** (`bronze/`, `silver/`, `gold/`) — splits IAM oddly (Glue role spans all layers)

**Consequences:**
- (+) Clean ownership; IAM lives next to the consumer of the privilege
- (+) Easy to delete one capability (e.g., swap Athena for Trino in the `query` module)
- (−) `storage` module is infrastructure-only, feels less "full" — accepted

---

## File Manifest

**Total files:** 34 (28 new, 0 modified; `fake_data_generator/` unchanged)

| # | File | Action | Purpose | Agent | Dependencies |
|---|------|--------|---------|-------|--------------|
| **ROOT** | | | | | |
| 1 | `README.md` | Create | Overview + Mermaid diagram + how-to-run + how-to-destroy | code-documenter | 30, 31, 32 |
| 2 | `.gitignore` | Create | Ignore `*.tfstate*`, `.terraform/`, `*.tfvars`, `__pycache__/`, `.venv/`, `.idea/` | general | None |
| 3 | `LICENSE` | Create | MIT (portfolio-friendly) | general | None |
| **TERRAFORM — ROOT** | | | | | |
| 4 | `terraform/providers.tf` | Create | AWS provider ~>5.80, region var, default_tags | aws-data-architect | None |
| 5 | `terraform/backend.tf` | Create | Local backend declaration (documenting intent) | aws-data-architect | None |
| 6 | `terraform/variables.tf` | Create | `project_name`, `region`, `budget_limit_usd`, `alert_email`, `glue_cadence_cron`, `firehose_buffer_seconds`, `firehose_buffer_size_mb`, `athena_bytes_scanned_cutoff`, `producer_device_count` | aws-data-architect | None |
| 7 | `terraform/locals.tf` | Create | Computed values: `name_prefix = "${var.project_name}-${random_id.suffix.hex}"`; bucket names | aws-data-architect | 6 |
| 8 | `terraform/main.tf` | Create | Wires all 6 modules with outputs → inputs | aws-data-architect | 9–29 |
| 9 | `terraform/outputs.tf` | Create | `firehose_stream_name`, `landing_bucket`, `silver_bucket`, `athena_workgroup`, `athena_results_bucket`, `producer_access_key_id` (sensitive), `producer_secret_access_key` (sensitive) | aws-data-architect | 8 |
| 10 | `terraform/terraform.tfvars.example` | Create | Example var values (no secrets) | aws-data-architect | 6 |
| **TERRAFORM — MODULE: storage** | | | | | |
| 11 | `terraform/modules/storage/main.tf` | Create | 3 S3 buckets (landing, silver, athena-results) + versioning (disabled — cheap) + SSE-S3 + lifecycle rules | aws-data-architect | None |
| 12 | `terraform/modules/storage/variables.tf` | Create | `name_prefix`, `bronze_retention_days=7`, `athena_results_retention_days=3` | aws-data-architect | None |
| 13 | `terraform/modules/storage/outputs.tf` | Create | Bucket names + ARNs | aws-data-architect | 11 |
| **TERRAFORM — MODULE: ingestion** | | | | | |
| 14 | `terraform/modules/ingestion/main.tf` | Create | Firehose delivery stream (extended_s3), Firehose IAM role + policy, CloudWatch log group, producer IAM user + policy + access key | aws-data-architect | None |
| 15 | `terraform/modules/ingestion/variables.tf` | Create | `name_prefix`, `landing_bucket_arn`, `buffer_size_mb`, `buffer_interval_seconds` | aws-data-architect | None |
| 16 | `terraform/modules/ingestion/outputs.tf` | Create | `firehose_stream_name`, `firehose_stream_arn`, `producer_access_key_id` (sensitive), `producer_secret_access_key` (sensitive) | aws-data-architect | 14 |
| **TERRAFORM — MODULE: catalog** | | | | | |
| 17 | `terraform/modules/catalog/main.tf` | Create | 2 Glue databases (`te_lake_silver`, `te_lake_gold`), 1 Glue Iceberg table `instantaneous_measurements` | aws-data-architect | None |
| 18 | `terraform/modules/catalog/variables.tf` | Create | `name_prefix`, `silver_table_location` (s3 URI) | aws-data-architect | None |
| 19 | `terraform/modules/catalog/outputs.tf` | Create | `silver_db_name`, `gold_db_name`, `silver_table_name` | aws-data-architect | 17 |
| **TERRAFORM — MODULE: etl** | | | | | |
| 20 | `terraform/modules/etl/main.tf` | Create | Glue job (5.0, PySpark, 2 DPU, 5 min timeout, `--datalake-formats iceberg`, spark.sql catalog confs), Glue IAM role + policy, script upload to `landing_bucket/scripts/`, EventBridge rule + target + role | aws-data-architect + spark-engineer | None |
| 21 | `terraform/modules/etl/variables.tf` | Create | `name_prefix`, `landing_bucket_name`, `landing_bucket_arn`, `silver_bucket_name`, `silver_bucket_arn`, `silver_db_name`, `silver_table_name`, `glue_cadence_cron`, `watermark_hours=6` | aws-data-architect | None |
| 22 | `terraform/modules/etl/outputs.tf` | Create | `glue_job_name`, `glue_role_arn` | aws-data-architect | 20 |
| 23 | `terraform/modules/etl/scripts/bronze_to_silver.py` | Create | PySpark job — reads JSON-gz from Bronze, filters invalid rows, casts, MERGE INTO Silver Iceberg | spark-engineer | None |
| **TERRAFORM — MODULE: query** | | | | | |
| 24 | `terraform/modules/query/main.tf` | Create | Athena workgroup + 3 `null_resource` for views with `local-exec` create + destroy | aws-data-architect | None |
| 25 | `terraform/modules/query/variables.tf` | Create | `name_prefix`, `athena_results_bucket_name`, `silver_db_name`, `silver_table_name`, `gold_db_name`, `bytes_scanned_cutoff`, `region` | aws-data-architect | None |
| 26 | `terraform/modules/query/outputs.tf` | Create | `workgroup_name`, `view_names` (list) | aws-data-architect | 24 |
| 27 | `terraform/modules/query/views/v_hourly_energy.sql.tftpl` | Create | G1 DDL template | sql-optimizer | None |
| 28 | `terraform/modules/query/views/v_daily_device_summary.sql.tftpl` | Create | G2 DDL template | sql-optimizer | None |
| 29 | `terraform/modules/query/views/v_fleet_daily_rollup.sql.tftpl` | Create | G3 DDL template | sql-optimizer | 27, 28 |
| **TERRAFORM — MODULE: observability** | | | | | |
| 30 | `terraform/modules/observability/main.tf` | Create | `aws_budgets_budget` with 3 notification thresholds, `aws_sns_topic`, `aws_sns_topic_subscription` (email) | aws-data-architect | None |
| **PRODUCER** | | | | | |
| 31 | `producer/producer.py` | Create | CLI: `--devices`, `--duration-min`, `--stream-name`, `--region`, `--profile`; loops, batches ≤500 records, handles throttling | python-developer | None |
| 32 | `producer/requirements.txt` | Create | `boto3>=1.34`, path install of `fake_data_generator` via `-e ..` | python-developer | None |
| 33 | `producer/README.md` | Create | How to run locally, how to set AWS profile | code-documenter | 31 |
| **CI** | | | | | |
| 34 | `.github/workflows/terraform-ci.yml` | Create | On PR: checkout, setup-terraform, `fmt -check`, `init -backend=false`, `validate`, `plan -refresh=false -lock=false` (skip if creds absent) | ci-cd-specialist | 8 |
| **DOCS** | | | | | |
| 35 | `docs/architecture.md` | Create | Mermaid deep-dive diagram, cost breakdown table, sequence diagrams | code-documenter | 1 |
| 36 | `docs/athena-queries.sql` | Create | 3 sample queries (one per Gold view), plus "show current Iceberg snapshots" query | sql-optimizer | 27, 28, 29 |

**Note:** `fake_data_generator/` is left untouched and imported by `producer/producer.py` via `sys.path` manipulation or a `-e ..` editable install.

---

## Agent Assignment Rationale

| Agent | Files Assigned | Why This Agent |
|-------|----------------|----------------|
| **@aws-data-architect** | 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 24, 25, 26, 30 | Owns AWS service wiring (S3, Firehose, Glue, Athena, Budgets, IAM). Primary driver of IaC design |
| **@spark-engineer** | 20 (reviews), 23 | PySpark + Iceberg MERGE INTO patterns, Glue-specific configuration (catalog conf, checkpointing) |
| **@sql-optimizer** | 27, 28, 29, 36 | Athena/Presto/Trino SQL idioms, time-aggregation patterns, window functions, cost-conscious view design |
| **@python-developer** | 31, 32 | Clean Python CLI with dataclasses, type hints, generator-friendly batch logic |
| **@ci-cd-specialist** | 34 | GitHub Actions Terraform workflow patterns, PR validation, least-privilege CI credentials |
| **@code-documenter** | 1, 33, 35 | README structure, Mermaid diagrams, how-to-run sections, portfolio polish |
| **(general)** | 2, 3 | `.gitignore` and `LICENSE` are boilerplate |

**Agent Discovery:**
- Scanned `.claude/agents/cloud/aws-data-architect.md`, `.claude/agents/data-engineering/spark-engineer.md`, `.claude/agents/data-engineering/sql-optimizer.md`, `.claude/agents/python/python-developer.md`, `.claude/agents/cloud/ci-cd-specialist.md`, `.claude/agents/dev/code-documenter.md`
- Primary IaC driver is `aws-data-architect`; Spark job script is owned by `spark-engineer` for Iceberg-specific patterns; SQL DDL owned by `sql-optimizer`

---

## Code Patterns

### Pattern 1: Firehose delivery stream (Terraform)

```hcl
# terraform/modules/ingestion/main.tf (excerpt)

resource "aws_kinesis_firehose_delivery_stream" "instant" {
  name        = "${var.name_prefix}-instant-stream"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose.arn
    bucket_arn          = var.landing_bucket_arn
    prefix              = "instantaneous/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"
    error_output_prefix = "errors/!{firehose:error-output-type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    compression_format  = "GZIP"

    buffering_size     = var.buffer_size_mb     # 128
    buffering_interval = var.buffer_interval_seconds  # 300

    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = aws_cloudwatch_log_group.firehose.name
      log_stream_name = "S3Delivery"
    }
  }
}

resource "aws_cloudwatch_log_group" "firehose" {
  name              = "/aws/kinesisfirehose/${var.name_prefix}-instant-stream"
  retention_in_days = 7
}
```

### Pattern 2: Iceberg table declaration (Terraform)

```hcl
# terraform/modules/catalog/main.tf (excerpt)

resource "aws_glue_catalog_database" "silver" {
  name = "te_lake_silver"
}

resource "aws_glue_catalog_table" "instantaneous" {
  name          = "instantaneous_measurements"
  database_name = aws_glue_catalog_database.silver.name
  table_type    = "EXTERNAL_TABLE"

  parameters = {
    "table_type"    = "ICEBERG"
    "classification" = "parquet"
  }

  open_table_format_input {
    iceberg_input {
      metadata_operation = "CREATE"
      version            = "2"
    }
  }

  storage_descriptor {
    location = var.silver_table_location  # s3://te-lake-silver-<uid>/instantaneous/

    # Column list matches InstantaneousData dataclass
    dynamic "columns" {
      for_each = local.silver_columns
      content {
        name = columns.value.name
        type = columns.value.type
      }
    }
  }
}

# locals.tf excerpt: authoritative column list (matches fake_data_generator/models.py)
locals {
  silver_columns = [
    { name = "device_id",                 type = "bigint"    },
    { name = "measured_at",               type = "timestamp" },
    { name = "mac_address",               type = "string"    },
    { name = "voltage_a",                 type = "double"    },
    # ... (all 29 measurement columns + derived columns)
    { name = "measured_date",             type = "date"      },
    { name = "_ingested_at",              type = "timestamp" },
  ]
}
```

### Pattern 3: Glue PySpark job with Iceberg MERGE INTO

```python
# terraform/modules/etl/scripts/bronze_to_silver.py

import sys
from datetime import datetime, timedelta, timezone

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql import functions as F
from pyspark.sql.types import (
    DoubleType, IntegerType, LongType, StringType,
    StructField, StructType, TimestampType,
)


def build_schema() -> StructType:
    """Authoritative schema for InstantaneousData JSON from producer."""
    return StructType([
        StructField("device_id", LongType(), nullable=False),
        StructField("measured_at", StringType(), nullable=False),  # ISO string → cast later
        StructField("mac_address", StringType()),
        StructField("voltage_a", DoubleType()), StructField("voltage_b", DoubleType()), StructField("voltage_c", DoubleType()),
        StructField("voltage_ab", DoubleType()), StructField("voltage_bc", DoubleType()), StructField("voltage_ca", DoubleType()),
        StructField("current_a", DoubleType()), StructField("current_b", DoubleType()), StructField("current_c", DoubleType()),
        StructField("active_power_a", DoubleType()), StructField("active_power_b", DoubleType()), StructField("active_power_c", DoubleType()),
        StructField("threephase_active_power", DoubleType()),
        StructField("reactive_power_a", DoubleType()), StructField("reactive_power_b", DoubleType()), StructField("reactive_power_c", DoubleType()),
        StructField("threephase_reactive_power", DoubleType()),
        StructField("apparent_power_a", DoubleType()), StructField("apparent_power_b", DoubleType()), StructField("apparent_power_c", DoubleType()),
        StructField("threephase_apparent_power", DoubleType()),
        StructField("frequency_a", DoubleType()), StructField("frequency_b", DoubleType()), StructField("frequency_c", DoubleType()),
        StructField("power_factor_a", DoubleType()), StructField("power_factor_b", DoubleType()), StructField("power_factor_c", DoubleType()),
        StructField("temperature", DoubleType()),
        StructField("angle_a", DoubleType()), StructField("angle_b", DoubleType()), StructField("angle_c", DoubleType()),
        StructField("neutral_current", DoubleType()),
        StructField("timezone", IntegerType()),
        StructField("daylight_saving_time", IntegerType()),
    ])


def read_bronze(glue_context, bronze_path: str, watermark_hours: int):
    """Read only the last N hours of Bronze to keep runs cheap and idempotent."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=watermark_hours)
    # Broad partition prune via path globbing — delivery-time partitioning
    # Read full day ranges that overlap the watermark window (simpler than per-hour globs)
    paths = [
        f"{bronze_path.rstrip('/')}/year={(cutoff + timedelta(hours=h)).strftime('%Y')}"
        f"/month={(cutoff + timedelta(hours=h)).strftime('%m')}"
        f"/day={(cutoff + timedelta(hours=h)).strftime('%d')}"
        f"/hour={(cutoff + timedelta(hours=h)).strftime('%H')}/"
        for h in range(watermark_hours + 2)
    ]
    return (
        glue_context.spark_session.read
        .schema(build_schema())
        .json(paths, mode="PERMISSIVE")
    )


def transform(df):
    return (
        df
        .filter(F.col("device_id").isNotNull() & F.col("measured_at").isNotNull())
        .withColumn("measured_at", F.to_timestamp("measured_at"))
        .withColumn("measured_date", F.to_date("measured_at"))
        .withColumn("_ingested_at", F.current_timestamp())
        .dropDuplicates(["device_id", "measured_at"])
    )


def merge_into_silver(spark, source_df, full_table_name: str):
    """Idempotent MERGE INTO on (device_id, measured_at)."""
    source_df.createOrReplaceTempView("bronze_batch")
    spark.sql(f"""
        MERGE INTO {full_table_name} t
        USING bronze_batch s
        ON t.device_id = s.device_id AND t.measured_at = s.measured_at
        WHEN NOT MATCHED THEN INSERT *
    """)


def main():
    args = getResolvedOptions(sys.argv, [
        "JOB_NAME", "bronze_path", "silver_table", "watermark_hours",
    ])

    sc = SparkContext()
    glue_context = GlueContext(sc)
    spark = glue_context.spark_session
    job = Job(glue_context)
    job.init(args["JOB_NAME"], args)

    bronze_df = read_bronze(glue_context, args["bronze_path"], int(args["watermark_hours"]))
    if bronze_df.rdd.isEmpty():
        glue_context.get_logger().warn("No Bronze records in watermark window; exiting cleanly.")
        job.commit()
        return

    silver_df = transform(bronze_df)
    merge_into_silver(spark, silver_df, args["silver_table"])  # e.g. glue_catalog.te_lake_silver.instantaneous_measurements

    job.commit()


if __name__ == "__main__":
    main()
```

**Glue job parameters (set in Terraform):**
```hcl
default_arguments = {
  "--job-language"              = "python"
  "--datalake-formats"          = "iceberg"
  "--conf"                      = join(" --conf ", [
    "spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog",
    "spark.sql.catalog.glue_catalog.warehouse=${var.silver_bucket_s3_uri}",
    "spark.sql.catalog.glue_catalog.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog",
    "spark.sql.catalog.glue_catalog.io-impl=org.apache.iceberg.aws.s3.S3FileIO",
    "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
  ])
  "--bronze_path"               = "s3://${var.landing_bucket_name}/instantaneous/"
  "--silver_table"              = "glue_catalog.${var.silver_db_name}.${var.silver_table_name}"
  "--watermark_hours"           = tostring(var.watermark_hours)
  "--enable-metrics"            = "true"
  "--enable-continuous-cloudwatch-log" = "true"
  "--TempDir"                   = "s3://${var.landing_bucket_name}/tmp/"
}
```

### Pattern 4: Athena view via `null_resource`

```hcl
# terraform/modules/query/main.tf (excerpt)

locals {
  views = {
    v_hourly_energy         = templatefile("${path.module}/views/v_hourly_energy.sql.tftpl",         { silver_db = var.silver_db_name, silver_table = var.silver_table_name, gold_db = var.gold_db_name })
    v_daily_device_summary  = templatefile("${path.module}/views/v_daily_device_summary.sql.tftpl",  { silver_db = var.silver_db_name, silver_table = var.silver_table_name, gold_db = var.gold_db_name })
    v_fleet_daily_rollup    = templatefile("${path.module}/views/v_fleet_daily_rollup.sql.tftpl",    { gold_db = var.gold_db_name })
  }
}

resource "null_resource" "gold_view" {
  for_each = local.views

  triggers = {
    ddl = each.value
    wg  = aws_athena_workgroup.analytics.name
  }

  provisioner "local-exec" {
    command     = <<-EOT
      aws athena start-query-execution \
        --region ${var.region} \
        --work-group ${aws_athena_workgroup.analytics.name} \
        --query-string "${replace(each.value, "\"", "\\\"")}"
    EOT
    interpreter = ["bash", "-c"]
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      aws athena start-query-execution \
        --region ${self.triggers.region} \
        --work-group ${self.triggers.wg} \
        --query-string "DROP VIEW IF EXISTS ${self.triggers.gold_db}.${each.key}"
    EOT
    interpreter = ["bash", "-c"]
  }
}
```

### Pattern 5: Gold view DDL — G1 hourly energy

```sql
-- terraform/modules/query/views/v_hourly_energy.sql.tftpl

CREATE OR REPLACE VIEW ${gold_db}.v_hourly_energy AS
SELECT
    device_id,
    measured_date,
    HOUR(measured_at)                              AS hour_of_day,
    AVG(threephase_active_power)                   AS avg_active_power_w,
    AVG(threephase_active_power) / 1000.0          AS kwh,  -- avg W × 1 h / 1000
    COUNT(*)                                       AS sample_count
FROM ${silver_db}.${silver_table}
WHERE threephase_active_power IS NOT NULL
GROUP BY device_id, measured_date, HOUR(measured_at);
```

### Pattern 6: Gold view DDL — G2 daily device summary

```sql
-- terraform/modules/query/views/v_daily_device_summary.sql.tftpl

CREATE OR REPLACE VIEW ${gold_db}.v_daily_device_summary AS
SELECT
    device_id,
    measured_date,
    MIN(voltage_a)                        AS min_voltage,
    AVG(voltage_a)                        AS avg_voltage,
    MAX(voltage_a)                        AS max_voltage,
    MAX(threephase_active_power)          AS peak_power_w,
    SUM(threephase_active_power) / 60000.0 AS total_kwh,  -- minute samples → hours
    COUNT(*)                              AS measurement_count,
    AVG(power_factor_a)                   AS avg_power_factor
FROM ${silver_db}.${silver_table}
WHERE voltage_a IS NOT NULL
  AND threephase_active_power IS NOT NULL
GROUP BY device_id, measured_date;
```

### Pattern 7: Gold view DDL — G3 fleet daily rollup

```sql
-- terraform/modules/query/views/v_fleet_daily_rollup.sql.tftpl

CREATE OR REPLACE VIEW ${gold_db}.v_fleet_daily_rollup AS
SELECT
    measured_date,
    COUNT(DISTINCT device_id) AS device_count,
    SUM(total_kwh)            AS fleet_total_kwh,
    AVG(peak_power_w)         AS fleet_avg_power_w,
    MAX(peak_power_w)         AS fleet_peak_power_w
FROM ${gold_db}.v_daily_device_summary
GROUP BY measured_date;
```

### Pattern 8: Producer CLI (Python)

```python
# producer/producer.py

"""Local producer: simulates N energy meters, PUTs InstantaneousData to Firehose."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

import boto3
from botocore.exceptions import ClientError

# Make sibling fake_data_generator importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fake_data_generator import DeviceConfig, InstantaneousGenerator  # noqa: E402

LOG = logging.getLogger("producer")
MAX_BATCH = 500  # Firehose PutRecordBatch hard limit


def build_devices(n: int) -> list[DeviceConfig]:
    return [
        DeviceConfig(
            device_id=1000 + i,
            mac_address=f"aa:bb:cc:dd:ee:{i:02x}",
            serial=f"TE{1000 + i}",
        )
        for i in range(n)
    ]


def iter_records(generators: list[InstantaneousGenerator]) -> Iterator[dict]:
    now = datetime.now(timezone.utc)
    for gen in generators:
        rec = gen.generate_single(now)  # fake_data_generator API
        yield rec.to_dict()


def chunked(it: Iterable[dict], size: int) -> Iterator[list[dict]]:
    batch: list[dict] = []
    for item in it:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def put_batch(firehose, stream: str, records: list[dict]) -> int:
    payload = [{"Data": (json.dumps(r, default=str) + "\n").encode()} for r in records]
    resp = firehose.put_record_batch(DeliveryStreamName=stream, Records=payload)
    failed = resp.get("FailedPutCount", 0)
    if failed:
        LOG.warning("Firehose reported %d failed records out of %d", failed, len(records))
    return len(records) - failed


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--devices",      type=int, default=10)
    p.add_argument("--duration-min", type=int, default=60)
    p.add_argument("--stream-name",  required=True)
    p.add_argument("--region",       default="us-east-1")
    p.add_argument("--profile",      default="te-lake-producer")
    p.add_argument("--tick-seconds", type=int, default=60)
    p.add_argument("--log-level",    default="INFO")
    args = p.parse_args()

    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s | %(message)s")

    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    firehose = session.client("firehose")
    devices = build_devices(args.devices)
    generators = [InstantaneousGenerator(d) for d in devices]

    end = time.monotonic() + args.duration_min * 60
    tick = 0
    total = 0
    while time.monotonic() < end:
        tick += 1
        sent = 0
        try:
            for batch in chunked(iter_records(generators), MAX_BATCH):
                sent += put_batch(firehose, args.stream_name, batch)
        except ClientError as e:
            LOG.error("Firehose error on tick %d: %s", tick, e)
        total += sent
        LOG.info("tick=%d sent=%d total=%d", tick, sent, total)
        time.sleep(args.tick_seconds)

    LOG.info("Done. total_records=%d", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### Pattern 9: Budget with 3 thresholds

```hcl
# terraform/modules/observability/main.tf (excerpt)

resource "aws_sns_topic" "budget_alerts" {
  name = "${var.name_prefix}-budget-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_budgets_budget" "monthly" {
  name         = "${var.name_prefix}-budget"
  budget_type  = "COST"
  limit_amount = tostring(var.budget_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = [50, 80, 100]  # %-of-budget — with $10 limit → $5/$8/$10
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "PERCENTAGE"
      notification_type          = "ACTUAL"
      subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
    }
  }

  cost_filter {
    name = "TagKeyValue"
    values = ["user:Project$${var.project_name}"]  # Budgets tag-filter syntax
  }
}
```

### Pattern 10: GitHub Actions Terraform CI

```yaml
# .github/workflows/terraform-ci.yml
name: terraform-ci

on:
  pull_request:
    paths:
      - "terraform/**"
      - ".github/workflows/terraform-ci.yml"

jobs:
  terraform:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: terraform
    steps:
      - uses: actions/checkout@v4

      - uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: "1.9.8"
          terraform_wrapper: false

      - name: fmt
        run: terraform fmt -check -recursive

      - name: init (no backend)
        run: terraform init -backend=false

      - name: validate
        run: terraform validate -no-color
```

**Note:** `terraform plan` is intentionally NOT run in CI — planning requires real AWS credentials, which the repo (public, personal) should not expose. `fmt` + `validate` + `init -backend=false` catch 90 % of PR issues without secrets.

---

## Data Flow

```text
1. User starts producer locally
     python producer/producer.py --stream-name te-lake-instant-stream \
                                 --devices 10 --duration-min 60
     │
     ▼
2. Producer generates 10 InstantaneousData per minute and calls
   firehose.put_record_batch (batches of ≤500). Each record is
   a JSON object terminated by "\n".
     │  (Firehose accepts within ms; client gets ack)
     ▼
3. Firehose buffers in memory:
   - flushes every 300 s (time trigger hits first at this volume)
   - writes one .json.gz file per flush under
     s3://te-lake-landing-<uid>/instantaneous/year=YYYY/month=MM/day=DD/hour=HH/
     │
     ▼
4. EventBridge cron(0 */3 * * ? *) fires at :00 of hours 0,3,6,9,12,15,18,21 UTC
     │
     ▼
5. EventBridge target: start Glue job te-lake-bronze-to-silver
   with arguments: --bronze_path s3://…/instantaneous/
                   --silver_table glue_catalog.te_lake_silver.instantaneous_measurements
                   --watermark_hours 6
     │
     ▼
6. Glue job:
   (a) Reads last 6 h of Bronze (path glob) as DataFrame
   (b) Filters null device_id / measured_at
   (c) Casts measured_at to TIMESTAMP, derives measured_date
   (d) Adds _ingested_at = current_timestamp()
   (e) dropDuplicates on (device_id, measured_at)
   (f) MERGE INTO Silver on (device_id, measured_at) — idempotent
     │
     ▼
7. Iceberg metadata files (manifest-list, manifest, snapshot)
   written to s3://te-lake-silver-<uid>/instantaneous/metadata/
   Data files written under .../data/<partition>/...
     │
     ▼
8. User runs Athena query against te_lake_gold.v_hourly_energy
   in workgroup te-lake-analytics-wg
     │  (Athena reads latest Iceberg snapshot via Glue Catalog pointer)
     ▼
9. Results delivered to s3://te-lake-athena-<uid>/query-results/
   (auto-cleaned after 3 days by lifecycle rule)
```

---

## Integration Points

| External System | Integration Type | Authentication |
|-----------------|------------------|----------------|
| AWS Firehose (from producer) | AWS SDK (`boto3.client("firehose")`) → `PutRecordBatch` | IAM user access key in `~/.aws/credentials` profile `te-lake-producer` |
| AWS Glue Catalog (from Athena) | Implicit — same account | Athena workgroup uses the caller's principal |
| AWS Glue Catalog (from Glue job) | Iceberg SparkCatalog | Glue job role (`aws_iam_role.glue_job`) |
| AWS S3 (from Firehose) | Managed delivery | Firehose delivery role |
| AWS S3 (from Glue job) | `s3a://` reads + writes | Glue job role |
| AWS S3 (from Athena) | Query results + data scan | Athena workgroup + caller principal |
| AWS SNS email (Budgets alert) | SNS topic subscription | Email confirmation |

---

## Testing Strategy

| Test Type | Scope | Files | Tools | Coverage Goal |
|-----------|-------|-------|-------|---------------|
| **Terraform static** | Syntax + schema | all `*.tf` | `terraform validate`, `terraform fmt -check` | 100 % |
| **Terraform plan snapshot** | Intended diff | `terraform plan` output | Manual review in PR | Key resources present |
| **Producer unit** | `chunked`, `iter_records`, `build_devices` | `producer/tests/test_producer.py` (optional) | pytest | 70 % (MVP — producer logic is thin) |
| **Glue job local smoke** | PySpark script runs on sample JSON | `glue_jobs/tests/` (optional) | pytest + Spark-local | Schema contract |
| **E2E — ingestion** | Producer → Firehose → S3 | Manual (AT-002) | AWS CLI `aws s3 ls` | 1 object delivered |
| **E2E — ETL** | Manual Glue run → Silver populated | Manual (AT-003) | `aws glue start-job-run` + Athena `SELECT COUNT(*)` | Row count > 0 |
| **E2E — idempotency** | Re-run Glue job; no duplicates | Manual (AT-004) | Athena `SELECT COUNT(*)` twice | Same count |
| **E2E — Gold views** | 3 queries return expected shape | Manual (AT-005/006/007) | Athena Console | All 3 views return rows |
| **E2E — destroy** | `terraform destroy` + console verify | Manual (AT-009) | AWS CLI | 0 project resources |
| **E2E — re-apply after destroy** | Clean state replays | Manual (AT-010) | `terraform apply` | Idempotent |
| **CI — PR gate** | fmt + validate + init | GH Actions | `.github/workflows/terraform-ci.yml` | Every PR |

**Unit tests for producer and Glue job script are MVP-optional** — E2E manual tests are the primary validation. Add unit tests post-MVP if refactoring.

---

## Error Handling

| Error Type | Handling Strategy | Retry? |
|------------|-------------------|--------|
| Firehose throttling (`ProvisionedThroughputExceeded`) | Producer logs warning with failed count from `FailedPutCount`; retry only the failed subset on next tick (producer's next iteration). At 10 devices no throttling expected. | Implicit (next tick) |
| Firehose transient network error | `boto3` default retries (5 attempts, adaptive mode) | Yes (SDK-level) |
| Firehose delivery error to S3 | Error objects land under `errors/` prefix in Bronze; CloudWatch log group captures details | Automatic re-attempt per Firehose config (24 h) |
| Glue job failure (script error / OOM) | Job returns non-zero; EventBridge target does NOT retry (explicit — retry = new cron fire); CloudWatch log retained 7 days; next 3-h cycle reprocesses the watermark window | Via next scheduled run |
| Malformed JSON in Bronze | Spark `mode="PERMISSIVE"` returns row with null columns; downstream filter drops any record missing `device_id` or `measured_at` | No (drop) |
| Duplicate event in Bronze (Firehose retry) | Silver `MERGE INTO` on `(device_id, measured_at)` deduplicates | Idempotent |
| Glue job run overlaps next cron fire | Glue job timeout = 5 min; cron is every 3 h → impossible to overlap | N/A |
| Athena query exceeds 1 GB scan | Workgroup rejects query with `Query has exceeded the maximum limit` error | Manual (user simplifies query) |
| `terraform destroy` fails on non-empty S3 bucket | All buckets have `force_destroy = true` | N/A |
| `terraform destroy` fails on Athena views | Destroy-time provisioner on `null_resource.gold_view` runs `DROP VIEW IF EXISTS` before Glue DB destroys | N/A |
| AWS Budgets notification undeliverable (unconfirmed email) | User sees Budgets console warning; email must be confirmed once | Manual |
| Producer IAM key compromise | `terraform destroy` + `terraform apply` rotates the key; no long-term secret | Re-apply |

---

## Configuration

All values set in `terraform/terraform.tfvars` (not committed; `.example` is the template).

| Config Key | Type | Default | Description |
|------------|------|---------|-------------|
| `project_name` | `string` | `"te-lake"` | Prefix for all resource names + tag value |
| `region` | `string` | `"us-east-1"` | AWS region for all regional resources |
| `budget_limit_usd` | `number` | `10` | Monthly Budget limit; alerts at 50/80/100 % |
| `alert_email` | `string` | `""` | Email for SNS budget-alert subscription (must confirm) |
| `glue_cadence_cron` | `string` | `"cron(0 */3 * * ? *)"` | EventBridge cron for Glue job (UTC) |
| `firehose_buffer_size_mb` | `number` | `128` | Firehose size buffer threshold (MB) |
| `firehose_buffer_seconds` | `number` | `300` | Firehose time buffer threshold (s, max 900) |
| `athena_bytes_scanned_cutoff` | `number` | `1073741824` | Workgroup per-query scan limit (bytes) — 1 GB |
| `producer_device_count` | `number` | `10` | Passed to producer README; not consumed by Terraform |
| `watermark_hours` | `number` | `6` | Glue job re-scan window over Bronze |
| `bronze_retention_days` | `number` | `7` | S3 lifecycle delete for Bronze |
| `athena_results_retention_days` | `number` | `3` | S3 lifecycle delete for Athena result staging |

---

## Security Considerations

- **Least-privilege IAM:** each of the 4 roles/users has the narrowest action set and specific resource ARNs (no wildcards). Producer IAM user: only `firehose:PutRecordBatch` + `firehose:DescribeDeliveryStream` on the single stream ARN.
- **No secrets in git:** `.gitignore` covers `*.tfstate*`, `*.tfvars`, `.terraform/`. Producer access key is a Terraform `output sensitive = true` — must be extracted via `terraform output -json | jq` locally, never logged.
- **S3 encryption:** all buckets SSE-S3 (AWS-managed keys). KMS CMK is out of scope (would add $1/month per key — eats budget).
- **Public bucket blocking:** all 3 buckets have `block_public_acls`, `block_public_policy`, `ignore_public_acls`, `restrict_public_buckets` = true.
- **Athena scan cap:** 1 GB per query (workgroup-enforced) prevents runaway spend.
- **No account ID in code:** resource names use `${name_prefix}` pattern and random 6-char suffix (`random_id.suffix`), making bucket names globally unique without hard-coded account ID.
- **Firehose in-transit:** TLS via SDK default.
- **CloudWatch log retention:** 7 days on all log groups (cheap + enough to debug).
- **No VPC:** all services run in AWS-managed networking; the only inbound from the internet is Firehose (managed endpoint with TLS).
- **MFA for AWS root / admin:** documented as prerequisite in README; not enforced by Terraform (out of scope).

---

## Observability

| Aspect | Implementation |
|--------|----------------|
| **Logging — Firehose** | CloudWatch log group `/aws/kinesisfirehose/${name_prefix}-instant-stream`, stream `S3Delivery`, retention 7 d |
| **Logging — Glue job** | CloudWatch log group `/aws-glue/jobs/output` (default Glue behavior); `--enable-continuous-cloudwatch-log true` for realtime |
| **Logging — Producer** | Structured Python logging to stdout (INFO level by default, `--log-level` flag) |
| **Metrics — Firehose** | Built-in CloudWatch metrics (`IncomingRecords`, `IncomingBytes`, `DeliveryToS3.Success`) — no dashboard; reviewed ad-hoc in console |
| **Metrics — Glue** | Job run metrics (`glue.driver.aggregate.recordsRead`, etc.) via `--enable-metrics true`; visible in Glue console Run History |
| **Metrics — Athena** | `bytes_scanned_cutoff_per_query` enforced; per-query stats in Athena console |
| **Alerts** | AWS Budgets → SNS email at 50 % / 80 % / 100 % of `$budget_limit_usd` |
| **Tracing** | Out of scope (X-Ray would add cost + complexity; no distributed calls to trace) |
| **Cost visibility** | Default Cost Explorer; resources tagged with `Project=${project_name}` via `default_tags` so filter is 1-click |

---

## Pipeline Architecture

### DAG Diagram

```text
        ┌─────────────────┐
        │ Local Producer  │ ← CLI invocation (manual)
        └────────┬────────┘
                 │
       PutRecordBatch (every 60 s)
                 ▼
        ┌─────────────────┐
        │   Firehose      │ buffer 128 MB / 300 s
        └────────┬────────┘
                 │ .json.gz objects
                 ▼
        ┌─────────────────┐
        │  S3 Bronze      │ year=/month=/day=/hour=
        │  (landing)      │ lifecycle: 7 d
        └────────┬────────┘
                 │
   cron(0 */3 * * ? *)  ← EventBridge
                 ▼
        ┌─────────────────┐
        │  Glue Job       │ Spark 3.5 + Iceberg 1.6
        │  bronze_to_     │ max 2 DPU / 5 min
        │  silver         │
        └────────┬────────┘
                 │ MERGE INTO (idempotent)
                 ▼
        ┌─────────────────┐
        │  S3 Silver      │ Iceberg table
        │  instantaneous_ │ partitioned by
        │  measurements   │   measured_date,
        │                 │   bucket(8, device_id)
        └────────┬────────┘
                 │
                 ▼
        ┌─────────────────────────────────┐
        │  Athena Gold Views              │
        │   v_hourly_energy         (G1)  │
        │   v_daily_device_summary  (G2)  │
        │   v_fleet_daily_rollup    (G3)  │
        └─────────────────────────────────┘
```

### Partition Strategy

| Table | Partition Key | Granularity | Rationale |
|-------|-------------|-------------|-----------|
| S3 Bronze (path-based, not Iceberg) | `year/month/day/hour` (delivery time) | Hourly | Firehose default; Glue job globs last 6 h |
| Silver `instantaneous_measurements` | `measured_date` + `bucket(8, device_id)` | Daily + 8 buckets | Daily pruning for all Gold queries; bucket for parallel writes and future device-scan queries |

### Incremental Strategy

| Model | Strategy | Key Column | Lookback |
|-------|----------|------------|----------|
| `silver.instantaneous_measurements` | `merge_incremental` via Iceberg `MERGE INTO` | `(device_id, measured_at)` | 6 h watermark (cadence=3 h; overlap=3 h absorbs delivery lag) |
| `gold.v_*` | Views — always current | N/A | N/A |

### Schema Evolution Plan

| Change Type | Handling | Rollback |
|-------------|----------|----------|
| **New column in `InstantaneousData`** | (a) Add column to `locals.silver_columns` in Terraform; (b) add to `build_schema()` in Glue script; (c) `terraform apply` → Iceberg column add is online + backwards-compatible | Remove from Terraform list + Glue schema; Iceberg `ALTER TABLE DROP COLUMN` if previously applied |
| **Column type widening** (INT→BIGINT, FLOAT→DOUBLE) | Iceberg supports; same 3-step apply | Iceberg doesn't support narrowing — write migration job |
| **Column removal** | Deprecate (stop writing) for one snapshot generation, then drop via Terraform + Iceberg `ALTER TABLE DROP COLUMN` | Re-add via Terraform |
| **Partition spec change** | Iceberg v2 supports spec evolution — old data keeps old spec, new data uses new spec. Apply via `ALTER TABLE ... REPLACE PARTITION FIELD` SQL (not Terraform-native; run via Athena DDL) | Another `ALTER TABLE` call |
| **Gold view change** | Edit `.sql.tftpl` → `terraform apply` (triggers `null_resource` recreate via `triggers.ddl`) | Revert SQL file + `terraform apply` |

### Data Quality Gates

| Gate | Tool | Threshold | Action on Failure |
|------|------|-----------|-------------------|
| Null `device_id` or `measured_at` in Bronze | Glue job `filter()` | Drop silently; log count | Log-only (records counted, not quarantined, for MVP) |
| Duplicate `(device_id, measured_at)` | Iceberg MERGE | 0 duplicates after MERGE | Built-in — MERGE deduplicates |
| Row count delta Bronze→Silver | Glue job logs read/written | `dropped <= 1 %` of read | Log-warn if > 1 %; MVP does not block |
| Freshness — Bronze | Firehose `DeliveryToS3.Success` metric | ≥ 1 success in last 10 min while producer is running | Manual console check; MVP no automated alert |
| Freshness — Silver | Iceberg `committed_at` on latest snapshot | Within 3.5 h of now | `SELECT max(committed_at) FROM "silver".instantaneous_measurements$snapshots` — manual check |
| Budget crossed | AWS Budgets | > 50 % / 80 % / 100 % | SNS email |

**Note:** Great Expectations / Glue Data Quality were explicitly cut from scope (DEFINE "Out of Scope"). Quality gates are Glue-job-inline + Iceberg-native + Budgets-native — sufficient for portfolio MVP.

---

## Cost Model (7-day demo, worst case)

| Service | Driver | Calculation | Cost |
|---------|--------|-------------|------|
| Firehose | Data ingested | ~15 MB/day × 7 d × $0.029/GB | < $0.01 |
| S3 storage | Bronze + Silver + Athena | ~50 MB avg × $0.023/GB-month × 7/30 | < $0.01 |
| S3 requests | PUTs + GETs | ~100 / day Firehose PUTs + Glue reads | < $0.05 |
| Glue Job | 2 DPU × 5 min × 8 runs/day × 7 d = 4.67 DPU-hr | 4.67 × $0.44 | **~$2.05** |
| Athena | Queries during demo | ~50 queries × 10 MB scanned × $5/TB | < $0.01 |
| EventBridge | 56 rule matches | Free tier | $0.00 |
| CloudWatch Logs | ~10 MB ingest | $0.50/GB × 0.01 | < $0.01 |
| SNS | ~3 emails | 1,000 free | $0.00 |
| Data transfer | None (all in-region) | — | $0.00 |
| **TOTAL (7 days)** | | | **≈ $2.15** |

**Headroom:** ~$7.85 vs $10 budget. A 30-day run would be ~$9 — still within budget if the user leaves it running by accident (which Budgets alerts will catch).

---

## Destroy Order (verified)

Terraform destroys in reverse dependency order. Verified safe sequence:

1. `null_resource.gold_view[*]` — destroy-time provisioner runs `DROP VIEW IF EXISTS` via Athena CLI
2. `aws_cloudwatch_event_target` + `aws_cloudwatch_event_rule` — EventBridge schedule removed (prevents new Glue runs during destroy)
3. `aws_glue_job` — any in-flight run is unaffected; new runs blocked
4. `aws_glue_catalog_table.instantaneous` — Iceberg table registration removed from Glue Catalog
5. `aws_glue_catalog_database.silver` + `.gold` — databases destroyed (empty now)
6. `aws_athena_workgroup.analytics` — workgroup removed (with `force_destroy = true` on workgroup)
7. `aws_kinesis_firehose_delivery_stream.instant` — stream removed; any in-flight records lost (acceptable — producer off by this time)
8. `aws_iam_user.producer`, `aws_iam_role.firehose/glue/eventbridge` + attached policies — IAM removed
9. `aws_s3_bucket.*` — `force_destroy = true` empties all objects (Iceberg data, metadata, Bronze gz, Athena results) and removes buckets
10. `aws_sns_topic_subscription` + `aws_sns_topic` + `aws_budgets_budget` + `aws_cloudwatch_log_group.*` — observability tear-down

**Pre-destroy checklist for the user:**
- Stop `producer/producer.py` (Ctrl-C)
- Confirm email subscription is unsubscribed if re-applying to a new topic soon (otherwise no action)
- Run `terraform destroy -auto-approve`

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-20 | design-agent | Initial design derived from DEFINE_aws-data-lakehouse.md |

---

## Next Step

**Ready for:** `/build .claude/sdd/features/DESIGN_aws-data-lakehouse.md`
