# Terraform script to create the PDS archive related resources

# Create a hot S3 archive bucket for each PDS Node
resource "aws_s3_bucket" "pds_nucleus_hot_archive_bucket" {
  count = length(var.pds_node_names)
  # convert PDS node name to S3 bucket name compatible format
  bucket = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_nucleus_archive_hot_bucket_name_postfix}"
}

# Create a hot S3 archive bucket for each PDS Node
resource "aws_s3_bucket" "pds_nucleus_col_archive_bucket" {
  count = length(var.pds_node_names)
  # convert PDS node name to S3 bucket name compatible format
  bucket = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_nucleus_archive_cold_bucket_name_postfix}"
}
