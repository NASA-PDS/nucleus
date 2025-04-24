# Terraform script to create a IAM roles to be used in Nucleus


data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

data "aws_iam_policy" "mcp_operator_policy" {
  arn = var.permission_boundary_for_iam_roles_arn
}

################################################################
#
# Assume role policies
#
################################################################

data "aws_iam_policy_document" "assume_role_lambda" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}


################################################################
#
# IAM Roles and policies used by cognito-auth terraform module
#
################################################################

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
      type        = "AWS"
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
      "arn:aws:airflow:${var.region}:${data.aws_caller_identity.current.account_id}:role/pds-nucleus-airflow-env/Admin"
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
      "arn:aws:airflow:${var.region}:${data.aws_caller_identity.current.account_id}:role/pds-nucleus-airflow-env/Op"
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
      "arn:aws:airflow:${var.region}:${data.aws_caller_identity.current.account_id}:role/pds-nucleus-airflow-env/User"
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
      "arn:aws:airflow:${var.region}:${data.aws_caller_identity.current.account_id}:role/pds-nucleus-airflow-env/Viewer"
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

  count = length(var.pds_node_names)

  statement {
    effect = "Allow"
    actions = [
      "elasticfilesystem:DescribeMountTargets",
      "elasticfilesystem:ClientMount",
      "elasticfilesystem:ClientWrite",
      "elasticfilesystem:ClientRootAccess"
    ]
    resources = [
      "arn:aws:elasticfilesystem:*:${data.aws_caller_identity.current.account_id}:file-system/pds-nucleus*-${var.pds_node_names[count.index]}"
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
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:/pds/ecs/*-${var.pds_node_names[count.index]}:log-stream:ecs/pds-*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:GetBucket*",
      "s3:GetObject*",
      "s3:List*"
    ]
    resources = [
      "arn:aws:s3:::${lower(replace(var.pds_node_names[count.index], "_", "-"))}-staging*",
      "arn:aws:s3:::${lower(replace(var.pds_node_names[count.index], "_", "-"))}-staging*/*",
      "arn:aws:s3:::${lower(replace(var.pds_node_names[count.index], "_", "-"))}-archive*",
      "arn:aws:s3:::${lower(replace(var.pds_node_names[count.index], "_", "-"))}-archive*/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject"
    ]
    resources = [
      "arn:aws:s3:::${lower(replace(var.pds_node_names[count.index], "_", "-"))}-archive*",
      "arn:aws:s3:::${lower(replace(var.pds_node_names[count.index], "_", "-"))}-archive*/*",
      "arn:aws:s3:::${lower(replace(var.pds_node_names[count.index], "_", "-"))}-config*/*",
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "sqs:sendmessage"
    ]
    resources = [
      "arn:aws:sqs:${var.region}:${data.aws_caller_identity.current.account_id}:pds-nucleus-*-${var.pds_node_names[count.index]}"
    ]
  }
}

# IAM Policy Document for Assume Role
data "aws_iam_policy_document" "ecs_task_role_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:ecs:${var.region}:${data.aws_caller_identity.current.account_id}:*"]
    }

    condition {
      test     = "StringLike"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

# Create pds_nucleus_ecs_task_roles per PDS Node
resource "aws_iam_role" "pds_nucleus_ecs_task_role" {
  count = length(var.pds_node_names)

  name = "pds_nucleus_ecs_task_role-${var.pds_node_names[count.index]}"
  inline_policy {
    name   = "pds-nucleus-ecs-task-role-inline-policy"
    policy = data.aws_iam_policy_document.ecs_task_role_inline_policy[count.index].json
  }
  assume_role_policy   = data.aws_iam_policy_document.ecs_task_role_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}


#-------------------------------------
# Harvest ECS Task Role
#-------------------------------------

# IAM Policy Document for Inline Policy
data "aws_iam_policy_document" "harvest_ecs_task_role_inline_policy" {
  count = length(var.pds_node_names)

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
      "arn:aws:elasticfilesystem:*:${data.aws_caller_identity.current.account_id}:file-system/pds-nucleus*-${var.pds_node_names[count.index]}"
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
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:/pds/ecs/harvest-${var.pds_node_names[count.index]}:log-stream:ecs/pds-registry-loader-harvest/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "aoss:APIAccessAll"
    ]
    resources = [
      var.pds_nucleus_opensearch_collection_arns[count.index]
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "aoss:DashboardsAccessAll"
    ]
    resources = [
      "arn:aws:aoss:${var.region}:${data.aws_caller_identity.current.account_id}:dashboards/default"
    ]
  }
}

# IAM Policy Document for Assume Role
data "aws_iam_policy_document" "harvest_ecs_task_role_assume_role" {
  count = length(var.pds_node_names)

  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:ecs:${var.region}:${data.aws_caller_identity.current.account_id}:*"]
    }

    condition {
      test     = "StringLike"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "pds_nucleus_harvest_ecs_task_role" {
  count = length(var.pds_node_names)

  name = "pds_nucleus_harvest_ecs_task_role-${var.pds_node_names[count.index]}"
  inline_policy {
    name   = "pds-nucleus-harvest-ecs-task-role-inline-policy"
    policy = data.aws_iam_policy_document.harvest_ecs_task_role_inline_policy[count.index].json
  }
  assume_role_policy   = data.aws_iam_policy_document.harvest_ecs_task_role_assume_role[count.index].json
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
    # https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html#ecr-required-iam-permissions
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
      "*" // It is required to set this * to make this work
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
      "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:pds/nucleus/opensearch/creds/*",
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
      "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:pds/nucleus/opensearch/creds/*",
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
  name                 = "pds-nucleus-archive-replication-role"
  assume_role_policy   = data.aws_iam_policy_document.pds_nucleus_archive_replication_assume_role.json
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
      "*" // This is required for MWAA (https://docs.aws.amazon.com/mwaa/latest/userguide/mwaa-create-role.html)
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
      values   = ["sqs.${var.region}.amazonaws.com"]
    }
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:DescribeLogGroups"
    ]
    resources = [
      "*" // This is required for MWAA (https://docs.aws.amazon.com/mwaa/latest/userguide/mwaa-create-role.html)
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
      "arn:aws:s3:::${var.mwaa_dag_s3_bucket_name}",
      "arn:aws:s3:::${var.mwaa_dag_s3_bucket_name}/*"
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
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:airflow-${var.airflow_env_name}-*",
      "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/pds/ecs/*:log-stream:ecs/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "iam:PassRole"
    ]
    resources = [
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/pds_nucleus_ecs_task_role-*",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/pds_nucleus_harvest_ecs_task_role-*",
      "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/pds_nucleus_ecs_task_execution_role"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "lambda:InvokeFunction"
    ]
    resources = [
      "arn:aws:lambda:${var.region}:${data.aws_caller_identity.current.account_id}:function:pds_nucleus_product_processing_status_tracker"
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

  count = length(var.pds_node_names)

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:CreateLogGroup",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:*:log-stream:*",
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
      "s3:List*"
    ]
    resources = [
      "arn:aws:s3:::pds-*-staging*",
      "arn:aws:s3:::pds-*-staging*/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:PutObject"
    ]
    resources = [
      "arn:aws:s3:::${lower(replace(var.pds_node_names[count.index], "_", "-"))}-config*/*",
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
  count = length(var.pds_node_names)

  name = "pds_nucleus_lambda_execution_role-${var.pds_node_names[count.index]}"
  inline_policy {
    name   = "pds-nucleus-lambda-execution-inline-policy"
    policy = data.aws_iam_policy_document.lambda_inline_policy[count.index].json
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

output "pds_nucleus_ecs_task_role_arns" {
  value = aws_iam_role.pds_nucleus_ecs_task_role.*.arn
}

output "pds_nucleus_harvest_ecs_task_role_arns" {
  value = aws_iam_role.pds_nucleus_harvest_ecs_task_role.*.arn
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

output "pds_nucleus_lambda_execution_role_arns" {
  value = aws_iam_role.pds_nucleus_lambda_execution_role.*.arn
}
