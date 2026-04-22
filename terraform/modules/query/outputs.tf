output "workgroup_name" {
  value = aws_athena_workgroup.analytics.name
}

output "workgroup_arn" {
  value = aws_athena_workgroup.analytics.arn
}

output "view_names" {
  value = concat(
    [for k in keys(local.base_views) : k],
    [for k in keys(local.derived_views) : k],
  )
}
