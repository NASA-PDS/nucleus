# Terraform script to create the PDS archive related resources

# Create a hot archive for each PDS Node
resource "aws_s3_bucket" "pds_nucleus_hot_archive" {
  count = length(var.pds_node_names)
  # convert PDS node name to S3 bucket name compatible format
  bucket = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_nucleus_hot_archive_name_postfix}"
}

# Create a cold archive for each PDS Node
resource "aws_glacieraws_s3_bucket_vault" "pds_nucleus_cold_archive" {
  count = length(var.pds_node_names)
  # convert PDS node name to S3 bucket name compatible format
  name = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_nucleus_cold_archive_name_postfix}"

  transition {
    storage_class = GLACIER_IR
  }
}


