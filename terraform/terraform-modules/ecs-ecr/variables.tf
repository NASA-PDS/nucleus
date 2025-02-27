variable "region" {
  type        = string
  description = "Region"
  default     = "us-west-2"
}

variable "efs_file_system_id" {
  type        = string
  description = "EFS File System ID"
  sensitive   = true
}

variable "pds_nucleus_ecs_cluster_name" {
  type        = string
  description = "The name of the PDS Nucleus ECS cluster"
  sensitive   = true
}

variable "pds_data_access_point_id" {
  type        = string
  description = "PDS Data Access Point ID"
  sensitive   = true
}

variable "pds_registry_loader_harvest_cloudwatch_logs_group" {
  type        = string
  description = "PDS Registry Loader Harvest CloudWatch Logs Group"
  default     = "/pds/ecs/harvest"
  sensitive   = true
}

variable "pds_registry_loader_harvest_cloudwatch_logs_region" {
  type        = string
  description = "PDS Registry Loader Harvest CloudWatch Logs Region"
  sensitive   = true
}

variable "pds_registry_loader_harvest_task_role_arn" {
  type        = string
  description = "PDS Registry Loader Harvest Task Role ARN"
  sensitive   = true
}

variable "pds_validate_cloudwatch_logs_group" {
  type        = string
  description = "PDS Validate CloudWatch Logs Group"
  default     = "/pds/ecs/validate"
  sensitive   = true
}

variable "pds_validate_cloudwatch_logs_region" {
  type        = string
  description = "PDS Validate CloudWatch Logs Region"
  sensitive   = true
}

variable "pds_validate_ref_cloudwatch_logs_region" {
  type        = string
  description = "PDS Validate Ref CloudWatch Logs Region"
  sensitive   = true
}

variable "pds_validate_ref_cloudwatch_logs_group" {
  type        = string
  description = "PDS Validate Ref CloudWatch Logs Group"
  default     = "/pds/ecs/validate-ref"
  sensitive   = true
}

variable "pds_nucleus_config_init_cloudwatch_logs_group" {
  type        = string
  description = "PDS Nucleus Config Init CloudWatch Logs Group"
  default     = "/pds/ecs/pds-nucleus-config-init"
  sensitive   = true
}

variable "pds_nucleus_config_init_cloudwatch_logs_region" {
  type        = string
  description = "PDS Nucleus Config Init CloudWatch Logs Region"
  sensitive   = true
}

variable "pds_nucleus_s3_to_efs_copy_cloudwatch_logs_group" {
  type        = string
  description = "PDS Nucleus S3 to EFS CopyCloudWatch Logs Group"
  default     = "/pds/ecs/pds-nucleus-s3-to-efs-copy"
  sensitive   = true
}

variable "permission_boundary_for_iam_roles" {
  type        = string
  description = "Permission boundary to be used to create IAM roles"
  sensitive   = true
}

variable "pds_node_names" {
  type        = list(string)
  description = "List of PDS Node Names"
  sensitive   = true
}

variable "aws_secretmanager_key_arn" {
  type        = string
  description = "The ARN of aws/secretsmanager key"
  sensitive   = true
}

variable "pds_nucleus_ecs_task_role_arn" {
  type        = string
  description = "PDS Nucleus ECS task role ARN"
  sensitive   = true
}

variable "pds_nucleus_ecs_task_execution_role_arn" {
  type        = string
  description = "PDS Nucleus ECS task execution role ARN"
  sensitive   = true
}
