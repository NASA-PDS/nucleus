variable "pds_node_names" {
  description = "List of PDS Node Names"
  type        = list(string)
  sensitive   = true
}

variable "pds_nucleus_archive_hot_bucket_name_postfix" {
  description = "The postfix of the name of the S3 archive hot bucket to receive data to be processed"
  default     = "archive-hot-<venue-name>"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_archive_cold_bucket_name_postfix" {
  description = "The postfix of the name of the S3 archive cold bucket to receive data to be processed"
  default     = "archive-cold-<venue-name>"
  type        = string
  sensitive   = true
}






