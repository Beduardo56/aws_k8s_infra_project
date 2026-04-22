output "glue_job_name" {
  value = aws_glue_job.bronze_to_silver.name
}

output "glue_job_arn" {
  value = aws_glue_job.bronze_to_silver.arn
}

output "glue_role_arn" {
  value = aws_iam_role.glue_job.arn
}

output "schedule_name" {
  value = aws_scheduler_schedule.glue_bronze_to_silver.name
}

output "initial_run_id" {
  description = "Synthetic output used by downstream modules (query) to depend on the initial Glue run."
  value       = null_resource.initial_run.id
}
