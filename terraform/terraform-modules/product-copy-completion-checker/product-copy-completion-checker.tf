# Terraform script to setup the PDS Product Copy Completion Checker

resource "random_password" "pds_nucleus_rds_password" {
  length  = 16
  special = false
}

resource "aws_db_subnet_group" "default" {
  name       = "main"
  subnet_ids = var.subnet_ids
}

resource "random_string" "random_secret_postfix" {
  length  = 8
  special = false
}

resource "aws_secretsmanager_secret" "pds_nucleus_rds_password" {
  name                    = "pds/nucleus/rds/password/${random_string.random_secret_postfix.result}"
  description             = "PDS Nucleus Database Password"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "pds_nucleus_rds_password" {
  secret_id     = aws_secretsmanager_secret.pds_nucleus_rds_password.id
  secret_string = random_password.pds_nucleus_rds_password.result
}

resource "aws_rds_cluster" "default" {
  cluster_identifier           = "pdsnucleus"
  engine                       = "aurora-mysql"
  engine_version               = "5.7.mysql_aurora.2.03.2"
  availability_zones  = var.database_availability_zones
  db_subnet_group_name         = aws_db_subnet_group.default.id
  database_name                = var.database_name
  master_username              = var.database_user
  master_password              = aws_secretsmanager_secret_version.pds_nucleus_rds_password.secret_string
  backup_retention_period      = 5
  preferred_backup_window      = "07:00-09:00"
  preferred_maintenance_window = "Mon:00:00-Mon:02:00"
  storage_encrypted            = true
  enable_http_endpoint         = true
  backtrack_window             = 0
  skip_final_snapshot          = true

  # Configuring aurora serverless
  engine_mode = "serverless"
  scaling_configuration {
    auto_pause               = false
    max_capacity             = 2
    min_capacity             = 1
    seconds_until_auto_pause = 600
  }
}

resource "aws_secretsmanager_secret" "pds_nucleus_rds_credentials" {
  name                    = "pds/nucleus/rds/creds/${random_string.random_secret_postfix.result}"
  description             = "PDS Nucleus Database Credentials"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "rds_credentials" {
  secret_id     = aws_secretsmanager_secret.pds_nucleus_rds_credentials.id
  secret_string = <<EOF
{
  "username": "${aws_rds_cluster.default.master_username}",
  "password": "${random_password.pds_nucleus_rds_password.result}",
  "engine": "mysql",
  "host": "${aws_rds_cluster.default.endpoint}",
  "port": ${aws_rds_cluster.default.port},
  "dbClusterIdentifier": "${aws_rds_cluster.default.cluster_identifier}"
}
EOF
}

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

data "aws_iam_policy" "mcp_operator_policy" {
  name = var.permission_boundary_for_iam_roles
}

data "aws_iam_policy_document" "assume_role_lambda_apigw" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com", "apigateway.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

data "aws_iam_policy_document" "inline_policy_lambda" {
  statement {
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "lambda:InvokeFunction",
      "rds-data:ExecuteStatement",
      "secretsmanager:GetSecretValue",
      "s3:GetObject",
      "s3:PutObject",
      "airflow:CreateCliToken"
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role" "pds_nucleus_lambda_execution_role" {
  name = "pds_nucleus_lambda_execution_role"
  inline_policy {
    name   = "unity-cs-lambda-auth-inline-policy"
    policy = data.aws_iam_policy_document.inline_policy_lambda.json
  }
  assume_role_policy   = data.aws_iam_policy_document.assume_role_lambda_apigw.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}

data "archive_file" "pds_nucleus_s3_file_file_event_processor_function_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/pds-nucleus-s3-file-event-processor.py"
  output_path = "${path.module}/lambda/pds-nucleus-s3-file-event-processor.zip"
}



data "archive_file" "pds_nucleus_product_completion_checker_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/pds-nucleus-product-completion-checker.py"
  output_path = "${path.module}/lambda/pds_nucleus_product_completion_checker.zip"
}

data "archive_file" "pds_nucleus_init_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/pds-nucleus-init.py"
  output_path = "${path.module}/lambda/pds_nucleus_init.zip"
}

resource "aws_lambda_function" "pds_nucleus_init_function" {
  function_name    = "pds-nucleus-init2"
  filename         = "${path.module}/lambda/pds_nucleus_init.zip"
  source_code_hash = data.archive_file.pds_nucleus_init_zip.output_base64sha256
  role             = aws_iam_role.pds_nucleus_lambda_execution_role.arn
  runtime          = "python3.9"
  handler          = "pds-nucleus-init.lambda_handler"
  timeout          = 10
  depends_on       = [data.archive_file.pds_nucleus_init_zip]

  environment {
    variables = {
      DB_CLUSTER_ARN = aws_rds_cluster.default.arn
      DB_SECRET_ARN  = aws_secretsmanager_secret.pds_nucleus_rds_credentials.arn
    }
  }

}
resource "aws_s3_bucket" "pds_nucleus_s3_config_bucket" {
  bucket        = var.pds_nucleus_config_bucket_name
  force_destroy = true
}

# Create an S3 Bucket for each PDS Node
resource "aws_s3_bucket" "pds_nucleus_s3_staging_bucket" {
  count = length(var.pds_node_names)
  bucket = "${var.pds_node_names[count.index]}-${var.pds_nucleus_staging_bucket_name_postfix}"
  force_destroy = true
}


# Create pds_nucleus_s3_file_file_event_processor_function for each PDS Node
resource "aws_lambda_function" "pds_nucleus_s3_file_file_event_processor_function" {
  count = length(var.pds_node_names)
  function_name    = "pds_nucleus_s3_file_event_processor-${var.pds_node_names[count.index]}"
  filename         = "${path.module}/lambda/pds-nucleus-s3-file-event-processor.zip"
  source_code_hash = data.archive_file.pds_nucleus_s3_file_file_event_processor_function_zip.output_base64sha256
  role             = aws_iam_role.pds_nucleus_lambda_execution_role.arn
  runtime          = "python3.9"
  handler          = "pds-nucleus-s3-file-event-processor.lambda_handler"
  timeout          = 10
  depends_on       = [data.archive_file.pds_nucleus_s3_file_file_event_processor_function_zip]

  environment {
    variables = {
      DB_CLUSTER_ARN = aws_rds_cluster.default.arn
      DB_SECRET_ARN  = aws_secretsmanager_secret.pds_nucleus_rds_credentials.arn
      EFS_MOUNT_PATH = "/mnt/data/"
      PDS_NODE       = var.pds_node_names[count.index]
    }
  }
}

# Create pds_nucleus_product_completion_checker_function for each PDS Node
resource "aws_lambda_function" "pds_nucleus_product_completion_checker_function" {
  count = length(var.pds_node_names)
  function_name    = "pds-nucleus-product-completion-checker-${var.pds_node_names[count.index]}"
  filename         = "${path.module}/lambda/pds_nucleus_product_completion_checker.zip"
  source_code_hash = data.archive_file.pds_nucleus_product_completion_checker_zip.output_base64sha256
  role             = aws_iam_role.pds_nucleus_lambda_execution_role.arn
  runtime          = "python3.9"
  handler          = "pds-nucleus-product-completion-checker.lambda_handler"
  timeout          = 10
  depends_on       = [data.archive_file.pds_nucleus_product_completion_checker_zip]

  environment {
    variables = {
      AIRFLOW_DAG_NAME               = var.pds_nucleus_default_airflow_dag_id
      DB_CLUSTER_ARN                 = aws_rds_cluster.default.arn
      DB_SECRET_ARN                  = aws_secretsmanager_secret.pds_nucleus_rds_credentials.arn
      EFS_MOUNT_PATH                 = "/mnt/data"
      ES_AUTH_CONFIG_FILE_PATH       = var.pds_nucleus_opensearch_auth_config_file_paths[count.index]
      ES_URL                         = var.pds_nucleus_opensearch_urls[count.index]
      NODE_NAME                      = var.pds_node_names[count.index]
      PDS_NUCLEUS_CONFIG_BUCKET_NAME = var.pds_nucleus_config_bucket_name
      REPLACE_PREFIX_WITH            = var.pds_nucleus_harvest_replace_prefix_with_list[count.index]
      PDS_MWAA_ENV_NAME              = var.airflow_env_name
    }
  }
}

# Apply lambda permissions for each pds_nucleus_s3_file_file_event_processor_function of each Node
resource "aws_lambda_permission" "s3-lambda-permission" {
  count = length(var.pds_node_names)
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pds_nucleus_s3_file_file_event_processor_function[count.index].function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.pds_nucleus_s3_staging_bucket[count.index].arn
}

# Creat  aws_s3_bucket_notification for each s3 bucket nof each Node
resource "aws_s3_bucket_notification" "pds_nucleus_s3_staging_bucket_notification" {

  count = length(var.pds_node_names)

  bucket = "${var.pds_node_names[count.index]}-${var.pds_nucleus_staging_bucket_name_postfix}"

  lambda_function {
    lambda_function_arn = aws_lambda_function.pds_nucleus_s3_file_file_event_processor_function[count.index].arn
    events              = ["s3:ObjectCreated:*"]
  }
}

resource "aws_lambda_invocation" "invoke_pds_nucleus_init_function" {
  function_name = aws_lambda_function.pds_nucleus_init_function.function_name

  input = ""

  lifecycle {
    replace_triggered_by = [
      aws_rds_cluster.default.id
    ]
  }

  depends_on = [aws_lambda_function.pds_nucleus_init_function, aws_rds_cluster.default]
}
