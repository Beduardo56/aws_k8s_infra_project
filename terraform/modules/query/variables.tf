variable "name_prefix" {
  description = "Prefix for the Athena workgroup."
  type        = string
}

variable "region" {
  description = "AWS region (passed to destroy-time provisioners)."
  type        = string
}

variable "athena_results_bucket_name" {
  description = "Bucket where Athena query results are written."
  type        = string
}

variable "silver_db_name" {
  description = "Glue Catalog database holding the Silver Iceberg table."
  type        = string
}

variable "silver_table_name" {
  description = "Silver Iceberg table name."
  type        = string
}

variable "gold_db_name" {
  description = "Glue Catalog database that will hold the Gold views."
  type        = string
}

variable "bytes_scanned_cutoff" {
  description = "Workgroup per-query scan limit (bytes)."
  type        = number
}

variable "glue_job_name" {
  description = "Name of the Glue job - used to order view creation after the first successful run (not a hard dep; views can be created on an empty table)."
  type        = string
  default     = ""
}
