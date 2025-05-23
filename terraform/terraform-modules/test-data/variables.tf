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

variable "pds_basic_registry_data_load_dag_file_name" {
  description = "PDS Basic Registry Data Load DAG File Name"
  type        = string
  default     = "pds-basic-registry-load-use-case.py"
  sensitive   = true
}

variable "pds_nucleus_default_airflow_dag_id" {
  description = "PDS Nucleus Default DAG ID"
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
  type        = string
}

variable "pds_node_names" {
  description = "List of PDS Node Names"
  type        = list(string)
  sensitive   = true
}