# Terraform script to create the common resources for PDS Nucleus

resource "aws_security_group" "nucleus_security_group" {
  name        = var.nucleus_security_group_name
  description = "PDS Nucleus security group"
  vpc_id      = var.vpc_id

  ingress {
    from_port = 2049
    to_port   = 2049
    protocol  = "tcp"
    self      = true
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
}

resource "aws_s3_bucket" "pds_nucleus_airflow_dags_bucket" {
  bucket = var.mwaa_dag_s3_bucket_name
  #  force_destroy = true
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

output "pds_nucleus_security_group_id" {
  value = aws_security_group.nucleus_security_group.id
}

output "pds_nucleus_airflow_dags_bucket_arn" {
  value = aws_s3_bucket.pds_nucleus_airflow_dags_bucket.arn
}
