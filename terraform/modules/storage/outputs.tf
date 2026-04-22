output "landing_bucket_name" {
  value = aws_s3_bucket.landing.id
}

output "landing_bucket_arn" {
  value = aws_s3_bucket.landing.arn
}

output "silver_bucket_name" {
  value = aws_s3_bucket.silver.id
}

output "silver_bucket_arn" {
  value = aws_s3_bucket.silver.arn
}

output "athena_results_bucket_name" {
  value = aws_s3_bucket.athena_results.id
}

output "athena_results_bucket_arn" {
  value = aws_s3_bucket.athena_results.arn
}
