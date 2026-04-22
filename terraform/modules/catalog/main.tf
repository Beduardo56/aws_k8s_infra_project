resource "aws_glue_catalog_database" "silver" {
  name        = var.silver_db_name
  description = "${var.name_prefix} Silver layer - Iceberg tables curated from Bronze"
}

resource "aws_glue_catalog_database" "gold" {
  name        = var.gold_db_name
  description = "${var.name_prefix} Gold layer - Athena views on top of Silver"
}
