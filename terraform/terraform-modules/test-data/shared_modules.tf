#-----------------------------------------------
# Shared PDS Airflow Custom Operators Module
#-----------------------------------------------

resource "aws_s3_object" "pds_airflow_custom_operators" {
  bucket      = var.mwaa_dag_s3_bucket_name
  key         = "dags/pds_airflow_custom_operators.py"
  acl         = "private"
  source      = "terraform-modules/test-data/dags/pds_airflow_custom_operators.py"
  source_hash = filemd5("terraform-modules/test-data/dags/pds_airflow_custom_operators.py")

  tags = var.tags
}

#-----------------------------------------------
# Shared PDS Log Parsers Module
#-----------------------------------------------

resource "aws_s3_object" "pds_log_parsers" {
  bucket      = var.mwaa_dag_s3_bucket_name
  key         = "dags/pds_log_parsers.py"
  acl         = "private"
  source      = "terraform-modules/test-data/dags/pds_log_parsers.py"
  source_hash = filemd5("terraform-modules/test-data/dags/pds_log_parsers.py")

  tags = var.tags
}

#-----------------------------------------------
# Shared PDS Registry Client Module
#-----------------------------------------------

resource "aws_s3_object" "pds_registry_client" {
  bucket      = var.mwaa_dag_s3_bucket_name
  key         = "dags/pds_registry_client.py"
  acl         = "private"
  source      = "terraform-modules/test-data/dags/pds_registry_client.py"
  source_hash = filemd5("terraform-modules/test-data/dags/pds_registry_client.py")

  tags = var.tags
}
