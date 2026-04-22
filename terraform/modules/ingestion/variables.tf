variable "name_prefix" {
  description = "Prefix used when naming Firehose stream and IAM resources."
  type        = string
}

variable "landing_bucket_arn" {
  description = "ARN of the Bronze landing bucket that Firehose delivers into."
  type        = string
}

variable "buffer_size_mb" {
  description = "Firehose size buffer (MB). Firehose flushes when size OR interval threshold is reached."
  type        = number
  default     = 128
}

variable "buffer_interval_seconds" {
  description = "Firehose time buffer (seconds). Max 900."
  type        = number
  default     = 300
}
