# Terraform script to create the baseline MWAA environemnt for Nucleus

resource "aws_security_group" "nucleus_security_group" {
  name        = "nucleus_security_group"
  description = "nucleus_security_group"
  vpc_id      = var.vpc_id

  ingress {
    description      = "All traffic"
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = var.nucleus_security_group_ingress_cidr
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
}

resource "aws_s3_bucket" "nucleus_airflow_dags_bucket" {
  bucket = "nucleus-airflow-dags-bucket"

  tags = {
    Name        = "Nucleus Airflow DAGS bucket terraform"
    Environment = "Dev"
  }
}

resource "aws_s3_bucket" "example_23" {
  bucket = "my-tf-test-bucket-23"
}

resource "aws_s3_bucket_object" "dags" {
  bucket = aws_s3_bucket.nucleus_airflow_dags_bucket.id
  acl    = "private"
  key    = "dags/"
  source = "/dev/null"
  depends_on = [aws_s3_bucket.nucleus_airflow_dags_bucket]
}

resource "aws_s3_bucket_object" "requirements" {

  bucket = aws_s3_bucket.nucleus_airflow_dags_bucket.id
  key    = "requirements.txt"
  acl    = "private"  # or can be "public-read"
  source = "./terraform-modules/mwaa-env/requirements.txt"
}

resource "aws_s3_bucket_public_access_block" "nucleus_airflow_dags_bucket_public_access_block" {
  bucket = aws_s3_bucket.nucleus_airflow_dags_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "allow_access_from_another_account" {
  bucket = aws_s3_bucket.nucleus_airflow_dags_bucket.id
  policy = data.aws_iam_policy_document.allow_access_from_another_account.json
}

data "aws_iam_policy_document" "allow_access_from_another_account" {
  statement {
    principals {
      type        = "AWS"
      identifiers = [var.airflow_execution_role]
    }

    actions = [
      "s3:*"
    ]

    effect = "Allow"

    resources = [
      aws_s3_bucket.nucleus_airflow_dags_bucket.arn,
      "${aws_s3_bucket.nucleus_airflow_dags_bucket.arn}/*",
    ]
  }
}

resource "aws_mwaa_environment" "pds_nucleus_airflow_env" {

  name                  = var.airflow_env_name
  airflow_version       = var.airflow_version
  environment_class     = var.airflow_env_class

  dag_s3_path           = var.airflow_dags_path
  execution_role_arn    = var.airflow_execution_role

  requirements_s3_path  = var.airflow_requirements_path

  depends_on = [aws_s3_bucket_object.dags]

  min_workers           = 1
  max_workers           = 25
  webserver_access_mode = "PUBLIC_ONLY"

  network_configuration   {
    security_group_ids = [aws_security_group.nucleus_security_group.id]
    subnet_ids         = var.subnet_ids
  }

  source_bucket_arn = aws_s3_bucket.nucleus_airflow_dags_bucket.arn

  airflow_configuration_options = {
    "core.load_default_connections" = "false"
    "core.load_examples"            = "false"
    "webserver.dag_default_view"    = "tree"
    "webserver.dag_orientation"     = "TB"
    "logging.logging_level"         = "INFO"
  }
}
