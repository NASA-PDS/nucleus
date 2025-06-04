# Terraform script to create the common resources for PDS Nucleus

resource "aws_s3_bucket" "pds_nucleus_airflow_dags_bucket" {
  bucket        = var.mwaa_dag_s3_bucket_name
  force_destroy = true
}

resource "aws_s3_bucket_logging" "pds_nucleus_auth_alb_logs_bucket_logging" {
  bucket = aws_s3_bucket.pds_nucleus_airflow_dags_bucket.id

  target_bucket = aws_s3_bucket.pds_nucleus_airflow_dags_bucket_logs.id
  target_prefix = "${var.mwaa_dag_s3_bucket_name}-logs"
}

#  logging bucket for pds_nucleus_airflow_dags_bucket bucket
resource "aws_s3_bucket" "pds_nucleus_airflow_dags_bucket_logs" {
  bucket = "${var.mwaa_dag_s3_bucket_name}-logs"
}

resource "aws_s3_bucket_ownership_controls" "pds_nucleus_airflow_dags_bucket_logs_controls" {
  bucket = aws_s3_bucket.pds_nucleus_airflow_dags_bucket_logs.id

  rule {
    object_ownership = "ObjectWriter"
  }
}

resource "aws_s3_bucket_acl" "pds_nucleus_airflow_dags_bucket_logs_acl" {
  bucket = aws_s3_bucket.pds_nucleus_airflow_dags_bucket_logs.id
  acl    = "log-delivery-write"

  depends_on = [
    aws_s3_bucket_ownership_controls.pds_nucleus_airflow_dags_bucket_logs_controls
  ]
}

data "aws_iam_policy_document" "pds_nucleus_airflow_dags_bucket_logs_bucket_policy" {
  statement {
    sid    = "s3-log-delivery"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["logging.s3.amazonaws.com"]
    }

    actions = ["s3:PutObject"]

    resources = [
      "${aws_s3_bucket.pds_nucleus_airflow_dags_bucket_logs.arn}/*",
    ]
  }
}

resource "aws_s3_bucket_policy" "pds_nucleus_airflow_dags_bucket_logs_bucket_policy" {
  bucket = aws_s3_bucket.pds_nucleus_airflow_dags_bucket_logs.id
  policy = data.aws_iam_policy_document.pds_nucleus_airflow_dags_bucket_logs_bucket_policy.json
}

resource "aws_s3_bucket_policy" "logs_bucket_policy" {
  bucket = aws_s3_bucket.pds_nucleus_airflow_dags_bucket_logs.id

  policy = data.aws_iam_policy_document.pds_nucleus_airflow_dags_bucket_logs_bucket_policy.json
}

resource "aws_s3_bucket_lifecycle_configuration" "pds_nucleus_airflow_dags_bucket_logs_lifecycle" {
  bucket = aws_s3_bucket.pds_nucleus_airflow_dags_bucket_logs.id

  rule {
    id     = "delete_old_logs"
    status = "Enabled"

    # Delete objects after a certain number of days
    expiration {
      days = 7
    }
  }
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
