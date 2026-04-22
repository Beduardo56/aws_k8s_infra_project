output "firehose_stream_name" {
  description = "Name of the Firehose delivery stream; pass to producer --stream-name"
  value       = module.ingestion.firehose_stream_name
}

output "region" {
  description = "AWS region all resources live in; pass to producer --region"
  value       = var.region
}

output "landing_bucket" {
  value = module.storage.landing_bucket_name
}

output "silver_bucket" {
  value = module.storage.silver_bucket_name
}

output "athena_results_bucket" {
  value = module.storage.athena_results_bucket_name
}

output "athena_workgroup" {
  description = "Athena workgroup for all Gold-layer queries; select in console"
  value       = module.query.workgroup_name
}

output "silver_database" {
  value = module.catalog.silver_db_name
}

output "gold_database" {
  value = module.catalog.gold_db_name
}

output "silver_table" {
  value = "${module.catalog.silver_db_name}.${local.silver_table_name}"
}

output "gold_views" {
  value = module.query.view_names
}

output "glue_job" {
  value = module.etl.glue_job_name
}

output "producer_iam_user" {
  value = module.ingestion.producer_iam_user_name
}

output "producer_access_key_id" {
  description = "Access key ID for the producer IAM user. Configure with: aws configure --profile te-lake-producer"
  value       = module.ingestion.producer_access_key_id
  sensitive   = true
}

output "producer_secret_access_key" {
  description = "Secret access key for the producer IAM user."
  value       = module.ingestion.producer_secret_access_key
  sensitive   = true
}

output "run_producer_command" {
  description = "Copy-paste command to run the local producer for 60 minutes."
  value       = "python producer/producer.py --stream-name ${module.ingestion.firehose_stream_name} --region ${var.region} --devices 10 --duration-min 60 --profile te-lake-producer"
}
