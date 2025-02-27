variable "nucleus_security_group_name" {
  description = "The name of the PDS Nucleus security group"
  default     = "pds_nucleus_security_group"
  type        = string
  sensitive   = true
}

variable "nucleus_auth_alb_security_group_name" {
  description = "The name of the PDS Nucleus authentication ALB security group"
  default     = "pds_nucleus_cognito_auth_alb_security_group"
  type        = string
  sensitive   = true
}

variable "auth_alb_listener_port" {
  description = "Auth ALB Listener Port"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
  sensitive   = true
}
