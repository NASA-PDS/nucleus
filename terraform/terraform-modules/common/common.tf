# Terraform script to create the common resources for PDS Nucleus

resource "aws_s3_bucket" "pds_nucleus_airflow_dags_bucket" {
  bucket        = var.mwaa_dag_s3_bucket_name
  force_destroy = true
}

resource "aws_s3_object" "dags" {
  bucket = aws_s3_bucket.pds_nucleus_airflow_dags_bucket.id
  acl    = "private"
  key    = "dags/"
  source = "/dev/null"

  depends_on = [aws_s3_bucket.pds_nucleus_airflow_dags_bucket]
}

resource "aws_s3_object" "pds_node_specific_dags" {
  count = length(var.pds_node_names)

  bucket = aws_s3_bucket.pds_nucleus_airflow_dags_bucket.id
  acl    = "private"
  key    = "dags/${var.pds_node_names[count.index]}/"
  source = "/dev/null"

  depends_on = [aws_s3_object.dags]
}

resource "aws_s3_bucket" "pds_node_specific_dags_approval_bucket" {
  count = length(var.pds_node_names)

  # convert PDS node name to S3 bucket name compatible format
  bucket = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_node_specific_dags_approval_bucket_postfix}"
}

resource "aws_s3_object" "pds_node_specific_dags_to_be_approved" {
  count = length(var.pds_node_names)

  bucket = aws_s3_bucket.pds_node_specific_dags_approval_bucket[count.index].id
  acl    = "private"
  key    = "To-Be-Approved-DAGs/"
  source = "/dev/null"

  depends_on = [aws_s3_object.dags]
}

resource "aws_s3_object" "pds_node_specific_dags_approved" {
  count = length(var.pds_node_names)

  bucket = aws_s3_bucket.pds_node_specific_dags_approval_bucket[count.index].id
  acl    = "private"
  key    = "Approved-DAGs/"
  source = "/dev/null"

  depends_on = [aws_s3_object.dags]
}

resource "aws_s3_object" "pds_node_specific_dags_rejected" {
  count = length(var.pds_node_names)

  bucket = aws_s3_bucket.pds_node_specific_dags_approval_bucket[count.index].id
  acl    = "private"
  key    = "Rejected-DAGs/"
  source = "/dev/null"

  depends_on = [aws_s3_object.dags]
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
