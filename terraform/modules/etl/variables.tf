variable "name_prefix" {
  description = "Prefix for Glue job, EventBridge rule, and IAM role names."
  type        = string
}

variable "region" {
  description = "AWS region (used by destroy-time provisioner to target glue endpoint)."
  type        = string
}

variable "landing_bucket_name" {
  description = "Name of the Bronze landing bucket (read source + script store + tmp dir)."
  type        = string
}

variable "landing_bucket_arn" {
  description = "ARN of the Bronze landing bucket."
  type        = string
}

variable "silver_bucket_name" {
  description = "Name of the Silver bucket (Iceberg warehouse)."
  type        = string
}

variable "silver_bucket_arn" {
  description = "ARN of the Silver bucket."
  type        = string
}

variable "silver_db_name" {
  description = "Glue Catalog database name for Silver."
  type        = string
}

variable "silver_table_name" {
  description = "Iceberg table name within silver_db."
  type        = string
}

variable "glue_cadence_cron" {
  description = "EventBridge cron (UTC) for scheduled Glue job runs."
  type        = string
}

variable "watermark_hours" {
  description = "How many recent hours of Bronze each run re-scans."
  type        = number
  default     = 6
}
