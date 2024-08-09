variable "pds_node_names" {
  description = "List of PDS Node Names"
  type        = list(string)
  sensitive   = true
}

variable "pds_nucleus_hot_archive_name_postfix" {
  description = "The postfix of the name of the hot archive"
  default     = "hot-archive-<venue-name>"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_cold_archive_name_postfix" {
  description = "The postfix of the name of the cold archive"
  default     = "cold-archive-<venue-name>"
  type        = string
  sensitive   = true
}






