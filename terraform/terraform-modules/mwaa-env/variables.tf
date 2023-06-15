variable "airflow_env_name" {
  description = "PDS Nucleus Airflow Env Name"
  default     = "PDS-Nucleus-Airflow-Env"
  type        = string
}

variable "airflow_version" {
  description = "PDS Nucleus Airflow Version"
  default     = "2.2.2"
  type        = string
}

variable "airflow_env_class" {
  description = "PDS Nucleus Airflow Environment Class"
  default     = "mw1.medium"
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
  # default     = "<VPC ID>"
  sensitive = true
}

variable "vpc_cidr" {
  description = "VPC CIDR for MWAA"
  type        = string
  # default     = "<VPC CIDR>"
  sensitive = true
}

variable "nucleus_security_group_ingress_cidr" {
  description = "Ingress CIDR for Nucleus Security Group"
  type        = list(string)
  # default     = ["<Ingress CIDR>"]
  sensitive = true
}

variable "subnet_ids" {
  description = "Subnet IDs"
  type        = list(string)
  # default     = ["<COMMA SEPERATED LIST OF SUBNET IDs>"]
  sensitive = true
}

variable "airflow_execution_role" {
  description = "Airflow AWS Execution Role"
  type        = string
  # default     = "<Airflow AWS Execution Role>"
  sensitive = true
}
