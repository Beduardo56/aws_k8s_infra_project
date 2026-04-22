variable "name_prefix" {
  description = "Prefix used in database descriptions and any catalog-scoped resources."
  type        = string
}

variable "silver_db_name" {
  description = "Glue Catalog database name for the Silver layer."
  type        = string
}

variable "gold_db_name" {
  description = "Glue Catalog database name for the Gold layer (Athena views)."
  type        = string
}
