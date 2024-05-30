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

variable "database_availability_zones" {
  description = "Comma Separated List of Availability Zones for Database"
  type        = list(string)
  sensitive   = true
}

variable "permission_boundary_for_iam_roles" {
  description = "Permission boundary to be used when creating IAM roles"
  type      = string
  sensitive = true
}

variable "mwaa_dag_s3_bucket_name" {
  description = "The name of the S3 bucket containing MWAA DAG files"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_staging_bucket_name_postfix" {
  description = "The postfix of the name of the S3 staging bucket to receive data to be processed"
  default     = "staging-<venue-name>"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_config_bucket_name" {
  description = "PDS Nucleus Configuration S3 Bucket Name"
  default     = "pds-nucleus-config-<venue-name>"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_default_airflow_dag_id" {
  description = "PDS Nucleus Default Airflow DAG ID"
  type        = string
  sensitive   = true
}

variable "pds_node_names" {
  description = "List of PDS Node Names"
  type        = list(string)
  default     = ["pds-sbn", "pds-img"]
}

variable "pds_nucleus_opensearch_auth_config_file_paths" {
  description = "List of PDS Nucleus OpenSearch Config file paths"
  type        = list(string)
  default     = ["/mnt/data/configs/pds-sbn-es-auth.cfg", "/mnt/data/configs/pds-img-es-auth.cfg"]
  sensitive   = true
}

variable "pds_nucleus_opensearch_urls" {
  description = "List of PDS Nucleus OpenSearch Config file paths"
  type        =  list(string)
  default     = ["https://search-sbnpsi-abcde.us-west-2.es.amazonaws.com:443","https://search-img-abcde.us-west-2.es.amazonaws.com:443"]
  sensitive   = true
}

variable "pds_nucleus_harvest_replace_prefix_with_list" {
  description = "List of PDS Nucleus Harvest Replace Prefix With"
  type        =  list(string)
  default     = ["s3://pds-nucleus-staging-sbn","s3://pds-nucleus-staging-img"]
}

# ---------------------------------------------
# Default values that are unchanged usually
# ---------------------------------------------
variable "airflow_env_name" {
  description = "PDS Nucleus Airflow Env Name"
  default     = "pds-nucleus-airflow-env"
  type        = string
}

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
