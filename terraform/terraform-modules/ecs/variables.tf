variable "efs_file_system_id" {
  type        = string
  description = "EFS File System ID"
  default     = "<EFS File System ID>"
}

variable "registry_loader_scripts_access_point_id" {
  type        = string
  description = "Registry Loader Scripts EFS Access Point ID"
  default     = "<Registry Loader Scripts EFS Access Point ID>"
}

variable "registry_loader_default_configs_access_point_id" {
  type        = string
  description = "Registry Loader Default Configs EFS Access Point ID"
  default     = "<Registry Loader Default Configs EFS Access Point ID>"
}

variable "task_role_arn" {
  type        = string
  description = "Airflow Task Role ARN"
  default     = "<Airflow Task Role ARN>"
}

variable "execution_role_arn" {
  type        = string
  description = "Airflow Execution Role ARN"
  default     = "<Airflow Execution Role ARN>"
}
