variable "permission_boundary_for_iam_roles" {
  type      = string
  sensitive = true
}

variable "rds_cluster_id" {
  default   = "pdsnucleus"
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
  default   = "pds_nucleus_user"
  type      = string
  sensitive = true
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

variable "pds_nucleus_config_bucket_name" {
  description = "PDS Nucleus Configuration S3 Bucket Name"
  type        = string
  sensitive   = true
}

variable "subnet_ids" {
  description = "Comma Separated List of Subnet IDs"
  type        = list(string)
  sensitive   = true
}

variable "database_availability_zones" {
  description = "Comma Separated List of Availability Zones for Database"
  type        = list(string)
  sensitive   = true
}

variable "pds_node_names" {
  description = "List of PDS Node Names"
  type        = list(string)
  sensitive   = true
}

variable "pds_nucleus_opensearch_url" {
  description = "List of PDS Nucleus OpenSearch URL"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_opensearch_registry_names" {
  description = "List of PDS Nucleus OpenSearch Registry Names"
  type        = list(string)
  sensitive   = true
}

variable "pds_nucleus_opensearch_credential_relative_url" {
  description = "List of PDS Nucleus OpenSearch Credential Relative URL"
  type        =  string
  sensitive   = true
}

variable "pds_nucleus_harvest_replace_prefix_with_list" {
  description = "List of PDS Nucleus Harvest Replace Prefix With"
  type        =  list(string)
}

variable "pds_nucleus_staging_bucket_name_postfix" {
  description = "The postfix of the name of the S3 staging bucket to receive data to be processed"
  default     = "staging-<venue-name>"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_hot_archive_bucket_name_postfix" {
  description = "The postfix of the name of the hot archive s3 bucket"
  default     = "hot-archive-<venue-name>"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_cold_archive_bucket_name_postfix" {
  description = "The postfix of the name of the cold archive s3 bucket"
  default     = "cold-archive-<venue-name>"
  type        = string
  sensitive   = true
}

variable "airflow_env_name" {
  description = "PDS Nucleus Airflow Env Name"
  default     = "pds-nucleus-airflow-env"
  type        = string
}

variable "product_batch_size" {
  description = "Size of the product batch to send to Nuclees DAG top process per given DAG invocation"
  default     = 10
  type        = number
}

variable "region" {
  description = "AWS Region"
  type        = string
}
