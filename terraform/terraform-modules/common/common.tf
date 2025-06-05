# Terraform script to create the common resources for PDS Nucleus

resource "aws_s3_bucket" "pds_nucleus_airflow_dags_bucket" {
  bucket        = var.mwaa_dag_s3_bucket_name
  force_destroy = true
}

#  PDS shared logs bucket for pds_nucleus_airflow_dags_bucket
data "aws_s3_bucket" "pds_shared_logs_bucket" {
  bucket = var.pds_shared_logs_bucket_name
}

resource "aws_s3_bucket_logging" "pds_nucleus_airflow_dags_bucket_logging" {
  bucket = aws_s3_bucket.pds_nucleus_airflow_dags_bucket.id

  target_bucket = data.aws_s3_bucket.pds_shared_logs_bucket.id
  target_prefix = "nucleus/dags-bucket-logs/${var.mwaa_dag_s3_bucket_name}-logs"
}

resource "aws_s3_object" "dags" {
  bucket = aws_s3_bucket.pds_nucleus_airflow_dags_bucket.id
  acl    = "private"
  key    = "dags/"
  source = "/dev/null"

  depends_on = [aws_s3_bucket.pds_nucleus_airflow_dags_bucket]
}

resource "aws_s3_object" "requirements" {

  bucket = aws_s3_bucket.pds_nucleus_airflow_dags_bucket.id
  key    = "requirements.txt"
  acl    = "private"
  source = "./terraform-modules/mwaa-env/requirements.txt"

  depends_on = [aws_s3_bucket.pds_nucleus_airflow_dags_bucket]
}

output "pds_nucleus_airflow_dags_bucket_arn" {
  value = aws_s3_bucket.pds_nucleus_airflow_dags_bucket.arn
}
