# Terraform script to create the baseline MWAA environment for Nucleus

# IAM Policy Document for Assume Role
data "aws_iam_policy_document" "assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["airflow-env.amazonaws.com", "airflow.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

# IAM Policy Document for Inline Policy
data "aws_iam_policy_document" "inline_policy" {
  source_policy_documents = [file("${path.module}/mwaa_iam_policy.json")]
}

# The Policy for Permission Boundary
data "aws_iam_policy" "mcp_operator_policy" {
  name = var.permission_boundary_for_iam_role
}

resource "aws_iam_role" "pds_nucleus_mwaa_execution_role" {
  name = "pds_nucleus_mwaa_execution_role"
  inline_policy {
    name   = "pds-nucleus-mwaa-execution-role-inline-policy"
    policy = data.aws_iam_policy_document.inline_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}

resource "aws_mwaa_environment" "pds_nucleus_airflow_env" {

  name              = var.airflow_env_name
  airflow_version   = var.airflow_version
  environment_class = var.airflow_env_class

  dag_s3_path        = var.airflow_dags_path
  execution_role_arn = aws_iam_role.pds_nucleus_mwaa_execution_role.arn

  requirements_s3_path = var.airflow_requirements_path

  min_workers           = 1
  max_workers           = 10
  webserver_access_mode = "PUBLIC_ONLY"

  network_configuration {
    security_group_ids = [var.nucleus_security_group_id]
    subnet_ids         = var.subnet_ids
  }

  source_bucket_arn = var.airflow_dags_bucket_arn

  airflow_configuration_options = {
    "core.load_default_connections" = "false"
    "core.load_examples"            = "false"
    "webserver.dag_default_view"    = "tree"
    "webserver.dag_orientation"     = "TB"
    "logging.logging_level"         = "INFO"
  }

  depends_on = [aws_iam_role.pds_nucleus_mwaa_execution_role]
}
