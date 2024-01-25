variable "efs_file_system_id" {
  type        = string
  description = "EFS File System ID"
  # default     = "<EFS File System ID>"
  sensitive = true
}

variable "registry_loader_scripts_access_point_id" {
  type        = string
  description = "Registry Loader Scripts EFS Access Point ID"
  # default     = "<Registry Loader Scripts EFS Access Point ID>"
  sensitive = true
}

variable "registry_loader_default_configs_access_point_id" {
  type        = string
  description = "Registry Loader Default Configs EFS Access Point ID"
  # default     = "<Registry Loader Default Configs EFS Access Point ID>"
  sensitive = true
}

variable "pds_data_access_point_id" {
  type        = string
  description = "PDS Data Access Point ID"
  # default     = "<PDS Data Access Point ID>"
  sensitive = true
}

variable "task_role_arn" {
  type        = string
  description = "Airflow Task Role ARN"
  # default     = "<Airflow Task Role>"
  sensitive = true
}

variable "execution_role_arn" {
  type        = string
  description = "Airflow Execution Role ARN"
  # default     = "<Airflow Execution Role>"
  sensitive = true
}
