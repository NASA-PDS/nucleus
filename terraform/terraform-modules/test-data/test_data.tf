# Terraform script to modify and copy files related with test data

data "aws_s3_bucket" "pds_nucleus_airflow_dags_bucket" {
  bucket = var.mwaa_dag_s3_bucket_name
}

#-----------------------------------------------
# PDS Nucleus Basic Registry Load Use Case DAG
#-----------------------------------------------

# Replace ECS related variables in PDS Basic Registry Load Use Case DAG file for each PDS Node
data "template_file" "pds-basic-registry-load-use-case-dag-template" {
  count    = length(var.pds_node_names)
  template = file("terraform-modules/test-data/dags/template-${var.pds_basic_registry_data_load_dag_file_name}")
  vars = {
    pds_node_name                                       = var.pds_node_names[count.index]
    pds_nucleus_ecs_cluster_name                        = var.pds_nucleus_ecs_cluster_name
    pds_nucleus_ecs_subnets                             = jsonencode(var.pds_nucleus_ecs_subnets)
    pds_nucleus_ecs_security_groups                     = var.pds_nucleus_security_group_id
    pds_nucleus_basic_registry_dag_id                   = "${var.pds_node_names[count.index]}-${var.pds_nucleus_default_airflow_dag_id}"
 }
}

# Create a default DAG file for each PDS Node
resource "local_file" "pds-basic-registry-load-use-case-dag-file" {
  count    = length(var.pds_node_names)
  content  = data.template_file.pds-basic-registry-load-use-case-dag-template[count.index].rendered
  filename = "terraform-modules/test-data/dags/${var.pds_node_names[count.index]}-${var.pds_basic_registry_data_load_dag_file_name}"
}

# Create an S3 object for default DAG file of each PDS Node
resource "aws_s3_object" "pds_basic_registry_data_load_dag_file" {
  count  = length(var.pds_node_names)
  bucket = var.mwaa_dag_s3_bucket_name
  key    = "dags/${var.pds_node_names[count.index]}-${var.pds_basic_registry_data_load_dag_file_name}"
  acl    = "private"
  source = "terraform-modules/test-data/dags/${var.pds_node_names[count.index]}-${var.pds_basic_registry_data_load_dag_file_name}"

  depends_on = [
    data.aws_s3_bucket.pds_nucleus_airflow_dags_bucket,
    local_file.pds-basic-registry-load-use-case-dag-file,
    data.template_file.pds-basic-registry-load-use-case-dag-template
  ]
}



#-----------------------------------------------
# PDS Nucleus S3 Backlog Processor DAG
#-----------------------------------------------

# Replace ECS related variables in PDS Nucleus S3 Backlog Processor DAG file for each PDS Node
data "template_file" "pds-nucleus-s3-backlog-processor-dag-template" {
  count    = length(var.pds_node_names)
  template = file("terraform-modules/test-data/dags/template-${var.pds_nucleus_s3_backlog_processor_dag_file_name}")
  vars = {
    pds_node_name                                       = var.pds_node_names[count.index]
    pds_nucleus_ecs_cluster_name                        = var.pds_nucleus_ecs_cluster_name
    pds_nucleus_ecs_subnets                             = jsonencode(var.pds_nucleus_ecs_subnets)
    pds_nucleus_ecs_security_groups                     = var.pds_nucleus_security_group_id
    pds_nucleus_s3_backlog_processor_dag_id             = "${var.pds_node_names[count.index]}-${var.pds_nucleus_s3_backlog_processor_dag_id}"
  }
}

# Create an S3 Backlog Processor DAG file for each PDS Node
resource "local_file" "pds-nucleus-s3-backlog-processor-dag-file" {
  count    = length(var.pds_node_names)
  content  = data.template_file.pds-nucleus-s3-backlog-processor-dag-template[count.index].rendered
  filename = "terraform-modules/test-data/dags/${var.pds_node_names[count.index]}-${var.pds_nucleus_s3_backlog_processor_dag_file_name}"
}

# Create an S3 object for S3 Backlog Processor DAG file of each PDS Node
resource "aws_s3_object" "pds_nucleus_s3_backlog_processor_dag_file" {
  count  = length(var.pds_node_names)
  bucket = var.mwaa_dag_s3_bucket_name
  key    = "dags/${var.pds_node_names[count.index]}-${var.pds_nucleus_s3_backlog_processor_dag_file_name}"
  acl    = "private"
  source = "terraform-modules/test-data/dags/${var.pds_node_names[count.index]}-${var.pds_nucleus_s3_backlog_processor_dag_file_name}"

  depends_on = [
    data.aws_s3_bucket.pds_nucleus_airflow_dags_bucket,
    local_file.pds-nucleus-s3-backlog-processor-dag-file,
    data.template_file.pds-nucleus-s3-backlog-processor-dag-template
  ]
}
