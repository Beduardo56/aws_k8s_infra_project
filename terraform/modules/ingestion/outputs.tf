output "firehose_stream_name" {
  value = aws_kinesis_firehose_delivery_stream.instant.name
}

output "firehose_stream_arn" {
  value = aws_kinesis_firehose_delivery_stream.instant.arn
}

output "producer_access_key_id" {
  value     = aws_iam_access_key.producer.id
  sensitive = true
}

output "producer_secret_access_key" {
  value     = aws_iam_access_key.producer.secret
  sensitive = true
}

output "producer_iam_user_name" {
  value = aws_iam_user.producer.name
}
