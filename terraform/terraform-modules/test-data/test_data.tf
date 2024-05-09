# Terraform script to modify and copy files related with test data

# Replace ECS related variables in PDS Basic Registry Load Use Case DAG file
data "template_file" "pds-basic-registry-load-use-case-dag-template" {
  template = file("terraform-modules/test-data/dags/template-${var.pds_basic_registry_data_load_dag_file_name}")
  vars     = {
    pds_nucleus_ecs_cluster_name      = var.pds_nucleus_ecs_cluster_name
    pds_nucleus_ecs_subnets           = jsonencode(var.pds_nucleus_ecs_subnets)
    pds_nucleus_ecs_security_groups   = var.pds_nucleus_security_group_id
    pds_nucleus_basic_registry_dag_id = var.pds_nucleus_basic_registry_dag_id
  }
}

resource "local_file" "pds-basic-registry-load-use-case-dag-file" {
  content  = data.template_file.pds-basic-registry-load-use-case-dag-template.rendered
  filename = "terraform-modules/test-data/dags/${var.pds_basic_registry_data_load_dag_file_name}"
}

data "aws_s3_bucket" "pds_nucleus_airflow_dags_bucket" {
  bucket = var.mwaa_dag_s3_bucket_name
}

resource "aws_s3_object" "pds_basic_registry_data_load_dag_file" {

  bucket        = var.mwaa_dag_s3_bucket_name
  key           = "dags/${var.pds_basic_registry_data_load_dag_file_name}"
  acl           = "private"
  force_destroy = true
  source        = "terraform-modules/test-data/dags/${var.pds_basic_registry_data_load_dag_file_name}"

  depends_on = [
    data.aws_s3_bucket.pds_nucleus_airflow_dags_bucket,
    local_file.pds-basic-registry-load-use-case-dag-file,
    data.template_file.pds-basic-registry-load-use-case-dag-template
  ]
}
