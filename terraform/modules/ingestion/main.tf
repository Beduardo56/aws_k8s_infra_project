############################################
# CloudWatch log group for Firehose delivery errors
############################################

resource "aws_cloudwatch_log_group" "firehose" {
  name              = "/aws/kinesisfirehose/${var.name_prefix}-instant-stream"
  retention_in_days = 7
}

resource "aws_cloudwatch_log_stream" "firehose_s3_delivery" {
  name           = "S3Delivery"
  log_group_name = aws_cloudwatch_log_group.firehose.name
}

############################################
# IAM role assumed by Firehose
############################################

data "aws_iam_policy_document" "firehose_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["firehose.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "firehose" {
  name               = "${var.name_prefix}-firehose-role"
  assume_role_policy = data.aws_iam_policy_document.firehose_assume_role.json
}

data "aws_iam_policy_document" "firehose_s3" {
  statement {
    sid    = "WriteToLandingBucket"
    effect = "Allow"
    actions = [
      "s3:AbortMultipartUpload",
      "s3:GetBucketLocation",
      "s3:GetObject",
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
      "s3:PutObject",
    ]
    resources = [
      var.landing_bucket_arn,
      "${var.landing_bucket_arn}/*",
    ]
  }

  statement {
    sid       = "WriteDeliveryLogs"
    effect    = "Allow"
    actions   = ["logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.firehose.arn}:*"]
  }
}

resource "aws_iam_role_policy" "firehose_s3" {
  name   = "${var.name_prefix}-firehose-delivery"
  role   = aws_iam_role.firehose.id
  policy = data.aws_iam_policy_document.firehose_s3.json
}

############################################
# Kinesis Firehose delivery stream
############################################

resource "aws_kinesis_firehose_delivery_stream" "instant" {
  name        = "${var.name_prefix}-instant-stream"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose.arn
    bucket_arn          = var.landing_bucket_arn
    prefix              = "instantaneous/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/hour=!{timestamp:HH}/"
    error_output_prefix = "errors/!{firehose:error-output-type}/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    compression_format  = "GZIP"

    buffering_size     = var.buffer_size_mb
    buffering_interval = var.buffer_interval_seconds

    cloudwatch_logging_options {
      enabled         = true
      log_group_name  = aws_cloudwatch_log_group.firehose.name
      log_stream_name = aws_cloudwatch_log_stream.firehose_s3_delivery.name
    }
  }

  depends_on = [aws_iam_role_policy.firehose_s3]
}

############################################
# IAM user for the local producer (programmatic access only)
############################################

resource "aws_iam_user" "producer" {
  name = "${var.name_prefix}-producer"
  path = "/service/"
}

resource "aws_iam_access_key" "producer" {
  user = aws_iam_user.producer.name
}

data "aws_iam_policy_document" "producer" {
  statement {
    sid    = "PutRecordsOnTheInstantStream"
    effect = "Allow"
    actions = [
      "firehose:PutRecord",
      "firehose:PutRecordBatch",
      "firehose:DescribeDeliveryStream",
    ]
    resources = [aws_kinesis_firehose_delivery_stream.instant.arn]
  }
}

resource "aws_iam_user_policy" "producer" {
  name   = "${var.name_prefix}-producer-firehose"
  user   = aws_iam_user.producer.name
  policy = data.aws_iam_policy_document.producer.json
}
