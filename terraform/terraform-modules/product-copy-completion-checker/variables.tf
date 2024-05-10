variable "permission_boundary_for_iam_roles" {
  type      = string
  sensitive = true
}

variable "database_name" {
  default   = "pds_nucleus"
  type      = string
  sensitive = true
}

variable "database_port" {
  type      = string
  sensitive = true
}

variable "database_user" {
  default   = "admin"
  type      = string
  sensitive = true
}

variable "pds_nucleus_staging_bucket_name" {
  description = "The name of the S3 staging bucket to receive data to be processed"
  type        = string
  sensitive   = true
}

variable "nucleus_security_group_id" {
  description = "PDS Nucleus Security Group ID"
  type        = string
  sensitive   = true
}

variable "database_creds_secret" {
  description = "PDS Nucleus database secret name in secret manager"
  default     = "pds/nucleus/database/creds"
  type        = string
  sensitive   = true
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_default_airflow_dag_id" {
  description = "PDS Nucleus Default Airflow DAG ID"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_opensearch_auth_config_file_path" {
  description = "PDS Nucleus Default Airflow DAG ID"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_opensearch_url" {
  description = "PDS Nucleus OpenSearch URL"
  type        = string
  sensitive   = true
}

variable "pds_node_name" {
  description = "PDS Node Name"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_config_bucket_name" {
  description = "PDS Nucleus Configuration S3 Bucket Name"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_harvest_replace_prefix_with" {
  description = "PDS Nucleus Harvest Replace Prefix With"
  type        = string
  sensitive   = true
}

variable "subnet_ids" {
  description = "Comma Separated List of Subnet IDs"
  type        = list(string)
  sensitive   = true
}
