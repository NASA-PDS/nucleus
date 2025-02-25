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

variable "pds_nucleus_auth_alb_function_name" {
  description = "PDS Nucleus Auth ALB Function name"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_alb_auth_lambda_execution_role_arn" {
  description = "PDS Nucleus ALB Auth Lambda Execution Role ARN"
  type = string
  sensitive = true
}

variable "pds_nucleus_admin_role_arn" {
  description = "PDS Nucleus Airflow Admin Role ARN"
  type = string
  sensitive = true
}

variable "pds_nucleus_op_role_arn" {
  description = "PDS Nucleus Airflow Op Role ARN"
  type = string
  sensitive = true
}

variable "pds_nucleus_user_role_arn" {
  description = "PDS Nucleus Airflow User Role ARN"
  type = string
  sensitive = true
}

variable "pds_nucleus_viewer_role_arn" {
  description = "PDS Nucleus Airflow Viewer Role ARN"
  type = string
  sensitive = true
}