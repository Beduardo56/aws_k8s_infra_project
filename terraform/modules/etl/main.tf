############################################
# Upload PySpark script to the landing bucket
############################################

resource "aws_s3_object" "glue_script" {
  bucket      = var.landing_bucket_name
  key         = "scripts/bronze_to_silver.py"
  source      = "${path.module}/scripts/bronze_to_silver.py"
  source_hash = filemd5("${path.module}/scripts/bronze_to_silver.py")
}

############################################
# IAM role assumed by the Glue job
############################################

data "aws_iam_policy_document" "glue_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["glue.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "glue_job" {
  name               = "${var.name_prefix}-glue-job-role"
  assume_role_policy = data.aws_iam_policy_document.glue_assume_role.json
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_job.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

data "aws_iam_policy_document" "glue_data_access" {
  statement {
    sid    = "ReadBronze"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      var.landing_bucket_arn,
      "${var.landing_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "WriteTmpAndScripts"
    effect = "Allow"
    actions = [
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
    ]
    resources = [
      "${var.landing_bucket_arn}/tmp/*",
      "${var.landing_bucket_arn}/scripts/*",
    ]
  }

  statement {
    sid    = "ReadWriteSilver"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:AbortMultipartUpload",
    ]
    resources = [
      var.silver_bucket_arn,
      "${var.silver_bucket_arn}/*",
    ]
  }

  statement {
    sid    = "GlueCatalogSilver"
    effect = "Allow"
    actions = [
      "glue:GetDatabase",
      "glue:GetDatabases",
      "glue:GetTable",
      "glue:GetTables",
      "glue:GetPartition",
      "glue:GetPartitions",
      "glue:CreateTable",
      "glue:UpdateTable",
      "glue:DeleteTable",
      "glue:BatchCreatePartition",
      "glue:BatchDeletePartition",
      "glue:BatchGetPartition",
      "glue:BatchUpdatePartition",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "glue_data_access" {
  name   = "${var.name_prefix}-glue-data-access"
  role   = aws_iam_role.glue_job.id
  policy = data.aws_iam_policy_document.glue_data_access.json
}

############################################
# Glue job
############################################

resource "aws_glue_job" "bronze_to_silver" {
  name              = "${var.name_prefix}-bronze-to-silver"
  role_arn          = aws_iam_role.glue_job.arn
  glue_version      = "5.0"
  worker_type       = "G.1X"
  number_of_workers = 2
  timeout           = 5

  execution_property {
    max_concurrent_runs = 1
  }

  command {
    script_location = "s3://${var.landing_bucket_name}/${aws_s3_object.glue_script.key}"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--datalake-formats"                 = "iceberg"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-job-insights"              = "true"
    "--TempDir"                          = "s3://${var.landing_bucket_name}/tmp/"
    "--bronze_path"                      = "s3://${var.landing_bucket_name}/instantaneous/"
    "--silver_table"                     = "glue_catalog.${var.silver_db_name}.${var.silver_table_name}"
    "--silver_warehouse_location"        = "s3://${var.silver_bucket_name}/instantaneous/"
    "--watermark_hours"                  = tostring(var.watermark_hours)
    "--conf" = join(
      " --conf ",
      [
        "spark.sql.catalog.glue_catalog=org.apache.iceberg.spark.SparkCatalog",
        "spark.sql.catalog.glue_catalog.warehouse=s3://${var.silver_bucket_name}/",
        "spark.sql.catalog.glue_catalog.catalog-impl=org.apache.iceberg.aws.glue.GlueCatalog",
        "spark.sql.catalog.glue_catalog.io-impl=org.apache.iceberg.aws.s3.S3FileIO",
        "spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
      ]
    )
  }
}

############################################
# Destroy-time hook: drop the Iceberg table before Glue DB destroy
#
# The Iceberg table is created by the Glue job (first run), not by Terraform,
# so Terraform does not know about it. Without this cleanup, destroying the
# Glue database would fail because it still contains the table.
############################################

resource "null_resource" "drop_silver_table_on_destroy" {
  triggers = {
    region     = var.region
    db_name    = var.silver_db_name
    table_name = var.silver_table_name
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      aws glue delete-table \
        --region ${self.triggers.region} \
        --database-name ${self.triggers.db_name} \
        --name ${self.triggers.table_name} \
        2>/dev/null || true
    EOT
  }

  depends_on = [aws_glue_job.bronze_to_silver]
}

############################################
# EventBridge Scheduler -> Glue job
#
# Classic EventBridge Rules cannot target Glue jobs directly (the API
# rejects the Glue job ARN). EventBridge Scheduler (aws_scheduler_schedule)
# has first-class Glue integration and is the modern replacement.
############################################

data "aws_iam_policy_document" "scheduler_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler" {
  name               = "${var.name_prefix}-scheduler-role"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume_role.json
}

data "aws_iam_policy_document" "scheduler_start_job" {
  statement {
    effect    = "Allow"
    actions   = ["glue:StartJobRun"]
    resources = [aws_glue_job.bronze_to_silver.arn]
  }
}

resource "aws_iam_role_policy" "scheduler_start_job" {
  name   = "${var.name_prefix}-scheduler-start-job"
  role   = aws_iam_role.scheduler.id
  policy = data.aws_iam_policy_document.scheduler_start_job.json
}

resource "aws_scheduler_schedule" "glue_bronze_to_silver" {
  name        = "${var.name_prefix}-bronze-to-silver"
  description = "Trigger Bronze->Silver Glue job on schedule"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = var.glue_cadence_cron
  schedule_expression_timezone = "UTC"

  target {
    arn      = "arn:aws:scheduler:::aws-sdk:glue:startJobRun"
    role_arn = aws_iam_role.scheduler.arn
    input = jsonencode({
      JobName = aws_glue_job.bronze_to_silver.name
    })

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 0
    }
  }
}

############################################
# Initial job run: creates the Iceberg table so downstream modules
# (Athena views) have something to reference. Re-runs whenever the
# Spark script changes.
############################################

resource "null_resource" "initial_run" {
  triggers = {
    script_hash = filemd5("${path.module}/scripts/bronze_to_silver.py")
    job_name    = aws_glue_job.bronze_to_silver.name
    region      = var.region
  }

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      set -euo pipefail
      RUN_ID=$(aws glue start-job-run \
        --region ${var.region} \
        --job-name ${aws_glue_job.bronze_to_silver.name} \
        --query 'JobRunId' --output text)
      echo "Started Glue job run: $RUN_ID"

      # Wait up to 6 minutes for the run to reach a terminal state.
      for _ in $(seq 1 72); do
        STATE=$(aws glue get-job-run \
          --region ${var.region} \
          --job-name ${aws_glue_job.bronze_to_silver.name} \
          --run-id "$RUN_ID" \
          --query 'JobRun.JobRunState' --output text)
        echo "  state=$STATE"
        case "$STATE" in
          SUCCEEDED) exit 0 ;;
          FAILED|STOPPED|TIMEOUT|ERROR) exit 1 ;;
        esac
        sleep 5
      done
      echo "Timed out waiting for initial Glue run" >&2
      exit 1
    EOT
  }

  depends_on = [
    aws_glue_job.bronze_to_silver,
    aws_iam_role_policy.glue_data_access,
    aws_iam_role_policy_attachment.glue_service,
  ]
}
