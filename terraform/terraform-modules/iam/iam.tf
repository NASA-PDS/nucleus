# Terraform script to create a IAM roles to be used in Nucleus


data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

####################################################
#
# IAM Roles used by cognito-auth terraform module
#
###################################################


data "aws_iam_policy" "mcp_operator_policy" {
  name = var.permission_boundary_for_iam_roles
}

data "aws_iam_policy_document" "assume_role_lambda" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com", "scheduler.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy_document" "alb_auth_lambda_execution_role_policy" {

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:/aws/lambda/${var.pds_nucleus_auth_alb_function_name}:log-stream:*"
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_alb_auth_lambda_execution_role" {
  name = "pds_nucleus_alb_auth_lambda_execution_role"

  inline_policy {
    name   = "alb_auth_lambda_execution_role_policy"
    policy = data.aws_iam_policy_document.alb_auth_lambda_execution_role_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.assume_role_lambda.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}

# Common assume role policy
data "aws_iam_policy_document" "pds_nucleus_airflow_assume_role" {
  statement {
    effect = "Allow"
    actions = [
      "sts:AssumeRole"
    ]
    principals {
      type = "AWS"
      identifiers = ["arn:aws:sts::${data.aws_caller_identity.current.account_id}:assumed-role/${aws_iam_role.pds_nucleus_alb_auth_lambda_execution_role.name}/${var.pds_nucleus_auth_alb_function_name}"]
    }
  }
}


# Airflow Admin Role

data "aws_iam_policy_document" "pds_nucleus_airflow_admin_policy" {
  statement {
    effect = "Allow"
    actions = [
      "airflow:CreateWebLoginToken"
    ]
    resources = [
      "arn:aws:airflow:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:role/pds-nucleus-airflow-env/Admin"
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_admin_role" {
  name = "pds_nucleus_airflow_admin_role"

  inline_policy {
    name   = "pds_nucleus_airflow_admin_policy"
    policy = data.aws_iam_policy_document.pds_nucleus_airflow_admin_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.pds_nucleus_airflow_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}


# Airflow Op Role

data "aws_iam_policy_document" "pds_nucleus_airflow_op_policy" {
  statement {
    effect = "Allow"
    actions = [
      "airflow:CreateWebLoginToken"
    ]
    resources = [
      "arn:aws:airflow:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:role/pds-nucleus-airflow-env/Op"
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_op_role" {
  name = "pds_nucleus_airflow_op_role"

  inline_policy {
    name   = "pds_nucleus_airflow_op_policy"
    policy = data.aws_iam_policy_document.pds_nucleus_airflow_op_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.pds_nucleus_airflow_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}



# Airflow User Role

data "aws_iam_policy_document" "pds_nucleus_airflow_user_policy" {
  statement {
    effect = "Allow"
    actions = [
      "airflow:CreateWebLoginToken"
    ]
    resources = [
      "arn:aws:airflow:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:role/pds-nucleus-airflow-env/User"
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_user_role" {
  name = "pds_nucleus_airflow_user_role"

  inline_policy {
    name   = "pds_nucleus_airflow_user_policy"
    policy = data.aws_iam_policy_document.pds_nucleus_airflow_user_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.pds_nucleus_airflow_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}


# Airflow Viewer Role

data "aws_iam_policy_document" "pds_nucleus_airflow_viewer_policy" {
  statement {
    effect = "Allow"
    actions = [
      "airflow:CreateWebLoginToken"
    ]
    resources = [
      "arn:aws:airflow:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:role/pds-nucleus-airflow-env/Viewer"
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_viewer_role" {
  name = "pds_nucleus_airflow_viewer_role"

  inline_policy {
    name   = "pds_nucleus_airflow_viewer_policy"
    policy = data.aws_iam_policy_document.pds_nucleus_airflow_viewer_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.pds_nucleus_airflow_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}



output "pds_nucleus_alb_auth_lambda_execution_role_arn" {
  value = aws_iam_role.pds_nucleus_alb_auth_lambda_execution_role.arn
}

output "pds_nucleus_admin_role_arn" {
  value = aws_iam_role.pds_nucleus_admin_role.arn
}

output "pds_nucleus_op_role_arn" {
  value = aws_iam_role.pds_nucleus_op_role.arn
}

output "pds_nucleus_user_role_arn" {
  value = aws_iam_role.pds_nucleus_user_role.arn
}

output "pds_nucleus_viewer_role_arn" {
  value = aws_iam_role.pds_nucleus_viewer_role.arn
}

