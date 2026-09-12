# Terraform script to setup the PDS Product Copy Completion Checker

# Node-scoped lookup maps, keyed by node name. These reference config that is
# shared across all data sources of a node (IAM role, DB, OpenSearch, harvest
# prefixes, archive bucket) WITHOUT creating/modifying any IAM resources —
# pds_nucleus_lambda_execution_role_arns still comes from the existing IAM
# module output, indexed by the untouched var.pds_node_names order.
locals {
  node_role_arn_map = zipmap(var.pds_node_names, var.pds_nucleus_lambda_execution_role_arns)
  node_archive_bucket_map = zipmap(var.pds_node_names, var.pds_archive_bucket_names)
  node_opensearch_registry_map = zipmap(var.pds_node_names, var.pds_nucleus_opensearch_registry_names)
  # Populated below, after the data.aws_s3_bucket.pds_nucleus_s3_staging_bucket data source is declared.
  node_staging_bucket_arn_map = zipmap(var.pds_node_names, data.aws_s3_bucket.pds_nucleus_s3_staging_bucket[*].arn)
  # Populated below, after aws_s3_bucket.pds_nucleus_s3_config_bucket is declared. Config bucket is
  # shared per node (not per data source) to keep the original IAM S3 resource pattern intact.
  node_config_bucket_name_map = zipmap(var.pds_node_names, aws_s3_bucket.pds_nucleus_s3_config_bucket[*].bucket)
}

resource "random_password" "pds_nucleus_rds_password" {
  length  = 16
  special = false
}

resource "aws_db_subnet_group" "default" {
  name       = "main"
  subnet_ids = var.subnet_ids
  
  tags = var.tags
}

resource "random_string" "random_secret_postfix" {
  length  = 8
  special = false
}

resource "aws_rds_cluster" "default" {
  cluster_identifier           = var.rds_cluster_id
  engine                       = "aurora-mysql"
  engine_mode                  = "provisioned"
  engine_version               = var.aws_rds_cluster_engine_version
  availability_zones           = var.database_availability_zones
  db_subnet_group_name         = aws_db_subnet_group.default.id
  # Bootstrap default database required by Aurora at cluster creation time.
  # Lambdas do not use this database — each PDS node has its own dedicated
  # database (pds_nucleus_<node>) created by pds-nucleus-init at deploy time.
  database_name                = var.database_name
  master_username              = var.database_user
  master_password              = random_password.pds_nucleus_rds_password.result
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
  
  tags = var.tags
}

resource "aws_rds_cluster_instance" "rds_cluster_instance" {
  identifier         = var.rds_cluster_id
  cluster_identifier = aws_rds_cluster.default.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.default.engine
  engine_version     = aws_rds_cluster.default.engine_version
  
  tags = var.tags
}

resource "aws_secretsmanager_secret" "pds_nucleus_rds_credentials" {
  name                    = "pds/nucleus/rds/creds/${random_string.random_secret_postfix.result}"
  description             = "PDS Nucleus Database Credentials"
  recovery_window_in_days = 0
  tags                    = var.tags
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
  runtime          = var.lambda_runtime
  handler          = "pds-nucleus-init.lambda_handler"
  timeout          = 60
  depends_on       = [data.archive_file.pds_nucleus_init_zip]

  environment {
    variables = {
      DB_CLUSTER_ARN = aws_rds_cluster.default.arn
      DB_SECRET_ARN  = aws_secretsmanager_secret.pds_nucleus_rds_credentials.arn
    }
  }
  
  tags = var.tags
}

# Config bucket stays per-node (shared, matches original IAM S3 resource pattern "${node}-conf*") —
# data sources are isolated via an S3 key prefix ("dag-data/<data_source>/<batch>") instead of a
# separate bucket, so no IAM policy changes are needed for per-data-source access.
resource "aws_s3_bucket" "pds_nucleus_s3_config_bucket" {
  count         = length(var.pds_node_names)
  bucket        = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_nucleus_config_bucket_name_postfix}"
  force_destroy = true
  
  tags = var.tags
}

# This data source is added to access existing S3 buckets, because an S3 staging bucket is already available in MCP Prod environment.
# Staging bucket stays per-node (NOT per data source, because data sources can be backlog locations too)
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


# Create pds_nucleus_s3_file_file_event_processor_function for each data source (IAM role shared per node via local.node_role_arn_map — no IAM created/modified here)
resource "aws_lambda_function" "pds_nucleus_s3_file_file_event_processor_function" {
  count            = length(var.pds_data_source_names)
  # Short prefix to stay under the AWS Lambda 64-character function name limit
  # once the node/data-source names are appended.
  function_name    = "pds-nucleus-s3-watch-${var.pds_data_source_node_names[count.index]}-${var.pds_data_source_names[count.index]}"
  filename         = "${path.module}/lambda/pds-nucleus-s3-file-event-processor.zip"
  source_code_hash = data.archive_file.pds_nucleus_s3_file_file_event_processor_function_zip.output_base64sha256
  role             = local.node_role_arn_map[var.pds_data_source_node_names[count.index]]
  runtime          = var.lambda_runtime
  handler          = "pds-nucleus-s3-file-event-processor.lambda_handler"
  timeout          = 900
  memory_size      = 1024
  depends_on       = [data.archive_file.pds_nucleus_s3_file_file_event_processor_function_zip]

  environment {
    variables = {
      DB_CLUSTER_ARN = aws_rds_cluster.default.arn
      DB_SECRET_ARN  = aws_secretsmanager_secret.pds_nucleus_rds_credentials.arn
      DB_NAME              = "pds_nucleus_${lower(var.pds_data_source_node_names[count.index])}_${lower(var.pds_data_source_names[count.index])}"
      EFS_MOUNT_PATH       = "/mnt/data/"
      PDS_NODE_NAME        = var.pds_data_source_node_names[count.index]
      PDS_DATA_SOURCE_NAME = var.pds_data_source_names[count.index]
    }
  }

  tags = var.tags
}

# Create SQS queue event source for pds_nucleus_s3_file_file_event_processor_function for each data source
resource "aws_lambda_event_source_mapping" "event_source_mapping" {
  count                                = length(var.pds_data_source_names)
  event_source_arn                     = aws_sqs_queue.pds_nucleus_files_to_save_in_database_sqs_queue[count.index].arn
  enabled                              = true
  function_name                        = aws_lambda_function.pds_nucleus_s3_file_file_event_processor_function[count.index].function_name
  batch_size                           = 100
  maximum_batching_window_in_seconds   = 1
  function_response_types              = ["ReportBatchItemFailures"]
}

# Create pds_nucleus_product_completion_checker_function for each data source (IAM role/DB/OpenSearch/archive bucket shared per node — no IAM created/modified here)
resource "aws_lambda_function" "pds_nucleus_product_completion_checker_function" {
  count            = length(var.pds_data_source_names)
  # Short prefix to stay under the AWS Lambda 64-character function name limit
  # once the node/data-source names are appended.
  function_name    = "pds-nucleus-prod-cmpl-chk-${var.pds_data_source_node_names[count.index]}-${var.pds_data_source_names[count.index]}"
  filename         = "${path.module}/lambda/pds_nucleus_product_completion_checker.zip"
  source_code_hash = data.archive_file.pds_nucleus_product_completion_checker_zip.output_base64sha256
  role             = local.node_role_arn_map[var.pds_data_source_node_names[count.index]]
  runtime          = var.lambda_runtime
  handler          = "pds-nucleus-product-completion-checker.lambda_handler"
  timeout          = 900
  memory_size      = 256
  depends_on       = [data.archive_file.pds_nucleus_product_completion_checker_zip]

  environment {
    variables = {
      AIRFLOW_DAG_NAME                   = "${var.pds_data_source_node_names[count.index]}_${var.pds_data_source_names[count.index]}-${var.pds_nucleus_default_airflow_dag_id}"
      DB_CLUSTER_ARN                     = aws_rds_cluster.default.arn
      DB_SECRET_ARN                      = aws_secretsmanager_secret.pds_nucleus_rds_credentials.arn
      DB_NAME                            = "pds_nucleus_${lower(var.pds_data_source_node_names[count.index])}_${lower(var.pds_data_source_names[count.index])}"
      EFS_MOUNT_PATH                     = "/mnt/data"
      ES_AUTH_CONFIG_FILE_PATH           = "/etc/es-auth.cfg"
      OPENSEARCH_ENDPOINT                = var.pds_nucleus_opensearch_url
      OPENSEARCH_REGISTRY_NAME           = local.node_opensearch_registry_map[var.pds_data_source_node_names[count.index]]
      OPENSEARCH_CREDENTIAL_RELATIVE_URL = var.pds_nucleus_opensearch_credential_relative_url
      PDS_NODE_NAME                      = var.pds_data_source_node_names[count.index]
      PDS_DATA_SOURCE_NAME               = var.pds_data_source_names[count.index]
      PDS_NUCLEUS_CONFIG_BUCKET_NAME     = local.node_config_bucket_name_map[var.pds_data_source_node_names[count.index]]
      REPLACE_PREFIX_WITH                = var.pds_nucleus_harvest_replace_prefix_with_list[count.index]
      HARVEST_REPLACE_PREFIX             = var.pds_nucleus_harvest_replace_prefix_list[count.index]
      PDS_MWAA_ENV_NAME                  = var.airflow_env_name
      PDS_HOT_ARCHIVE_S3_BUCKET_NAME     = local.node_archive_bucket_map[var.pds_data_source_node_names[count.index]]
      PRODUCT_BATCH_SIZE                 = var.product_batch_size
    }
  }
  
  tags = var.tags
}

# One EventBridge scheduled rule per data source (not shared), so each data source's completion checker runs on its own rule.
resource "aws_cloudwatch_event_rule" "every_one_minute" {
  count               = length(var.pds_data_source_names)
  # Short prefix to stay under the AWS EventBridge 64-character rule name limit
  # once the node/data-source names are appended.
  name                = "pds-nucleus-minute-${var.pds_data_source_node_names[count.index]}-${var.pds_data_source_names[count.index]}"
  description         = "Fires every one minute for ${var.pds_data_source_node_names[count.index]} - ${var.pds_data_source_names[count.index]}"
  schedule_expression = "rate(1 minute)"
  state               = "DISABLED"

  tags = var.tags
}

resource "aws_cloudwatch_event_target" "check_product_completion_event_target" {
  count = length(var.pds_data_source_names)

  rule      = aws_cloudwatch_event_rule.every_one_minute[count.index].name
  # target_id has a 64-character AWS limit — use a short prefix instead of the full descriptive name.
  target_id = "pds-nucleus-pcc-${var.pds_data_source_node_names[count.index]}-${var.pds_data_source_names[count.index]}"
  arn       = aws_lambda_function.pds_nucleus_product_completion_checker_function[count.index].arn
}

resource "aws_lambda_permission" "allow_cloudwatch_to_call_product_completion_checker_function" {
  count = length(var.pds_data_source_names)

  statement_id  = "AllowExecutionFromCloudWatch-${var.pds_data_source_node_names[count.index]}-${var.pds_data_source_names[count.index]}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pds_nucleus_product_completion_checker_function[count.index].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.every_one_minute[count.index].arn
}

# Apply lambda permissions for each pds_nucleus_s3_file_file_event_processor_function of each data source
resource "aws_lambda_permission" "s3-lambda-permission" {
  count         = length(var.pds_data_source_names)
  statement_id  = "AllowExecutionFromS3Bucket-${var.pds_data_source_node_names[count.index]}-${var.pds_data_source_names[count.index]}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.pds_nucleus_s3_file_file_event_processor_function[count.index].function_name
  principal     = "s3.amazonaws.com"
  source_arn    = local.node_staging_bucket_arn_map[var.pds_data_source_node_names[count.index]]
}

# Create an SQS queue to receive S3 bucket notifications for each s3 bucket of each data source
resource "aws_sqs_queue" "pds_nucleus_files_to_save_in_database_sqs_queue" {
  count                      = length(var.pds_data_source_names)
  # Queue name ends with the node name (data source placed before it) to match the existing
  # ECS task role IAM SQS resource pattern "pds-nucleus-*-<node>" without any IAM changes.
  # Short prefix to stay well under the AWS SQS 80-character queue name limit
  # once the data-source/node names are appended.
  name                       = "pds-nucleus-file-save-${var.pds_data_source_names[count.index]}-${var.pds_data_source_node_names[count.index]}"
  delay_seconds              = 0
  visibility_timeout_seconds = 300
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 0
  sqs_managed_sse_enabled    = true
  
  tags = var.tags
}

# Create an SQS policy document for SQS queue of each data source
data "aws_iam_policy_document" "pds_nucleus_files_to_save_in_database_sqs_queue_policy_document" {
  count = length(var.pds_data_source_names)

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
      values   = [local.node_staging_bucket_arn_map[var.pds_data_source_node_names[count.index]]]
    }
  }
}

# Create an SQS policy for SQS queue of each data source
resource "aws_sqs_queue_policy" "pds_nucleus_files_to_save_in_database_sqs_queue_policy" {
  count     = length(var.pds_data_source_names)
  queue_url = aws_sqs_queue.pds_nucleus_files_to_save_in_database_sqs_queue[count.index].url
  policy    = data.aws_iam_policy_document.pds_nucleus_files_to_save_in_database_sqs_queue_policy_document[count.index].json
}

resource "time_sleep" "wait_for_database" {
  create_duration = "2m"

  depends_on = [aws_rds_cluster_instance.rds_cluster_instance]
}

resource "aws_lambda_invocation" "invoke_pds_nucleus_init_function" {
  count         = length(var.pds_data_source_names)
  function_name = aws_lambda_function.pds_nucleus_init_function.function_name

  input = jsonencode({
    pds_node_name         = var.pds_data_source_node_names[count.index]
    pds_data_source_name  = var.pds_data_source_names[count.index]
  })

  lifecycle {
    replace_triggered_by = [
      aws_rds_cluster.default.id,
      aws_lambda_function.pds_nucleus_init_function
    ]
  }

  depends_on = [aws_lambda_function.pds_nucleus_init_function, aws_rds_cluster.default, aws_rds_cluster_instance.rds_cluster_instance, time_sleep.wait_for_database]
}
