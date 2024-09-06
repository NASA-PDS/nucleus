variable "pds_node_names" {
  description = "List of PDS Node Names"
  type        = list(string)
  sensitive   = true
}

variable "pds_nucleus_hot_archive_bucket_name_postfix" {
  description = "The postfix of the name of the hot archive s3 bucket"
  default     = "hot-archive-<venue-name>"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_cold_archive_bucket_name_postfix" {
  description = "The postfix of the name of the cold archive s3 bucket"
  default     = "cold-archive-<venue-name>"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_cold_archive_buckets" {
  description = "The list of the names of the cold archive s3 buckets"
  type        = list
  sensitive   = true
}

variable "pds_nucleus_cold_archive_storage_class" {
  description = "The storage class of the cold archive s3 buckets"
  type        = string
}

variable "permission_boundary_for_iam_roles" {
  description = "Permission boundary for IAM roles"
  type      = string
  sensitive = true
}
