output "silver_db_name" {
  value = aws_glue_catalog_database.silver.name
}

output "gold_db_name" {
  value = aws_glue_catalog_database.gold.name
}
