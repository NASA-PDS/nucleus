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

data "aws_caller_identity" "current" {}

# IAM Policy Document for Inline Policy
data "aws_iam_policy_document" "mwaa_inline_policy" {
  statement {
    effect = "Allow"
    actions = [
      "airflow:PublishMetrics"
    ]
    resources = [
      "arn:aws:airflow:*:${data.aws_caller_identity.current.account_id}:role/*/*",
      "arn:aws:airflow:*:${data.aws_caller_identity.current.account_id}:environment/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricData"
    ]
    resources = [
      "*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "ecs:RunTask",
      "ecs:DescribeTasks"
    ]
    resources = [
      "arn:aws:ecs:*:${data.aws_caller_identity.current.account_id}:task-definition/pds*:*",
      "arn:aws:ecs:*:${data.aws_caller_identity.current.account_id}:task/pds*/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "iam:PassRole"
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/pds-*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:GenerateDataKey*",
      "kms:Encrypt"
    ]
    not_resources = ["arn:aws:kms:*:${data.aws_caller_identity.current.account_id}:key/*"]
    condition {
      test     = "StringLike"
      variable = "kms:ViaService"
      values   = ["sqs.${var.region}.amazonaws.com"]
    }
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:GetLogEvents",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:*:log-stream:*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:DescribeLogGroups"
    ]
    resources = [
      "*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:GetLogRecord",
      "logs:GetQueryResults",
      "logs:GetLogGroupFields",
      "logs:CreateLogGroup"
    ]
    resources = [
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "sqs:ChangeMessageVisibility",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
      "sqs:GetQueueUrl",
      "sqs:ReceiveMessage",
      "sqs:SendMessage"
    ]
    resources = [
      "arn:aws:sqs:${var.region}:*:airflow-celery-*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:ListAllMyBuckets"
    ]
    resources = [
      "*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:GetBucket*",
      "s3:GetObject*",
      "s3:GetAccountPublicAccessBlock",
      "s3:List*"
    ]
    resources = [
      "arn:aws:s3:::pds-nucleus*",
      "arn:aws:s3:::pds-nucleus*/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:CreateLogGroup",
      "logs:PutLogEvents",
      "logs:GetLogEvents",
      "logs:GetLogRecord",
      "logs:GetLogGroupFields",
      "logs:GetQueryResults"
    ]
    resources = [
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:airflow-${var.airflow_env_name}-*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:DescribeLogGroups"
    ]
    resources = [
      "*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "cloudwatch:PutMetricData"
    ]
    resources = [
      "*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "iam:PassRole"
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/pds_nucleus_*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "lambda:InvokeFunction"
    ]
    resources = [
      "arn:aws:lambda:${var.region}:${data.aws_caller_identity.current.account_id}:function:pds_nucleus_*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "lambda:InvokeFunction"
    ]
    resources = [
      "arn:aws:lambda:${var.region}:${data.aws_caller_identity.current.account_id}:function:pds_nucleus_*"
    ]
  }
}


# The Policy for Permission Boundary
data "aws_iam_policy" "mcp_operator_policy" {
  name = var.permission_boundary_for_iam_roles
}

resource "aws_iam_role" "pds_nucleus_mwaa_execution_role" {
  name = "pds_nucleus_mwaa_execution_role"
  inline_policy {
    name   = "pds-nucleus-mwaa-execution-role-inline-policy"
    policy = data.aws_iam_policy_document.mwaa_inline_policy.json
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

  logging_configuration {
    dag_processing_logs {
      enabled   = true
      log_level = "DEBUG"
    }

    scheduler_logs {
      enabled   = true
      log_level = "INFO"
    }

    task_logs {
      enabled   = true
      log_level = "INFO"
    }

    webserver_logs {
      enabled   = true
      log_level = "ERROR"
    }

    worker_logs {
      enabled   = true
      log_level = "CRITICAL"
    }
  }

  timeouts {
    create = "4h"
    update = "4h"
    delete = "1h"
  }

  depends_on = [aws_iam_role.pds_nucleus_mwaa_execution_role]
}
