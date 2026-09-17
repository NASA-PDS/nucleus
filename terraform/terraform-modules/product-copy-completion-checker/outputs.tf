output "pds_nucleus_files_to_save_in_database_sqs_queue_urls" {
  description = "SQS queue URL (used to register files in the database) for each data source, indexed the same as var.pds_data_source_names"
  value       = aws_sqs_queue.pds_nucleus_files_to_save_in_database_sqs_queue[*].url
}

output "pds_nucleus_rds_cluster_arn" {
  description = "Aurora cluster ARN, for consumers (e.g. the validate-and-harvest DAG) that write to product_tracking via the RDS Data API"
  value       = aws_rds_cluster.default.arn
}

output "pds_nucleus_rds_secret_arn" {
  description = "RDS credentials secret ARN, for consumers (e.g. the validate-and-harvest DAG) that write to product_tracking via the RDS Data API"
  value       = aws_secretsmanager_secret.pds_nucleus_rds_credentials.arn
}

output "pds_nucleus_rds_readonly_secret_arn" {
  description = "SELECT-only RDS credentials secret ARN, for the /nucleus/products search page (cognito-auth module) -- never the master secret"
  value       = aws_secretsmanager_secret.pds_nucleus_readonly_db_credentials.arn
}
