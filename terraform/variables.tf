variable "project_name" {
  description = "Prefix for all resource names and primary tag value"
  type        = string
  default     = "te-lake"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.project_name))
    error_message = "project_name must be 3-21 chars, lowercase alphanumeric + dashes, starting with a letter."
  }
}

variable "region" {
  description = "AWS region for all regional resources"
  type        = string
  default     = "us-east-1"
}

variable "budget_limit_usd" {
  description = "Monthly AWS budget ceiling in USD. Alerts fire at 50/80/100% of this value."
  type        = number
  default     = 10

  validation {
    condition     = var.budget_limit_usd > 0 && var.budget_limit_usd <= 100
    error_message = "budget_limit_usd must be between 1 and 100 USD (this is a personal-project demo)."
  }
}

variable "alert_email" {
  description = "Email address to subscribe to the budget-alert SNS topic. Must be confirmed after apply."
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "alert_email must be a valid email address."
  }
}

variable "glue_cadence_cron" {
  description = "EventBridge cron expression (UTC) for the Bronze->Silver Glue job."
  type        = string
  default     = "cron(0 */3 * * ? *)"
}

variable "firehose_buffer_size_mb" {
  description = "Firehose size buffer in MB (ignored at low volume; time buffer fires first)."
  type        = number
  default     = 128
}

variable "firehose_buffer_seconds" {
  description = "Firehose time buffer in seconds (max 900)."
  type        = number
  default     = 300
}

variable "athena_bytes_scanned_cutoff" {
  description = "Workgroup per-query scan limit in bytes (cost guardrail). Default 1 GiB."
  type        = number
  default     = 1073741824
}

variable "watermark_hours" {
  description = "How many recent hours of Bronze the Glue job re-scans every run."
  type        = number
  default     = 6
}

variable "bronze_retention_days" {
  description = "S3 lifecycle: days to keep raw Bronze objects before deletion."
  type        = number
  default     = 7
}

variable "athena_results_retention_days" {
  description = "S3 lifecycle: days to keep Athena query results before deletion."
  type        = number
  default     = 3
}
