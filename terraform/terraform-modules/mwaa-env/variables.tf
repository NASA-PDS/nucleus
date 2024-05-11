variable "airflow_env_name" {
  description = "PDS Nucleus Airflow Env Name"
  default     = "PDS-Nucleus-Airflow-Env"
  type        = string
}

variable "airflow_version" {
  description = "PDS Nucleus Airflow Version"
  default     = "2.8.1"
  type        = string
}

variable "airflow_env_class" {
  description = "PDS Nucleus Airflow Environment Class"
  default     = "mw1.small"
  type        = string
}

variable "airflow_dags_path" {
  description = "PDS Nucleus Airflow DAGs Path"
  default     = "dags/"
  type        = string
}

variable "airflow_requirements_path" {
  description = "PDS Nucleus Airflow Python Requirements File Path"
  default     = "requirements.txt"
  type        = string
}

variable "airflow_dags_bucket_arn" {
  description = "PDS Nucleus Airflow DAGS Bucket ARN"
  type        = string
}

variable "nucleus_security_group_id" {
  description = "PDS Nucleus Security Group ID"
  type        = string
}

variable "region" {
  description = "region"
  type        = string
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
  description = "Comma Seperated List of Subnet IDs"
  type        = list(string)
  sensitive   = true
}

variable "permission_boundary_for_iam_roles" {
  description = "Permission boundary for IAM roles"
  type      = string
  sensitive = true
}
