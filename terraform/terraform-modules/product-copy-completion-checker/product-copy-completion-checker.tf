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
  cluster_identifier           = var.rds_cluster_id
  engine                       = "aurora-mysql"
  engine_mode                  = "provisioned"
  engine_version               = "8.0.mysql_aurora.3.08.0"
  availability_zones           = var.database_availability_zones
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
  vpc_security_group_ids       = [var.nucleus_security_group_id]

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 128.0
  }

  lifecycle {
    ignore_changes = [availability_zones]
  }
}

resource "aws_rds_cluster_instance" "rds_cluster_instance" {
  identifier         = var.rds_cluster_id
  cluster_identifier = aws_rds_cluster.default.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.default.engine
  engine_version     = aws_rds_cluster.default.engine_version
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
  function_name    = "pds-nucleus-init"
  filename         = "${path.module}/lambda/pds_nucleus_init.zip"
  source_code_hash = data.archive_file.pds_nucleus_init_zip.output_base64sha256
  role             = var.pds_nucleus_lambda_execution_role_arns[0]
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
  count  = length(var.pds_node_names)
  bucket = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_nucleus_config_bucket_name_postfix}"
  force_destroy = true
}

# This data source is added to access existing S3 buckets, bcause an S3 staging bucket is already available in MCP Prod environment.
data "aws_s3_bucket" "pds_nucleus_s3_staging_bucket" {
  count  = length(var.pds_node_names)
  bucket = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_nucleus_staging_bucket_name_postfix}"
}

# Commented out the following S3 bucket resources, because an S3 staging bucket is already available in MCP Prod environment.
# However, this resource is useful when deploying in a fresh environment.

# # Create a staging S3 Bucket for each PDS Node
# resource "aws_s3_bucket" "pds_nucleus_s3_staging_bucket" {
#   count = length(var.pds_node_names)
#   # convert PDS node name to S3 bucket name compatible format
#   bucket = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_nucleus_staging_bucket_name_postfix}"
# }

# # Create an aws_s3_bucket_notification for each s3 bucket of each Node
# resource "aws_s3_bucket_notification" "pds_nucleus_s3_staging_bucket_notification" {
#
#   count = length(var.pds_node_names)
#   # convert PDS node name to S3 bucket name compatible format
#   bucket = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_nucleus_staging_bucket_name_postfix}"
#
#   queue {
#     events    = ["s3:ObjectCreated:*"]
#     queue_arn = aws_sqs_queue.pds_nucleus_files_to_save_in_database_sqs_queue[count.index].arn
#   }
# }


# Create pds_nucleus_s3_file_file_event_processor_function for each PDS Node
resource "aws_lambda_function" "pds_nucleus_s3_file_file_event_processor_function" {
  count            = length(var.pds_node_names)
  function_name    = "pds_nucleus_s3_file_event_processor-${var.pds_node_names[count.index]}"
  filename         = "${path.module}/lambda/pds-nucleus-s3-file-event-processor.zip"
  source_code_hash = data.archive_file.pds_nucleus_s3_file_file_event_processor_function_zip.output_base64sha256
  role             = var.pds_nucleus_lambda_execution_role_arns[count.index]
  runtime          = "python3.9"
  handler          = "pds-nucleus-s3-file-event-processor.lambda_handler"
  timeout          = 300
  depends_on       = [data.archive_file.pds_nucleus_s3_file_file_event_processor_function_zip]

  environment {
    variables = {
      DB_CLUSTER_ARN = aws_rds_cluster.default.arn
      DB_SECRET_ARN  = aws_secretsmanager_secret.pds_nucleus_rds_credentials.arn
      EFS_MOUNT_PATH = "/mnt/data/"
      PDS_NODE_NAME  = var.pds_node_names[count.index]
    }
  }
}

# Create SQS queue event source for pds_nucleus_s3_file_file_event_processor_function for each PDS Node
resource "aws_lambda_event_source_mapping" "event_source_mapping" {
  count            = length(var.pds_node_names)
  event_source_arn = aws_sqs_queue.pds_nucleus_files_to_save_in_database_sqs_queue[count.index].arn
  enabled          = true
  function_name    = aws_lambda_function.pds_nucleus_s3_file_file_event_processor_function[count.index].function_name
  batch_size       = 1
}

# Create pds_nucleus_product_completion_checker_function for each PDS Node
resource "aws_lambda_function" "pds_nucleus_product_completion_checker_function" {
  count            = length(var.pds_node_names)
  function_name    = "pds-nucleus-product-completion-checker-${var.pds_node_names[count.index]}"
  filename         = "${path.module}/lambda/pds_nucleus_product_completion_checker.zip"
  source_code_hash = data.archive_file.pds_nucleus_product_completion_checker_zip.output_base64sha256
  role             = var.pds_nucleus_lambda_execution_role_arns[count.index]
  runtime          = "python3.12"
  handler          = "pds-nucleus-product-completion-checker.lambda_handler"
  timeout          = 300
  depends_on       = [data.archive_file.pds_nucleus_product_completion_checker_zip]

  environment {
    variables = {
      AIRFLOW_DAG_NAME                   = "${var.pds_node_names[count.index]}-${var.pds_nucleus_default_airflow_dag_id}"
      DB_CLUSTER_ARN                     = aws_rds_cluster.default.arn
      DB_SECRET_ARN                      = aws_secretsmanager_secret.pds_nucleus_rds_credentials.arn
      EFS_MOUNT_PATH                     = "/mnt/data"
      ES_AUTH_CONFIG_FILE_PATH           = "/etc/es-auth.cfg"
      OPENSEARCH_ENDPOINT                = var.pds_nucleus_opensearch_url
      OPENSEARCH_REGISTRY_NAME           = var.pds_nucleus_opensearch_registry_names[count.index]
      OPENSEARCH_CREDENTIAL_RELATIVE_URL = var.pds_nucleus_opensearch_credential_relative_url
      PDS_NODE_NAME                      = var.pds_node_names[count.index]
      PDS_NUCLEUS_CONFIG_BUCKET_NAME     = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_nucleus_config_bucket_name_postfix}"
      REPLACE_PREFIX_WITH                = var.pds_nucleus_harvest_replace_prefix_with_list[count.index]
      PDS_MWAA_ENV_NAME                  = var.airflow_env_name
      PDS_HOT_ARCHIVE_S3_BUCKET_NAME     = var.pds_archive_bucket_names[count.index]
      PRODUCT_BATCH_SIZE                 = var.product_batch_size
    }
  }
}

resource "aws_cloudwatch_event_rule" "every_one_minute" {
  name                = "pds-nucleus-every-one-minutes"
  description         = "Fires every one minute"
  schedule_expression = "rate(1 minute)"
}

resource "aws_cloudwatch_event_target" "check_product_completion_event_target" {
  count = length(var.pds_node_names)

  rule      = aws_cloudwatch_event_rule.every_one_minute.name
  target_id = "pds-nucleus-check-product-completion-event-target-${var.pds_node_names[count.index]}"
  arn       = aws_lambda_function.pds_nucleus_product_completion_checker_function[count.index].arn
}

resource "aws_lambda_permission" "allow_cloudwatch_to_call_product_completion_checker_function" {
  count = length(var.pds_node_names)

  statement_id  = "AllowExecutionFromCloudWatch"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pds_nucleus_product_completion_checker_function[count.index].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.every_one_minute.arn
}

# Apply lambda permissions for each pds_nucleus_s3_file_file_event_processor_function of each Node
resource "aws_lambda_permission" "s3-lambda-permission" {
  count         = length(var.pds_node_names)
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pds_nucleus_s3_file_file_event_processor_function[count.index].function_name
  principal     = "s3.amazonaws.com"
  source_arn    = data.aws_s3_bucket.pds_nucleus_s3_staging_bucket[count.index].arn
}

# Create an SQS queue to receive S3 bucket notifications for each s3 bucket of each Node
resource "aws_sqs_queue" "pds_nucleus_files_to_save_in_database_sqs_queue" {
  count                      = length(var.pds_node_names)
  name                       = "pds-nucleus-files-to-save-in-database-${var.pds_node_names[count.index]}"
  delay_seconds              = 0
  visibility_timeout_seconds = 300
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 0
  sqs_managed_sse_enabled    = true
}

# Create an SQS policy document for SQS queue of each Node
data "aws_iam_policy_document" "pds_nucleus_files_to_save_in_database_sqs_queue_policy_document" {
  count = length(var.pds_node_names)

  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.pds_nucleus_files_to_save_in_database_sqs_queue[count.index].arn]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = [data.aws_s3_bucket.pds_nucleus_s3_staging_bucket[count.index].arn]
    }
  }
}

# Create an SQS policy for SQS queue of each Node
resource "aws_sqs_queue_policy" "pds_nucleus_files_to_save_in_database_sqs_queue_policy" {
  count     = length(var.pds_node_names)
  queue_url = aws_sqs_queue.pds_nucleus_files_to_save_in_database_sqs_queue[count.index].url
  policy    = data.aws_iam_policy_document.pds_nucleus_files_to_save_in_database_sqs_queue_policy_document[count.index].json
}

resource "time_sleep" "wait_for_database" {
  create_duration = "2m"

  depends_on = [aws_rds_cluster_instance.rds_cluster_instance]
}

resource "aws_lambda_invocation" "invoke_pds_nucleus_init_function" {
  function_name = aws_lambda_function.pds_nucleus_init_function.function_name

  input = ""

  lifecycle {
    replace_triggered_by = [
      aws_rds_cluster.default.id
    ]
  }

  depends_on = [aws_lambda_function.pds_nucleus_init_function, aws_rds_cluster.default, aws_rds_cluster_instance.rds_cluster_instance, time_sleep.wait_for_database]
}


data "archive_file" "pds_nucleus_product_processing_status_tracker_function_zip" {
  type        = "zip"
  source_file = "${path.module}/lambda/pds-nucleus-product-processing-status-tracker.py"
  output_path = "${path.module}/lambda/pds-nucleus-product-processing-status-tracker.zip"
}

# Create pds_nucleus_product_processing_status_tracker_function for each PDS Node
resource "aws_lambda_function" "pds_nucleus_product_processing_status_tracker_function" {
  function_name    = "pds_nucleus_product_processing_status_tracker"
  filename         = "${path.module}/lambda/pds-nucleus-product-processing-status-tracker.zip"
  source_code_hash = data.archive_file.pds_nucleus_product_processing_status_tracker_function_zip.output_base64sha256
  role             = var.pds_nucleus_lambda_execution_role_arns[0]
  runtime          = "python3.12"
  handler          = "pds-nucleus-product-processing-status-tracker.lambda_handler"
  timeout          = 10
  depends_on       = [data.archive_file.pds_nucleus_product_processing_status_tracker_function_zip]

  environment {
    variables = {
      DB_CLUSTER_ARN = aws_rds_cluster.default.arn
      DB_SECRET_ARN  = aws_secretsmanager_secret.pds_nucleus_rds_credentials.arn
    }
  }
}

# Create CloudWatch Log Group for pds_nucleus_s3_file_file_event_processor_function for each PDS Node
resource "aws_cloudwatch_log_group" "pds_nucleus_product_processing_status_tracker_function_log_group" {
  name = "/aws/lambda/pds_nucleus_product_processing_status_tracker"
}
