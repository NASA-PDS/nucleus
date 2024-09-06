# Terraform script to create the PDS archive related resources

# Create a cold archive for each PDS Node
resource "aws_s3_bucket" "pds_nucleus_cold_archive" {
  count = length(var.pds_node_names)
  # convert PDS node name to S3 bucket name compatible format
  bucket = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_nucleus_cold_archive_bucket_name_postfix}"
}

resource "aws_s3_bucket_versioning" "pds_nucleus_cold_archive" {
  count = length(var.pds_node_names)
  bucket = aws_s3_bucket.pds_nucleus_cold_archive[count.index].id
  versioning_configuration {
    status = "Enabled"
  }
}

output "pds_nucleus_cold_archive_buckets" {
  value = aws_s3_bucket.pds_nucleus_cold_archive
}
