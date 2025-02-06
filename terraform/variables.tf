variable "env" {
  description = "Environment"
  type        = string
  default     = "dev"
}

variable "region" {
  description = "Region"
  type        = string
  default     = "us-west-2"
}

variable "region_secondary" {
  description = "Secondary Region for Archive"
  type        = string
  default     = "us-east-2"
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

variable "auth_alb_subnet_ids" {
  description = "Auth ALB Subnet IDs"
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
  type        = string
  sensitive   = true
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

variable "pds_nucleus_cold_archive_storage_class" {
  description = "The storage class of the cold archive s3 buckets"
  default     = "DEEP_ARCHIVE"
  type        = string
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

variable "pds_nucleus_opensearch_urls" {
  description = "List of PDS Nucleus OpenSearch Config file paths"
  type        = list(string)
  sensitive   = true
}

variable "pds_nucleus_opensearch_credential_relative_url" {
  description = "List of PDS Nucleus OpenSearch Credential Relative URL"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_harvest_replace_prefix_with_list" {
  description = "List of PDS Nucleus Harvest Replace Prefix With"
  type        = list(string)
  default     = ["s3://pds-nucleus-staging-sbn", "s3://pds-nucleus-staging-img"]
}

variable "pds_registry_loader_harvest_task_role_arn" {
  type        = string
  description = "PDS Registry Loader Harvest Task Role ARN"
  sensitive   = true
}

variable "aws_secretmanager_key_arn" {
  description = "The ARN of aws/secretsmanager key"
  type        = string
  sensitive   = true
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
  description = "The name of the PDS Nucleus ECS cluster"
  type        = string
  default     = "pds-nucleus-ecs"
}

variable "pds_registry_loader_harvest_cloudwatch_logs_group" {
  description = "PDS Registry Loader Harvest Cloudwatch Logs Group"
  type        = string
  default     = "/pds/ecs/harvest"
}

variable "pds_validate_cloudwatch_logs_group" {
  description = "PDS Validate Cloudwatch Logs Group"
  type        = string
  default     = "/pds/ecs/validate"
}

variable "pds_validate_ref_cloudwatch_logs_group" {
  description = "PDS Validate Ref Cloudwatch Logs Group"
  type        = string
  default     = "/pds/ecs/validate-ref"
}

variable "pds_nucleus_config_init_cloudwatch_logs_group" {
  description = "PDS Nucleus Config Init CloudWatch Logs Group"
  type        = string
  default     = "/pds/ecs/pds-nucleus-config-init"
}

variable "pds_nucleus_s3_to_efs_copy_cloudwatch_logs_group" {
  description = "PDS Nucleus S3 to EFS CopyCloudWatch Logs Group"
  type        = string
  default     = "/pds/ecs/pds-nucleus-s3-to-efs-copy"
}

variable "database_port" {
  description = "PDS Database Port"
  type        = string
  default     = "3306"
}

variable "cognito_user_pool_id" {
  description = "Cognito user pool ID"
  type        = string
  sensitive   = true
}

variable "cognito_user_pool_domain" {
  description = "Cognito user pool domain"
  type        = string
  default     = "pds-registry"
  sensitive   = true
}

variable "auth_alb_name" {
  description = "Auth ALB Name"
  default     = "pds-nucleus"
  type        = string
  sensitive   = true
}

variable "auth_alb_listener_port" {
  description = "Auth ALB Listener Port"
  default     = "4443"
  type        = string
  sensitive   = true
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