# Terraform script to setup the PDS Product Copy Completion Checker

resource "aws_dynamodb_table" "received_data_files" {
  name           = "received_data_files"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "s3_url_of_data_file"

  attribute {
    name = "s3_url_of_data_file"
    type = "S"
  }
}

resource "aws_dynamodb_table" "expected_data_files" {
  name           = "expected_data_files"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "s3_url_of_data_file"

  attribute {
    name = "s3_url_of_data_file"
    type = "S"
  }
}

resource "aws_dynamodb_table" "incomplete_products" {
  name           = "incomplete_products"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "s3_url_of_product_label"

  attribute {
    name = "s3_url_of_product_label"
    type = "S"
  }
}

resource "aws_sqs_queue" "pds-nucleus-ready-to-process-products" {
  name                      = "pds-nucleus-ready-to-process-products"
  delay_seconds             = 90
  max_message_size          = 2048
  message_retention_seconds = 86400
  receive_wait_time_seconds = 10
}
