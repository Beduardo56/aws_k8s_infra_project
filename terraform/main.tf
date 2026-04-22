############################################
# Storage: S3 buckets (Bronze, Silver, Athena results)
############################################

module "storage" {
  source = "./modules/storage"

  name_prefix                   = local.name_prefix
  bronze_retention_days         = var.bronze_retention_days
  athena_results_retention_days = var.athena_results_retention_days
}

############################################
# Ingestion: Firehose + producer IAM user
############################################

module "ingestion" {
  source = "./modules/ingestion"

  name_prefix             = local.name_prefix
  landing_bucket_arn      = module.storage.landing_bucket_arn
  buffer_size_mb          = var.firehose_buffer_size_mb
  buffer_interval_seconds = var.firehose_buffer_seconds
}

############################################
# Catalog: Glue databases (silver, gold)
############################################

module "catalog" {
  source = "./modules/catalog"

  name_prefix    = local.name_prefix
  silver_db_name = local.silver_db_name
  gold_db_name   = local.gold_db_name
}

############################################
# ETL: Glue job + EventBridge schedule + initial run to init Iceberg table
############################################

module "etl" {
  source = "./modules/etl"

  name_prefix         = local.name_prefix
  region              = var.region
  landing_bucket_name = module.storage.landing_bucket_name
  landing_bucket_arn  = module.storage.landing_bucket_arn
  silver_bucket_name  = module.storage.silver_bucket_name
  silver_bucket_arn   = module.storage.silver_bucket_arn
  silver_db_name      = module.catalog.silver_db_name
  silver_table_name   = local.silver_table_name
  glue_cadence_cron   = var.glue_cadence_cron
  watermark_hours     = var.watermark_hours

  depends_on = [module.catalog]
}

############################################
# Query: Athena workgroup + Gold views (requires initialized Iceberg table)
############################################

module "query" {
  source = "./modules/query"

  name_prefix                = local.name_prefix
  region                     = var.region
  athena_results_bucket_name = module.storage.athena_results_bucket_name
  silver_db_name             = module.catalog.silver_db_name
  silver_table_name          = local.silver_table_name
  gold_db_name               = module.catalog.gold_db_name
  bytes_scanned_cutoff       = var.athena_bytes_scanned_cutoff
  glue_job_name              = module.etl.glue_job_name

  depends_on = [module.etl]
}

############################################
# Observability: Budgets + SNS email alerts
############################################

module "observability" {
  source = "./modules/observability"

  name_prefix      = local.name_prefix
  project_name     = var.project_name
  budget_limit_usd = var.budget_limit_usd
  alert_email      = var.alert_email
}
