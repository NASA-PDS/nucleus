variable "pds_nucleus_ecs_cluster_name" {
  description = "PDS Nucleus ECS Cluster Name"
  type        = string
  sensitive   = true
}

variable "pds_nucleus_ecs_subnets" {
  description = "PDS Nucleus ECS Subnets"
  type        = list(string)
  sensitive   = true
}

variable "pds_nucleus_security_group_id" {
  description = "PDS Nucleus ECS Security Group ID"
  type        = string
  sensitive   = true
}

variable "mwaa_dag_s3_bucket_name" {
  description = "The name of the S3 bucket containing MWAA DAG files"
  type        = string
  #  default     = "pds-nucleus-airflow-dags-bucket-mcp-dev-2"
  sensitive   = true
}

variable "pds_validate_and_harvest_dag_file_name" {
  description = "PDS Validate and Harvest DAG file name (no archive task)"
  default     = "pds-validate-and-harvest.py"
  type        = string
}

variable "pds_validate_and_harvest_dag_id" {
  description = "PDS Validate and Harvest DAG ID (no archive task)"
  default     = "pds-validate-and-harvest"
  type        = string
}

variable "pds_basic_registry_data_load_dag_file_name" {
  description = "PDS Basic Registry Data Load DAG File Name"
  type        = string
  default     = "pds-basic-registry-load.py"
  sensitive   = true
}

variable "pds_basic_registry_data_load_dag_id" {
  description = "PDS Basic Registry Data Load DAG ID"
  default     = "pds-basic-registry-load"
  type        = string
}

variable "pds_nucleus_s3_backlog_processor_dag_file_name" {
  description = "PDS Nucleus S3 Backlog Processor DAG File Name"
  type        = string
  default     = "pds-nucleus-s3-backlog-processor.py"
  sensitive   = true
}

variable "pds_nucleus_s3_backlog_processor_dag_id" {
  description = "PDS Nucleus S3 Backlog Processor DAG ID"
  default     = "pds-nucleus-s3-backlog-processor"
  type        = string
}

variable "pds_nucleus_default_airflow_dag_id" {
  description = "PDS Nucleus Default DAG ID"
  default     = "pds-validate-and-harvest"
  type        = string
}

variable "pds_node_names" {
  description = "List of PDS Node Names"
  type        = list(string)
  sensitive   = true
}

variable "tags" {
  description = "Resource tags"
  type        = map(string)
  default     = {}
}

variable "region" {
  description = "AWS Region"
  type        = string
}