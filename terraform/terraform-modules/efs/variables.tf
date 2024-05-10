variable "subnet_ids" {
  description = "Subnet IDs"
  type        = list(string)
  sensitive   = true
}

variable "nucleus_security_group_id" {
  description = "PDS Nucleus Security Group ID"
  type        = string
  sensitive   = true
}
