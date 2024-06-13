# Terraform script to modify and copy files related with test data

data "aws_s3_bucket" "pds_nucleus_airflow_dags_bucket" {
  bucket = var.mwaa_dag_s3_bucket_name
}

# Replace ECS related variables in PDS Basic Registry Load Use Case DAG file for each PDS Node
data "template_file" "pds-basic-registry-load-use-case-dag-template" {
  count    = length(var.pds_node_names)
  template = file("terraform-modules/test-data/dags/template-${var.pds_basic_registry_data_load_dag_file_name}")
  vars = {
    pds_nucleus_ecs_cluster_name      = var.pds_nucleus_ecs_cluster_name
    pds_nucleus_ecs_subnets           = jsonencode(var.pds_nucleus_ecs_subnets)
    pds_nucleus_ecs_security_groups   = var.pds_nucleus_security_group_id
    pds_nucleus_basic_registry_dag_id = "${var.pds_node_names[count.index]}-${var.pds_nucleus_basic_registry_dag_id}"
  }
}

# Create a default DAG file for each PDS Node
resource "local_file" "pds-basic-registry-load-use-case-dag-file" {
  count    = length(var.pds_node_names)
  content  = data.template_file.pds-basic-registry-load-use-case-dag-template[count.index].rendered
  filename = "terraform-modules/test-data/dags/${var.pds_node_names[count.index]}-${var.pds_basic_registry_data_load_dag_file_name}"
}

# Create S3 object for default DAG file of each PDS Node
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
