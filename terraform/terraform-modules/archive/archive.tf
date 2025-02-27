# Terraform script to create the PDS archive related resources

# Create a hot archive for each PDS Node
resource "aws_s3_bucket" "pds_nucleus_hot_archive" {
  count = length(var.pds_node_names)
  # convert PDS node name to S3 bucket name compatible format
  bucket = "${lower(replace(var.pds_node_names[count.index], "_", "-"))}-${var.pds_nucleus_hot_archive_bucket_name_postfix}"
}

resource "aws_s3_bucket_versioning" "pds_nucleus_hot_archive" {
  count = length(var.pds_node_names)

  bucket = aws_s3_bucket.pds_nucleus_hot_archive[count.index].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_replication_configuration" "pds_nucleus_s3_bucket_replication_configuration" {

  count = length(var.pds_node_names)

  role   = var.pds_nucleus_archive_replication_role_arn
  bucket = aws_s3_bucket.pds_nucleus_hot_archive[count.index].id

  rule {

    filter {
    }

    id = "pds-nucleus-replication-rule-${var.pds_node_names[count.index]}"

    status = "Enabled"

    delete_marker_replication {
      status = "Disabled"
    }

    destination {
      bucket        = var.pds_nucleus_cold_archive_buckets[count.index].arn
      storage_class = var.pds_nucleus_cold_archive_storage_class

      metrics {
        event_threshold {
          minutes = 15
        }
        status = "Enabled"
      }


      replication_time {
        status = "Enabled"
        time {
          minutes = 15
        }
      }

    }
  }

  depends_on = [aws_s3_bucket_versioning.pds_nucleus_hot_archive]
}
