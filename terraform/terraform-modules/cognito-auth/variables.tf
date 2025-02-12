variable "permission_boundary_for_iam_roles" {
  type      = string
  sensitive = true
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
  sensitive   = true
}

variable "nucleus_auth_alb_security_group_name" {
  description = "The name of the PDS Nucleus authentication ALB security group"
  default     = "pds_nucleus_cognito_auth_alb_security_group"
  type        = string
  sensitive   = true
}

variable "auth_alb_subnet_ids" {
  description = "Auth ALB Subnet IDs"
  type        = list(string)
  sensitive   = true
}

variable "cognito_user_pool_id" {
  description = "Cognito user pool ID"
  type        = string
  sensitive   = true
}

variable "cognito_user_pool_domain" {
  description = "Cognito user pool domain"
  type        = string
  sensitive   = true
}

variable "auth_alb_name" {
  description = "Auth ALB Name"
  type        = string
  sensitive   = true
}

variable "auth_alb_listener_port" {
  description = "Auth ALB Listener Port"
  type        = string
}

variable "auth_alb_listener_certificate_arn" {
  description = "Auth ALB Listener Certificate ARN"
  type        = string
  sensitive   = true
}

variable "aws_elb_account_id_for_the_region" {
  description = "Standard AWS ELB Account ID for the related region"
  type        = string
  sensitive   = true
}

variable "airflow_env_name" {
  description = "MWAA Airflow Environment Name"
  type = string
  sensitive = true
}
