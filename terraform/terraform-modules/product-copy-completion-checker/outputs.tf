output "pds_nucleus_files_to_save_in_database_sqs_queue_urls" {
  description = "SQS queue URL (used to register files in the database) for each data source, indexed the same as var.pds_data_source_names"
  value       = aws_sqs_queue.pds_nucleus_files_to_save_in_database_sqs_queue[*].url
}
