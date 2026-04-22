variable "name_prefix" {
  description = "Prefix used when naming all buckets."
  type        = string
}

variable "bronze_retention_days" {
  description = "Days to keep raw Bronze objects before auto-delete."
  type        = number
  default     = 7
}

variable "athena_results_retention_days" {
  description = "Days to keep Athena query results before auto-delete."
  type        = number
  default     = 3
}
