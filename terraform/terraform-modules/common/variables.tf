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
  default     = "dags/"
  type        = string
}

variable "region" {
  description = "region"
  type        = string
  default     = "us-west-2"
}

variable "tags" {
  description = "Default tags"
  default     = { "env" : "dev" }
  type        = map(string)
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

variable "mwaa_dag_s3_bucket_name" {
  description = "The name of the S3 bucket containing MWAA DAG files"
  type        = string
  sensitive   = true
}

variable "nucleus_security_group_id" {
  description = "The ID of the PDS Nucleus security group"
  type        = string
  sensitive   = true
}

variable "pds_node_names" {
  type        = list(string)
  description = "List of PDS Node Names"
}

variable "pds_node_specific_dags_approval_bucket_postfix" {
  type        = string
  default     = "dags-for-approval"
  description = "PDS Node Specific DAG Approval Bucket Postfix"
}
