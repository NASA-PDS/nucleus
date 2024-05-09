variable "env" {
  type        = string
  description = "Environment"
  default     = "dev"
}

variable "region" {
  type        = string
  description = "Region"
  default     = "us-west-2"
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
  sensitive   = true
}

variable "vpc_cidr" {
  description = "VPC CIDR for MWAA"
  type        = string
  sensitive   = true
}

variable "subnet_ids" {
  description = "Subnet IDs"
  type        = list(string)
  sensitive   = true
}

variable "mwaa_dag_s3_bucket_name" {
  type        = string
  description = "The name of the S3 bucket containing MWAA DAG files"
  sensitive   = true
}

variable "pds_nucleus_staging_bucket_name" {
  type        = string
  description = "The name of the S3 staging bucket to receive data to be processed"
  sensitive   = true
}

variable "pds_nucleus_config_bucket_name" {
  description = "PDS Nucleus Configuration S3 Bucket Name"
  default     = "pds-nucleus-config-test"
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

variable "pds_nucleus_harvest_replace_prefix_with" {
  description = "PDS Nucleus Harvest Replace Prefix With"
  default     = "s3://pds-nucleus-staging"
  type        = string
  sensitive   = true
}

# ---------------------------------------------
# Default values that are unchanged usually
# ---------------------------------------------

variable "pds_nucleus_ecs_cluster_name" {
  type        = string
  description = "The name of the PDS Nucleus ECS cluster"
  default     = "pds-nucleus-ecs"
}

variable "pds_registry_loader_harvest_cloudwatch_logs_group" {
  type        = string
  description = "PDS Registry Loader Harvest Cloudwatch Logs Group"
  default     = "/pds/ecs/harvest"
}

variable "pds_validate_cloudwatch_logs_group" {
  type        = string
  description = "PDS Validate Cloudwatch Logs Group"
  default     = "/pds/ecs/validate"
}

variable "pds_validate_ref_cloudwatch_logs_group" {
  type        = string
  description = "PDS Validate Ref Cloudwatch Logs Group"
  default     = "/pds/ecs/validate-ref"
}

variable "pds_nucleus_config_init_cloudwatch_logs_group" {
  type        = string
  description = "PDS Nucleus Config Init CloudWatch Logs Group"
  default     = "/pds/ecs/pds-nucleus-config-init"
}

variable "pds_nucleus_s3_to_efs_copy_cloudwatch_logs_group" {
  type        = string
  description = "PDS Nucleus S3 to EFS CopyCloudWatch Logs Group"
  default     = "/pds/ecs/pds-nucleus-s3-to-efs-copy"
}

variable "database_port" {
  type        = string
  description = "PDS Database Port"
  default     = "3306"
}
