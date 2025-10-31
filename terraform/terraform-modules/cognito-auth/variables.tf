variable "venue" {
  description = "Venue"
  type        = string
  default     = "dev"
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

variable "auth_alb_dns_name_ssm_param" {
  description = "SSM parameter to hold the Auth ALB dns name"
  type        = string
  sensitive   = true
}

variable "auth_alb_listener_certificate_arn" {
  description = "Auth ALB Listener Certificate ARN"
  type        = string
  sensitive   = true
}

variable "nucleus_cloudfront_origin_hostname" {
  description = "Hostname of the Nucleus Cloudfront origin (E.g: pds-sit.mcp.nasa.gov)"
  type        = string
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

variable "nucleus_auth_alb_security_group_id" {
  description = "The ID of the PDS Nucleus authentication ALB security group id"
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

variable "region" {
  description = "Region"
  type        = string
}

variable "pds_shared_logs_bucket_name" {
  description = "The name of the PDS shared logs bucket"
  type        = string
  sensitive   = true
}

variable "lambda_runtime" {
  description = "Lambda runtime"
  type        = string
}