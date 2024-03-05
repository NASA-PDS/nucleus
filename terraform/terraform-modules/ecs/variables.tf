variable "efs_file_system_id" {
  type        = string
  description = "EFS File System ID"
  # default     = "<EFS File System ID>"
  sensitive = true
}

#variable "registry_loader_scripts_access_point_id" {
#  type        = string
#  description = "Registry Loader Scripts EFS Access Point ID"
#  # default     = "<Registry Loader Scripts EFS Access Point ID>"
#  sensitive = true
#}
#
#variable "registry_loader_default_configs_access_point_id" {
#  type        = string
#  description = "Registry Loader Default Configs EFS Access Point ID"
#  # default     = "<Registry Loader Default Configs EFS Access Point ID>"
#  sensitive = true
#}

variable "pds_data_access_point_id" {
  type        = string
  description = "PDS Data Access Point ID"
  # default     = "<PDS Data Access Point ID>"
  sensitive = true
}

variable "pds_registry_loader_harvest_ecr_image_path" {
  type        = string
  description = "PDS Registry Loader Harvest ECR Image Path"
  # default     = "<PDS Registry Loader Harvest ECR Image Path>"
  sensitive = true
}

variable "pds_registry_loader_harvest_cloudwatch_logs_group" {
  type        = string
  description = "PDS Registry Loader Harvest CloudWatch Logs Group"
  # default     = "<PDS Registry Loader Harvest CloudWatch Logs Group>"
  sensitive = true
}

variable "pds_registry_loader_harvest_cloudwatch_logs_region" {
  type        = string
  description = "PDS Validate CloudWatch Logs Region"
  # default     = "<PDS Registry Loader Harvest CloudWatch Logs Region>"
  sensitive = true
}
#
#variable "pds_registry_loader_harvest_data_access_point_id" {
#  type        = string
#  description = "PDS Validate EFS Access Point ID"
#  # default     = "<PDS Registry Loader Harvest EFS Access Access Point ID>"
#  sensitive = true
#}

variable "pds_validate_ecr_image_path" {
  type        = string
  description = "PDS Validate ECR Image Path"
  # default     = "<PDS Validate ECR Image Path>"
  sensitive = true
}

variable "pds_validate_cloudwatch_logs_group" {
  type        = string
  description = "PDS Validate CloudWatch Logs Group"
  # default     = "<PDS Validate CloudWatch Logs Group>"
  sensitive = true
}

variable "pds_validate_cloudwatch_logs_region" {
  type        = string
  description = "PDS Validate CloudWatch Logs Region"
  # default     = "<PDS Validate CloudWatch Logs Region>"
  sensitive = true
}

variable "pds_validate_ref_cloudwatch_logs_region" {
  type        = string
  description = "PDS Validate Ref CloudWatch Logs Region"
  # default     = "<PDS Validate Ref CloudWatch Logs Region>"
  sensitive = true
}

variable "pds_validate_ref_cloudwatch_logs_group" {
  type        = string
  description = "PDS Validate Ref CloudWatch Logs Group"
  # default     = "<PDS Validate Ref CloudWatch Logs Group>"
  sensitive = true
}

#variable "pds_validate_data_access_point_id" {
#  type        = string
#  description = "PDS Validate EFS Access Point ID"
#  # default     = "<PDS Validate EFS Access Access Point ID>"
#  sensitive = true
#}

variable "ecs_task_role_arn" {
  type        = string
  description = "Airflow Task Role ARN"
  # default     = "<ECS Task Role>"
  sensitive = true
}

variable "ecs_task_execution_role_arn" {
  type        = string
  description = "ECS Task Execution Role ARN"
  # default     = "<ECS Task Execution Role>"
  sensitive = true
}

variable "permission_boundary_for_iam_role" {
  default = "mcp-tenantOperator-APIG"
}
