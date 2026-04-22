############################################
# Athena workgroup with scan cap
############################################

resource "aws_athena_workgroup" "analytics" {
  name          = "${var.name_prefix}-analytics-wg"
  force_destroy = true

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true
    bytes_scanned_cutoff_per_query     = var.bytes_scanned_cutoff

    result_configuration {
      output_location = "s3://${var.athena_results_bucket_name}/query-results/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }
}

############################################
# Gold views
#
# Views have a DAG of dependencies:
#   v_hourly_energy          -> Silver           (base)
#   v_daily_device_summary   -> Silver           (base)
#   v_fleet_daily_rollup     -> v_daily_device_summary  (derived)
#
# Terraform's `for_each` would create all three in parallel; the derived view
# would sometimes race ahead of its base and fail. Split into two resources
# with explicit `depends_on` to serialize.
############################################

locals {
  base_views = {
    v_hourly_energy = templatefile("${path.module}/views/v_hourly_energy.sql.tftpl", {
      silver_db    = var.silver_db_name
      silver_table = var.silver_table_name
      gold_db      = var.gold_db_name
    })
    v_daily_device_summary = templatefile("${path.module}/views/v_daily_device_summary.sql.tftpl", {
      silver_db    = var.silver_db_name
      silver_table = var.silver_table_name
      gold_db      = var.gold_db_name
    })
  }

  derived_views = {
    v_fleet_daily_rollup = templatefile("${path.module}/views/v_fleet_daily_rollup.sql.tftpl", {
      gold_db = var.gold_db_name
    })
  }
}

resource "null_resource" "gold_view_base" {
  for_each = local.base_views

  triggers = {
    ddl       = each.value
    workgroup = aws_athena_workgroup.analytics.name
    region    = var.region
    gold_db   = var.gold_db_name
    view_name = each.key
  }

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      set -euo pipefail

      DDL=$(cat <<'__SQL__'
${each.value}
__SQL__
)

      QID=$(aws athena start-query-execution \
        --region ${var.region} \
        --work-group ${aws_athena_workgroup.analytics.name} \
        --query-string "$DDL" \
        --query 'QueryExecutionId' --output text)
      echo "Athena query: $QID ( ${each.key} )"

      for _ in $(seq 1 60); do
        STATE=$(aws athena get-query-execution \
          --region ${var.region} \
          --query-execution-id "$QID" \
          --query 'QueryExecution.Status.State' --output text)
        case "$STATE" in
          SUCCEEDED) exit 0 ;;
          FAILED|CANCELLED)
            REASON=$(aws athena get-query-execution \
              --region ${var.region} \
              --query-execution-id "$QID" \
              --query 'QueryExecution.Status.StateChangeReason' --output text || true)
            echo "Athena query $QID failed: $REASON" >&2
            exit 1
            ;;
        esac
        sleep 2
      done
      echo "Timed out waiting for Athena query $QID" >&2
      exit 1
    EOT
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      aws athena start-query-execution \
        --region ${self.triggers.region} \
        --work-group ${self.triggers.workgroup} \
        --query-string "DROP VIEW IF EXISTS ${self.triggers.gold_db}.${self.triggers.view_name}" \
        2>/dev/null || true
    EOT
  }
}

resource "null_resource" "gold_view_derived" {
  for_each = local.derived_views

  depends_on = [null_resource.gold_view_base]

  triggers = {
    ddl       = each.value
    workgroup = aws_athena_workgroup.analytics.name
    region    = var.region
    gold_db   = var.gold_db_name
    view_name = each.key
  }

  provisioner "local-exec" {
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      set -euo pipefail

      DDL=$(cat <<'__SQL__'
${each.value}
__SQL__
)

      QID=$(aws athena start-query-execution \
        --region ${var.region} \
        --work-group ${aws_athena_workgroup.analytics.name} \
        --query-string "$DDL" \
        --query 'QueryExecutionId' --output text)
      echo "Athena query: $QID ( ${each.key} )"

      for _ in $(seq 1 60); do
        STATE=$(aws athena get-query-execution \
          --region ${var.region} \
          --query-execution-id "$QID" \
          --query 'QueryExecution.Status.State' --output text)
        case "$STATE" in
          SUCCEEDED) exit 0 ;;
          FAILED|CANCELLED)
            REASON=$(aws athena get-query-execution \
              --region ${var.region} \
              --query-execution-id "$QID" \
              --query 'QueryExecution.Status.StateChangeReason' --output text || true)
            echo "Athena query $QID failed: $REASON" >&2
            exit 1
            ;;
        esac
        sleep 2
      done
      echo "Timed out waiting for Athena query $QID" >&2
      exit 1
    EOT
  }

  provisioner "local-exec" {
    when        = destroy
    interpreter = ["bash", "-c"]
    command     = <<-EOT
      aws athena start-query-execution \
        --region ${self.triggers.region} \
        --work-group ${self.triggers.workgroup} \
        --query-string "DROP VIEW IF EXISTS ${self.triggers.gold_db}.${self.triggers.view_name}" \
        2>/dev/null || true
    EOT
  }
}
