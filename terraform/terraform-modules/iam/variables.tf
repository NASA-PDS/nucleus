variable "permission_boundary_for_iam_roles" {
  type      = string
  sensitive = true
}

variable "permission_boundary_for_iam_roles_arn" {
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

variable "airflow_env_name" {
  description = "PDS Nucleus Airflow Env Name"
  type        = string
}

variable "rds_cluster_id" {
  type      = string
  sensitive = true
}

variable "region" {
  description = "Region"
  type        = string
}

variable "mwaa_dag_s3_bucket_name" {
  description = "The name of the S3 bucket containing MWAA DAG files"
  type        = string
  sensitive   = true
}

variable "pds_node_names" {
  type        = list(string)
  description = "List of PDS Node Names"
}

variable "pds_nucleus_opensearch_collection_arns" {
  type        = list(string)
  description = "List of PDS OpenSearch Collection ARN"
  sensitive   = true
}