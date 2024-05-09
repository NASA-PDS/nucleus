variable "permission_boundary_for_iam_role" {
  default   = "mcp-tenantOperator-APIG"
  type      = string
  sensitive = true
}

variable "database_name" {
  default   = "pds_nucleus"
  type      = string
  sensitive = true
}

variable "database_port" {
  default   = "3306"
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
  # default     = "<PDS Nucleus Security Group ID>"
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
  default     = "vpc-0f6bd07eb690a5c3b"
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
  default     = "/mnt/data/configs/es-auth.cfg"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_opensearch_url" {
  description = "PDS Nucleus OpenSearch URL"
  default     = "https://search-sbnpsi-prod-egowc5td43xn744siksghckq4i.us-west-2.es.amazonaws.com:443"
  type        = string
  sensitive   = true
}

variable "pds_node_name" {
  description = "PDS Node Name"
  default     = "PDS_IMG"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_config_bucket_name" {
  description = "PDS Nucleus Configuration S3 Bucket Name"
  default     = "pds-nucleus-config"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_harvest_replace_prefix_with" {
  description = "PDS Nucleus Harvest Replace Prefix With"
  default     = "s3://pds-nucleus-staging"
  type        = string
  sensitive   = true
}

variable "subnet_ids" {
  description = "Comma Separated List of Subnet IDs"
  type        = list(string)
  sensitive   = true
}
