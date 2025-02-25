variable "permission_boundary_for_iam_roles" {
  type      = string
  sensitive = true
}

variable "pds_nucleus_auth_alb_function_name" {
  type      = string
  sensitive = true
}

variable "aws_secretmanager_key_arn" {
  description = "The ARN of aws/secretsmanager key"
  type        = string
  sensitive   = true
}
