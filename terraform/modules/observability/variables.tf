variable "name_prefix" {
  description = "Prefix for budget, SNS topic, and subscription names."
  type        = string
}

variable "project_name" {
  description = "Value of the Project tag used as the budget cost-filter."
  type        = string
}

variable "budget_limit_usd" {
  description = "Monthly budget ceiling in USD."
  type        = number
}

variable "alert_email" {
  description = "Email subscribed to the SNS budget-alert topic."
  type        = string
}
