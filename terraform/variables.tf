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

variable "nucleus_security_group_ingress_cidr" {
  description = "Ingress CIDR for Nucleus Security Group"
  type        = list(string)
  sensitive   = true
}

variable "subnet_ids" {
  description = "Subnet IDs"
  type        = list(string)
  sensitive   = true
}

#variable "airflow_execution_role" {
#  description = "Airflow AWS Execution Role"
#  type        = string
#  sensitive   = true
#}
#
#variable "efs_file_system_id" {
#  type        = string
#  description = "EFS File System ID"
#  sensitive   = true
#}
#
#variable "registry_loader_scripts_access_point_id" {
#  type        = string
#  description = "Registry Loader Scripts EFS Access Point ID"
#  sensitive   = true
#}
#
#variable "registry_loader_default_configs_access_point_id" {
#  type        = string
#  description = "Registry Loader Default Configs EFS Access Point ID"
#  sensitive   = true
#}
#
#variable "pds_data_access_point_id" {
#  type        = string
#  description = "PDS Data Access Point ID"
#  sensitive   = true
#}

#variable "task_role_arn" {
#  type        = string
#  description = "Airflow Task Role ARN"
#  sensitive   = true
#}
#
#variable "execution_role_arn" {
#  type        = string
#  description = "Airflow Execution Role ARN"
#  sensitive   = true
#}

variable "mwaa_dag_s3_bucket_name" {
  type        = string
  description = "The name of the S3 bucket containing MWAA DAG files"
  sensitive   = true
}

variable "pds_registry_loader_harvest_ecr_image_path" {
  type        = string
  description = "PDS Registry Loader Harvest ECR Image Path"
  sensitive   = true
}

variable "pds_registry_loader_harvest_cloudwatch_logs_group" {
  type        = string
  description = "PDS Registry Loader Harvest Cloudwatch Logs Group"
  sensitive   = true
}

variable "pds_registry_loader_harvest_cloudwatch_logs_region" {
  type        = string
  description = "PDS Registry Loader Harvest Cloudwatch Logs Region"
  sensitive   = true
}

variable "pds_validate_ecr_image_path" {
  type        = string
  description = "PDS Validate ECR Image Path"
  sensitive   = true
}

variable "pds_validate_cloudwatch_logs_group" {
  type        = string
  description = "PDS Validate Cloudwatch Logs Group"
  sensitive   = true
}

variable "pds_validate_cloudwatch_logs_region" {
  type        = string
  description = "PDS Validate Cloudwatch Logs Region"
  sensitive   = true
}

variable "pds_validate_ref_cloudwatch_logs_group" {
  type        = string
  description = "PDS Validate Ref Cloudwatch Logs Group"
  sensitive   = true
}

variable "pds_validate_ref_cloudwatch_logs_region" {
  type        = string
  description = "PDS Validate Ref Cloudwatch Logs Region"
  sensitive   = true
}

