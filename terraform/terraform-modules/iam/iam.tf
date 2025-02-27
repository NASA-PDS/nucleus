# Terraform script to create a IAM roles to be used in Nucleus


data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_iam_policy" "mcp_operator_policy" {
  name = var.permission_boundary_for_iam_roles
}

####################################################
#
# IAM Roles and policies used by cognito-auth terraform module
#
###################################################

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



##########################################################
#
# IAM Roles and policies used by ECS tasks
#
##########################################################

#-------------------------------------
# ECS Task Role
#-------------------------------------

# IAM Policy Document for Inline Policy
data "aws_iam_policy_document" "ecs_task_role_inline_policy" {
  statement {
    effect = "Allow"
    actions = [
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:BatchCheckLayerAvailability"
    ]
    resources = [
      "arn:aws:ecr:*:${data.aws_caller_identity.current.account_id}:repository/pds*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "elasticfilesystem:DescribeMountTargets",
      "elasticfilesystem:ClientMount",
      "elasticfilesystem:ClientWrite",
      "elasticfilesystem:ClientRootAccess"
    ]
    resources = [
      "arn:aws:elasticfilesystem:*:${data.aws_caller_identity.current.account_id}:access-point/*",
      "arn:aws:elasticfilesystem:*:${data.aws_caller_identity.current.account_id}:file-system/pds-nucleus*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:CreateLogGroup",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:*:log-stream:*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken"
    ]
    resources = [
      "arn:aws:ecr:*:${data.aws_caller_identity.current.account_id}:repository/pds*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:GetBucket*",
      "s3:GetObject*",
      "s3:List*",
      "s3:PutObject"
    ]
    resources = [
      "arn:aws:s3:::pds-nucleus*",
      "arn:aws:s3:::pds-nucleus*/*",
      "arn:aws:s3:::pds-*-staging*",
      "arn:aws:s3:::pds-*-staging*/*",
      "arn:aws:s3:::pds-*-archive*",
      "arn:aws:s3:::pds-*-archive*/*"
    ]
  }
}


# TODO: Restrict to PDS accounts in future

# IAM Policy Document for Assume Role
data "aws_iam_policy_document" "ecs_task_role_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "pds_nucleus_ecs_task_role" {
  name = "pds_nucleus_ecs_task_role"
  inline_policy {
    name   = "pds-nucleus-ecs-task-role-inline-policy"
    policy = data.aws_iam_policy_document.ecs_task_role_inline_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.ecs_task_role_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}


#-------------------------------------
# ECS Task Execution Role
#-------------------------------------

# IAM Policy Document for Inline Policy
data "aws_iam_policy_document" "ecs_task_execution_role_inline_policy" {
  statement {
    effect = "Allow"
    actions = [
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:BatchCheckLayerAvailability"
    ]
    resources = [
      "arn:aws:ecr:*:${data.aws_caller_identity.current.account_id}:repository/pds*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken"
    ]
    resources = [
      "*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:CreateLogGroup"
    ]
    resources = [
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:*:log-stream:*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "ecs:stopTask"
    ]
    resources = [
      "arn:aws:ecs:*:${data.aws_caller_identity.current.account_id}:task/pds-nucleus-ecs/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "kms:Decrypt"
    ]
    resources = [
      "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:pds/nucleus/opensearch/creds/*",
      var.aws_secretmanager_key_arn
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "kms:Decrypt"
    ]
    resources = [
      "arn:aws:secretsmanager:${data.aws_region.current.name}}:${data.aws_caller_identity.current.account_id}:secret:pds/nucleus/opensearch/creds/*",
      var.aws_secretmanager_key_arn
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_ecs_task_execution_role" {
  name = "pds_nucleus_ecs_task_execution_role"
  inline_policy {
    name   = "pds-nucleus-ecs-task-execution-role-inline-policy"
    policy = data.aws_iam_policy_document.ecs_task_execution_role_inline_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.ecs_task_role_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}



##########################################################
#
# IAM Roles and policies used by archive replication
#
##########################################################

data "aws_iam_policy_document" "pds_nucleus_archive_replication_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "pds_nucleus_archive_replication_role" {
  name               = "pds-nucleus-archive-replication-role"
  assume_role_policy = data.aws_iam_policy_document.pds_nucleus_archive_replication_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}

data "aws_iam_policy_document" "pds_nucleus_archive_replication_policy" {

  statement {
    effect = "Allow"

    actions = [
      "s3:GetReplicationConfiguration",
      "s3:ListBucket",
    ]

    resources = ["arn:aws:s3:::pds-*-archive-*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "s3:GetObjectVersionForReplication",
      "s3:GetObjectVersionAcl",
      "s3:GetObjectVersionTagging",
    ]

    resources = ["arn:aws:s3:::pds-*-archive-*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "s3:ReplicateObject",
      "s3:ReplicateDelete",
      "s3:ReplicateTags",
    ]

    resources = ["arn:aws:s3:::pds-*-archive-*"]
  }
}

resource "aws_iam_policy" "pds_nucleus_archive_replication_policy" {
  name   = "pds-nucleus-archive-replication-policy"
  policy = data.aws_iam_policy_document.pds_nucleus_archive_replication_policy.json
}

resource "aws_iam_role_policy_attachment" "pds_nucleus_archive_replication_policy_document" {
  role       = aws_iam_role.pds_nucleus_archive_replication_role.name
  policy_arn = aws_iam_policy.pds_nucleus_archive_replication_policy.arn
}


##########################################################
#
# IAM Roles and policies used by MWAA
#
##########################################################

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
      "kms:Decrypt",
      "kms:DescribeKey",
      "kms:GenerateDataKey*",
      "kms:Encrypt"
    ]
    not_resources = ["arn:aws:kms:*:${data.aws_caller_identity.current.account_id}:key/*"]
    condition {
      test     = "StringLike"
      variable = "kms:ViaService"
      values   = ["sqs.${data.aws_region.current.name}.amazonaws.com"]
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
      "arn:aws:sqs:${data.aws_region.current.name}:*:airflow-celery-*"
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
      "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:airflow-${var.airflow_env_name}-*"
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
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/pds_nucleus_ecs_task_role",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/pds_nucleus_ecs_task_execution_role",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/pds-eng-aoss-role"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "lambda:InvokeFunction"
    ]
    resources = [
      "arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:function:pds_nucleus_product_processing_status_tracker"
    ]
  }
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


########################################################################
#
# IAM Roles and policies used by product copy completion checker module
#
########################################################################

data "aws_iam_policy_document" "assume_role_airflow" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["airflow-env.amazonaws.com", "airflow.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy_document" "lambda_inline_policy" {
  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:CreateLogGroup",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:*:log-stream:*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "rds-data:ExecuteStatement"
    ]
    resources = [
      "arn:aws:rds:*:${data.aws_caller_identity.current.account_id}:cluster:${var.rds_cluster_id}"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue"
    ]
    resources = [
      "arn:aws:secretsmanager:*:${data.aws_caller_identity.current.account_id}:secret:pds/nucleus/rds/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:GetBucket*",
      "s3:GetObject*",
      "s3:PutObject*",
      "s3:List*"
    ]
    resources = [
      "arn:aws:s3:::pds-nucleus*",
      "arn:aws:s3:::pds-nucleus*/*",
      "arn:aws:s3:::pds-*-staging*",
      "arn:aws:s3:::pds-*-staging*/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "airflow:CreateCliToken"
    ]
    resources = [
      "arn:aws:airflow:*:${data.aws_caller_identity.current.account_id}:environment/pds*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ]
    resources = [
      "arn:aws:sqs:*:${data.aws_caller_identity.current.account_id}:pds-*"
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_lambda_execution_role" {
  name = "pds_nucleus_lambda_execution_role"
  inline_policy {
    name   = "pds-nucleus-lambda-execution-inline-policy"
    policy = data.aws_iam_policy_document.lambda_inline_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.assume_role_lambda.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}



###########################################################
#
# Outputs
#
###########################################################

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

output "pds_nucleus_ecs_task_role_arn" {
  value = aws_iam_role.pds_nucleus_ecs_task_role.arn
}

output "pds_nucleus_ecs_task_execution_role_arn" {
  value = aws_iam_role.pds_nucleus_ecs_task_execution_role.arn
}

output "pds_nucleus_archive_replication_role_arn" {
  value = aws_iam_role.pds_nucleus_archive_replication_role.arn
}

output "pds_nucleus_mwaa_execution_role_arn" {
  value = aws_iam_role.pds_nucleus_mwaa_execution_role.arn
}

output "pds_nucleus_lambda_execution_role_arn" {
  value = aws_iam_role.pds_nucleus_lambda_execution_role.arn
}