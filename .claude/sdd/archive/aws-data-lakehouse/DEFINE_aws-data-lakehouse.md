# DEFINE: AWS Data Lakehouse (Personal Portfolio Project)

> Build a fully destroyable, serverless AWS data lakehouse (Firehose → S3 Bronze → Glue/PySpark → Iceberg Silver → Athena Gold) for simulated energy-meter telemetry, provisioned by Terraform and kept under a $10 USD total-cost ceiling.

## Metadata

| Attribute | Value |
|-----------|-------|
| **Feature** | aws-data-lakehouse |
| **Date** | 2026-04-20 |
| **Author** | define-agent |
| **Status** | ✅ Shipped 2026-04-21 |
| **Clarity Score** | 15/15 |
| **Source** | `.claude/sdd/features/BRAINSTORM_aws-data-lakehouse.md` |

---

## Problem Statement

Bruno wants to learn and publicly demonstrate AWS data-lakehouse skills (Firehose + Iceberg + Glue + Athena + Terraform) via a portfolio-grade GitHub project, but cannot afford ongoing AWS charges. A usable end-to-end lakehouse on AWS typically requires either (a) always-on EMR/EC2 infrastructure that rapidly exceeds a personal budget, or (b) a fragmented, half-serverless setup that fails to showcase the full medallion pattern. The outcome must be a one-command `terraform apply` → working Bronze/Silver/Gold pipeline → `terraform destroy` → $0 residual, with total lifetime spend provably under **$10 USD**.

---

## Target Users

| User | Role | Pain Point |
|------|------|------------|
| **Bruno (author)** | Solo developer building AWS expertise | Needs hands-on reps with Iceberg/Glue/Athena/Terraform without risking personal money; current private-cloud (CL9) stack doesn't teach AWS-native services |
| **Portfolio reviewer** | Recruiter / hiring manager / interviewer | Needs to quickly judge the author's senior-DE grasp (Iceberg, Glue, Athena, IAM, Terraform modules) from a single public repo — ideally in under 10 minutes |
| **Future Bruno (re-runner)** | Author returning months later or fork-user | Needs the repo to be idempotent: clone → `terraform apply` → working lakehouse → `terraform destroy` → no leftover charges, with zero tribal knowledge required |

---

## Goals

What success looks like (prioritized):

| Priority | Goal |
|----------|------|
| **MUST** | `terraform apply` on a clean AWS account provisions the full stack (Firehose + 3 S3 buckets + Glue DB/table/job + EventBridge rule + Athena workgroup + IAM + Budgets) with zero errors |
| **MUST** | Local producer (`producer/producer.py`) pushes simulated `InstantaneousData` records to Firehose; records land in S3 Bronze within 5 min |
| **MUST** | Scheduled Glue PySpark job reads Bronze, writes/MERGES into an Iceberg Silver table registered in Glue Catalog, idempotent on `(device_id, measured_at)` |
| **MUST** | Three Athena Gold views exist in `te_lake_gold` catalog and return correct results: `v_hourly_energy` (G1), `v_daily_device_summary` (G2), `v_fleet_daily_rollup` (G3) |
| **MUST** | `terraform destroy` completes cleanly with no manual S3 emptying, leaving $0 residual resources |
| **MUST** | Total AWS cost for a 3–7 day demo window stays **under $10 USD**, verified via Cost Explorer |
| **MUST** | AWS Budgets alerts configured at $5 / $8 / $10 thresholds, wired to SNS email |
| **SHOULD** | Public GitHub repo with README containing Mermaid architecture diagram, 3 sample Athena queries, and a "how to run / how to destroy" section |
| **SHOULD** | GitHub Actions workflow runs `terraform fmt -check && terraform validate && terraform plan` on every PR |
| **SHOULD** | Terraform is organized in modules (`storage/`, `ingestion/`, `catalog/`, `etl/`, `query/`, `observability/`) to demonstrate IaC structure discipline |
| **COULD** | README includes screenshots of Athena query results showing each Gold view |
| **COULD** | Architecture doc (`docs/architecture.md`) contains a cost breakdown table mapped to AWS pricing |

**Priority Guide:**
- **MUST** = MVP fails without this
- **SHOULD** = Important, but workaround exists
- **COULD** = Nice-to-have, cut first if needed

---

## Success Criteria

Measurable outcomes (must include numbers):

- [ ] `terraform apply` completes in **≤ 5 minutes** with zero errors on a clean AWS account
- [ ] `terraform destroy` completes in **≤ 3 minutes** with zero errors and zero manual intervention
- [ ] After producer runs for 60 min with 10 simulated devices, S3 Bronze contains **≥ 1 delivered Firehose object** (time buffer ≤ 300 s)
- [ ] After first scheduled Glue run, Silver row count matches producer output **within 1% tolerance** (allowing Firehose buffer boundaries)
- [ ] `SELECT COUNT(*) FROM te_lake_silver.instantaneous_measurements` returns the same count across two consecutive runs (proves idempotent MERGE)
- [ ] Athena query `SELECT * FROM te_lake_gold.v_hourly_energy` returns **≥ 1 row per device per hour** of producer activity
- [ ] Athena query on `te_lake_gold.v_daily_device_summary` returns exactly one row per `(device_id, measured_date)` with non-null `min_voltage`, `avg_voltage`, `max_voltage`, `peak_power_w`, `total_kwh`, `measurement_count`
- [ ] Athena query on `te_lake_gold.v_fleet_daily_rollup` returns exactly one row per `measured_date` with fleet-total kWh
- [ ] Total AWS bill for the demo window is **< $10 USD** (verified in Cost Explorer at teardown)
- [ ] Glue job `max_capacity = 2` and `timeout ≤ 5 min` set in Terraform (defense-in-depth against runaway cost)
- [ ] All S3 buckets declared with `force_destroy = true` and Bronze bucket has lifecycle rule deleting objects `> 7 days`
- [ ] GitHub repo is public with `.gitignore` covering `*.tfstate*`, `.terraform/`, `*.tfvars` (except `.example`); no secrets / account IDs in git history
- [ ] GitHub Actions PR workflow passes on `main` with `terraform fmt -check`, `terraform validate`, `terraform plan` (plan with dummy / OIDC-read credentials or `-refresh=false`)

---

## Acceptance Tests

| ID | Scenario | Given | When | Then |
|----|----------|-------|------|------|
| AT-001 | Green-field apply | Clean AWS account, `terraform.tfvars` with region+budget set | `terraform init && terraform apply -auto-approve` is run | Exits 0, all resources created, `terraform output` prints Firehose stream name + bucket names + Athena workgroup |
| AT-002 | Producer delivers to Bronze | Stack is applied; IAM user creds exported locally | `python producer/producer.py --devices 10 --duration-min 10` runs | Within 10 min of start, `aws s3 ls s3://<landing-bucket>/instantaneous/ --recursive` shows ≥ 1 object |
| AT-003 | Scheduled Glue job materializes Silver | Bronze has at least 60 min of data | Next EventBridge trigger fires (or manual `aws glue start-job-run`) | Job succeeds in < 5 min; `SELECT COUNT(*) FROM te_lake_silver.instantaneous_measurements` > 0 in Athena |
| AT-004 | Idempotent MERGE | Silver already has N rows; producer has not added new data | Glue job is re-run | Silver row count still = N (MERGE finds no new keys) |
| AT-005 | Gold view — hourly energy | Silver has ≥ 2 hours of data for device D | Athena query `SELECT * FROM te_lake_gold.v_hourly_energy WHERE device_id = D` | Returns ≥ 2 rows, one per hour, with `kwh > 0` |
| AT-006 | Gold view — daily device summary | Silver has 1 day of data for device D | Athena query `v_daily_device_summary WHERE device_id = D` | Returns exactly 1 row for that day with non-null aggregates |
| AT-007 | Gold view — fleet rollup | Silver has N devices reporting on day X | Athena query `v_fleet_daily_rollup WHERE measured_date = X` | Returns exactly 1 row with `total_kwh = SUM(v_daily_device_summary.total_kwh)` for day X |
| AT-008 | Budget alert fires | Budget set to $5/$8/$10 with SNS email subscription confirmed | Simulated/actual spend crosses $5 | Subscribed email receives AWS Budgets alert within 24 h |
| AT-009 | Destroy-on-demand | Full stack applied with data in all buckets | `terraform destroy -auto-approve` is run | Exits 0 in ≤ 3 min; `aws s3 ls` shows zero project buckets; `aws glue get-databases` shows project DBs gone |
| AT-010 | Re-apply after destroy | Stack destroyed; state file clean | `terraform apply` is run again | Exits 0; stack re-provisions identically (no drift, no resource name collisions) |
| AT-011 | Glue guardrails enforced | Terraform plan output | `terraform show -json tfplan \| jq` on glue job resource | `max_capacity == 2` and `timeout == 5` |
| AT-012 | PR CI passes | Branch with valid Terraform changes | PR opened against `main` | GH Actions workflow passes: `fmt -check`, `validate`, `plan` all green |
| AT-013 | PR CI blocks bad format | Branch with unformatted `.tf` file | PR opened | `terraform fmt -check` step fails, PR marked failing |
| AT-014 | No secrets in repo | Git history of the public repo | `git log -p \| grep -iE 'AKIA\|aws_secret\|account-id'` | Returns zero matches |

---

## Out of Scope

Explicitly NOT included in this feature (carried over from BRAINSTORM YAGNI list):

- **`SyncParametersData` Silver table** — schema defined in generator but no Gold view needs it (future work)
- **`DeviceData` dimension table / SCD-1** — Gold views operate on `device_id` alone (future work)
- **EMR / EMR Serverless / self-managed Spark** — explicitly rejected for budget reasons
- **Lambda / ECS / EC2 producer runtime** — local producer chosen; swap-in is a future option
- **Kinesis Data Streams** — Firehose Direct PUT sufficient at this volume
- **Step Functions orchestration** — EventBridge cron is enough for a single Glue job
- **Data quality framework** (Glue Data Quality, Deequ, Great Expectations)
- **Glue Crawler** — Iceberg table DDL declared in Terraform
- **`tfsec` / `checkov` / `infracost` / `pre-commit` hooks** — defer to post-MVP hardening
- **Remote Terraform state** (S3 + DynamoDB) — local state is sufficient for single-dev personal project
- **Multi-environment layouts** (dev/stg/prod) — single-env MVP
- **CloudWatch dashboards** — Budgets SNS alerts are enough safety
- **Cost Anomaly Detection** — overlap with Budgets
- **VPC / private networking** — all services are AWS-managed; not needed
- **Slack / PagerDuty / non-email alerts** — email via SNS is enough
- **Any non-AWS cloud** — strictly AWS-only
- **Real-time / sub-minute freshness** — 3-hour batch cadence is the target
- **Production-grade security hardening** (KMS CMK per bucket, CloudTrail data events, GuardDuty) — defaults are acceptable for portfolio demo

---

## Constraints

| Type | Constraint | Impact |
|------|------------|--------|
| **Budget** | Hard ceiling $10 USD lifetime | Disqualifies EMR-on-EC2, always-on clusters, materialized Gold tables; drives Glue DPU/timeout caps; drives 3-hour cadence over hourly |
| **Teardown** | Every resource must destroy via `terraform destroy` | All S3 buckets `force_destroy = true`; avoid resources with destroy-prevention (no non-empty ECR, no Aurora snapshots, etc.) |
| **Producer location** | Producer runs locally, outside AWS | Only ingress: IAM user with `firehose:PutRecordBatch`; no VPC / endpoint; credentials must stay out of git |
| **IaC** | Terraform ≥ 1.0 + AWS Provider ≥ 5.0 (per CLAUDE.md) | Use modern provider features (e.g., `aws_glue_catalog_table` Iceberg support); AWS Provider 5.x syntax |
| **Language** | Python 3.11 for producer; Glue 4.0 / 5.0 runtime for PySpark job | Glue 4.0 = Python 3.10/Spark 3.3 + Iceberg 1.0; Glue 5.0 = Python 3.11/Spark 3.5 + Iceberg 1.6 — prefer Glue 5.0 |
| **Region** | Default `us-east-1` (cheapest + widest service availability); exposed as Terraform variable | All regional resources parameterized |
| **Security** | IAM least-privilege per role; no wildcard resources in policies; no long-lived access keys checked in | Producer IAM user's secret key stays in local AWS profile; `.tfvars` with any sensitive values not committed |
| **Public repo** | Repo will be public on GitHub | No account IDs, no ARNs with account numbers in committed examples; `.gitignore` covers state files and tfvars |
| **Team size** | Single developer | No remote state, no multi-env, no complex branching |
| **Demo window** | 3–7 days of running infra | S3 lifecycle on Bronze set to 7 days matches; Silver survives the window; total cost dominated by Glue runs + Firehose |

---

## Technical Context

> Essential context for Design phase — prevents misplaced files and missed infrastructure needs.

| Aspect | Value | Notes |
|--------|-------|-------|
| **Deployment Location** | `terraform/` (modules under `terraform/modules/`), `glue_jobs/`, `producer/`, `.github/workflows/`, `docs/` at repo root | New top-level dirs alongside existing `fake_data_generator/` (unchanged) |
| **KB Domains** | `lakehouse` (Iceberg table layout, partition spec, MERGE semantics), `pipeline` (batch orchestration, EventBridge), `aws` (Glue Job, Firehose, Athena, IAM patterns) | Consult during Design for Iceberg partitioning and Glue Iceberg connector config |
| **IaC Impact** | **All new resources** — greenfield. ~20 Terraform resources total: 3 S3 buckets, 1 Firehose delivery stream, 1 Glue database (silver), 1 Glue database (gold), 1 Glue table (Iceberg silver), 1 Glue job, 1 EventBridge rule + target, 1 Athena workgroup, 3 Athena views (via `aws_athena_named_query` or inline DDL), 1 Budget, 1 SNS topic + subscription, IAM roles (firehose-delivery, glue-job, athena-user), 1 IAM user (producer) | No modifications to existing systems |

**Why This Matters:**

- **Location** → Design phase places `.tf` in `terraform/modules/<module>/`, Glue script in `glue_jobs/bronze_to_silver.py`, producer in `producer/producer.py`
- **KB Domains** → Design phase pulls Iceberg partitioning patterns (avoid common pitfalls like `device_id` as partition key causing small-file problem)
- **IaC Impact** → Design must enumerate every resource, IAM action, and inter-module reference (bucket ARNs, role ARNs, stream name)

---

## Data Contract

### Source Inventory

| Source | Type | Volume | Freshness | Owner |
|--------|------|--------|-----------|-------|
| Local `fake_data_generator.FakeDataOrchestrator` → boto3 → Firehose | Local Python process (simulated IoT) | 10 devices × 1 record/min = 14,400 records/day (~15 MB/day JSON; ~3 MB/day Parquet) | Near-real-time while producer is running | Bruno |

### Schema Contract — Bronze

Raw Firehose delivery. No enforced schema; files are JSON objects (one record per line or record-delimited) produced by `InstantaneousData.to_json()`. Path: `s3://<landing>/instantaneous/year=YYYY/month=MM/day=DD/hour=HH/`.

### Schema Contract — Silver (`te_lake_silver.instantaneous_measurements`)

Iceberg table in Glue Catalog, derived from `InstantaneousData` dataclass:

| Column | Type | Constraints | PII? |
|--------|------|-------------|------|
| `device_id` | `BIGINT` | NOT NULL, part of primary key for MERGE | No |
| `measured_at` | `TIMESTAMP` | NOT NULL, part of primary key for MERGE | No |
| `mac_address` | `STRING` | Nullable | No |
| `voltage_a` / `voltage_b` / `voltage_c` | `DOUBLE` | Nullable | No |
| `voltage_ab` / `voltage_bc` / `voltage_ca` | `DOUBLE` | Nullable | No |
| `current_a` / `current_b` / `current_c` | `DOUBLE` | Nullable | No |
| `active_power_a` / `active_power_b` / `active_power_c` | `DOUBLE` | Nullable | No |
| `threephase_active_power` | `DOUBLE` | Nullable — driver for G1/G2 kWh calcs | No |
| `reactive_power_a/b/c`, `threephase_reactive_power` | `DOUBLE` | Nullable | No |
| `apparent_power_a/b/c`, `threephase_apparent_power` | `DOUBLE` | Nullable | No |
| `frequency_a/b/c` | `DOUBLE` | Nullable | No |
| `power_factor_a/b/c` | `DOUBLE` | Nullable | No |
| `temperature` | `DOUBLE` | Nullable | No |
| `angle_a/b/c` | `DOUBLE` | Nullable | No |
| `neutral_current` | `DOUBLE` | Nullable | No |
| `timezone` | `INT` | Nullable | No |
| `daylight_saving_time` | `INT` | Nullable | No |
| `measured_date` | `DATE` | Derived column (`CAST(measured_at AS DATE)`); partition key | No |
| `_ingested_at` | `TIMESTAMP` | NOT NULL, audit column set by Glue job | No |

**Partitioning:** `PARTITIONED BY (measured_date, bucket(8, device_id))` — daily time pruning + device parallelism.

**MERGE key:** `(device_id, measured_at)` — guarantees idempotency on reprocess.

### Schema Contract — Gold (Athena views)

**G1 — `te_lake_gold.v_hourly_energy`**

| Column | Type | Derivation |
|--------|------|------------|
| `device_id` | BIGINT | from Silver |
| `measured_date` | DATE | from Silver |
| `hour_of_day` | INT | `HOUR(measured_at)` |
| `avg_active_power_w` | DOUBLE | `AVG(threephase_active_power)` over the hour |
| `kwh` | DOUBLE | `avg_active_power_w * 1h / 1000` (trapezoidal-free simplification for MVP) |
| `sample_count` | INT | `COUNT(*)` minutes-recorded in that hour |

**G2 — `te_lake_gold.v_daily_device_summary`**

| Column | Type | Derivation |
|--------|------|------------|
| `device_id` | BIGINT | |
| `measured_date` | DATE | |
| `min_voltage` | DOUBLE | `MIN(voltage_a)` |
| `avg_voltage` | DOUBLE | `AVG(voltage_a)` |
| `max_voltage` | DOUBLE | `MAX(voltage_a)` |
| `peak_power_w` | DOUBLE | `MAX(threephase_active_power)` |
| `total_kwh` | DOUBLE | `SUM(v_hourly_energy.kwh)` for that device-day |
| `measurement_count` | INT | `COUNT(*)` minutes recorded that day |
| `avg_power_factor` | DOUBLE | `AVG(power_factor_a)` |

**G3 — `te_lake_gold.v_fleet_daily_rollup`**

| Column | Type | Derivation |
|--------|------|------------|
| `measured_date` | DATE | |
| `device_count` | INT | `COUNT(DISTINCT device_id)` |
| `fleet_total_kwh` | DOUBLE | `SUM(v_daily_device_summary.total_kwh)` |
| `fleet_avg_power_w` | DOUBLE | `AVG(v_daily_device_summary.peak_power_w)` |
| `fleet_peak_power_w` | DOUBLE | `MAX(v_daily_device_summary.peak_power_w)` |

### Freshness SLAs

| Layer | Target | Measurement |
|-------|--------|-------------|
| **Bronze (S3 landing)** | Data available within ≤ 5 min of `put_record_batch` call | Firehose 300 s time buffer + ≤ 60 s delivery |
| **Silver (Iceberg)** | Refreshed every 3 h (EventBridge `cron(0 */3 * * ? *)`) | Glue job successful run timestamp; max staleness ≈ 3 h + job runtime |
| **Gold (Athena views)** | As fresh as Silver (views, not materializations) | No batch; always at Silver freshness |

### Completeness Metrics

- ≥ 99 % of producer-generated records land in Bronze (loss budget: Firehose retry + occasional network blip)
- ≥ 99 % of Bronze records land in Silver (loss budget: transient Glue job failure + next-run recovery)
- Zero duplicates in Silver for any `(device_id, measured_at)` across repeated Glue runs (MERGE guarantee)
- Zero null `device_id` or `measured_at` in Silver (enforced by Glue job filter — drop invalid records to quarantine prefix in Bronze or reject outright for MVP)

### Lineage Requirements

- Producer → Bronze: object key includes `year=YYYY/month=MM/day=DD/hour=HH/` so Bronze→Silver mapping is trivially time-partitioned
- Bronze → Silver: Glue job logs each run's input S3 prefix + row counts read/written to CloudWatch
- Silver → Gold: view DDL is versioned in `terraform/modules/query/` — schema changes visible in git blame
- Column-level lineage tool (OpenMetadata / DataHub): **out of scope** for MVP

---

## Assumptions

Assumptions that if wrong could invalidate the design:

| ID | Assumption | If Wrong, Impact | Validated? |
|----|------------|------------------|------------|
| A-001 | Glue 5.0 runtime with bundled Iceberg 1.6 connector is available in `us-east-1` and supports `MERGE INTO` from PySpark via Spark SQL | Would need to ship a Glue 4.0 job with a custom Iceberg JAR via `--extra-jars`, adding Terraform complexity | [ ] Verify during Design (AWS docs) |
| A-002 | Firehose Direct PUT → S3 (with or without Parquet format conversion) supports `measured_date` dynamic partitioning from record payloads | Might need a Lambda transformation, or accept a simpler `timestamp-partitioned` prefix that Glue reconciles | [ ] Verify during Design |
| A-003 | Athena engine v3 supports Iceberg tables written by Glue 5.0 natively without needing Athena-specific table creation | Would need to register the Iceberg table via Athena DDL (`CREATE TABLE … USING ICEBERG`) in addition to the Glue job creating it | [ ] Verify during Design |
| A-004 | 10 simulated devices × 1 record/min is the target scale (producer can be pointed at 1–100 devices via CLI arg) | Doesn't invalidate design, only cost math; still well under $10 at 100 devices | [x] Confirmed in brainstorm |
| A-005 | The existing `fake_data_generator` package can be imported and used from a local `producer/producer.py` without modification | Would need to refactor the generator | [x] Confirmed — `__init__.py` exposes required classes |
| A-006 | AWS account used is a personal account in good standing with no Service Control Policies blocking Glue / Athena / Firehose | Would need to request permissions | [ ] Verify before `terraform apply` |
| A-007 | 2 DPU × 5 min × 8 runs/day × 7 days = 4.67 DPU-hours/day ≈ $2.05/day for Glue will stay under $10 for a 4-day demo | Budget re-math; may need to drop to every-6h cadence | [x] Verified in brainstorm budget table |
| A-008 | `terraform destroy` on `aws_glue_catalog_database` with tables inside works without manual pre-deletion (Terraform handles dependency order) | Would need explicit `depends_on` or two-step destroy | [ ] Verify during Design |
| A-009 | Iceberg table files in S3 are deleted when `aws_s3_bucket.silver` has `force_destroy = true`, even though the Glue table references them | Confirmed — `force_destroy` deletes S3 objects regardless of catalog references | [x] Confirmed via Terraform docs |
| A-010 | Producer local machine has internet access and outbound HTTPS to `firehose.<region>.amazonaws.com` | Would need VPN / proxy workaround | [x] Standard dev-machine assumption |

**Note:** A-001 / A-002 / A-003 / A-006 / A-008 must be validated during DESIGN phase before committing to the approach. The rest are either confirmed or low-risk.

---

## Clarity Score Breakdown

| Element | Score (0-3) | Notes |
|---------|-------------|-------|
| Problem | 3 | Specific problem (learn + portfolio + $10 ceiling), specific impact (must be destroyable), no ambiguity |
| Users | 3 | Three personas (author, reviewer, future-author) with distinct pain points and success signals |
| Goals | 3 | 12 goals prioritized MUST/SHOULD/COULD; every MUST has a measurable success criterion |
| Success | 3 | 13 testable success criteria with explicit thresholds (time, cost, row counts, tolerance %) |
| Scope | 3 | 18 out-of-scope items explicit; 10 constraints enumerated; nothing left ambiguous |
| **Total** | **15/15** | Pre-validated by BRAINSTORM phase; ready for Design without clarification round |

**Minimum to proceed: 12/15** ✅

---

## Open Questions

None — ready for Design.

The four **unvalidated assumptions** (A-001, A-002, A-003, A-006, A-008) should be verified in the first step of the DESIGN phase (quick AWS-docs check, no user input needed). All other questions were resolved during brainstorm.

---

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-04-20 | define-agent | Initial version extracted from `BRAINSTORM_aws-data-lakehouse.md` |

---

## Next Step

**Ready for:** `/design .claude/sdd/features/DEFINE_aws-data-lakehouse.md`
