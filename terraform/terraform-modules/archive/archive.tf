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

data "aws_iam_policy_document" "pds_nucleus_archive_replication_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

# The Policy for Permission Boundary
data "aws_iam_policy" "mcp_operator_policy" {
  name = var.permission_boundary_for_iam_roles
}

resource "aws_iam_role" "pds_nucleus_archive_replication_role" {
  name               = "pds-nucleus-archive-replication-role"
  assume_role_policy = data.aws_iam_policy_document.pds_nucleus_archive_replication_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}

data "aws_iam_policy_document" "pds_nucleus_archive_replication_policy" {

  statement {
    effect = "Allow"

    actions = [
      "s3:GetReplicationConfiguration",
      "s3:ListBucket",
    ]

    resources = ["arn:aws:s3:::pds-*-archive-*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "s3:GetObjectVersionForReplication",
      "s3:GetObjectVersionAcl",
      "s3:GetObjectVersionTagging",
    ]

    resources = ["arn:aws:s3:::pds-*-archive-*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "s3:ReplicateObject",
      "s3:ReplicateDelete",
      "s3:ReplicateTags",
    ]

    resources = ["arn:aws:s3:::pds-*-archive-*"]
  }
}

resource "aws_iam_policy" "pds_nucleus_archive_replication_policy" {
  name   = "pds-nucleus-archive-replication-policy"
  policy = data.aws_iam_policy_document.pds_nucleus_archive_replication_policy.json
}

resource "aws_iam_role_policy_attachment" "pds_nucleus_archive_replication_policy_document" {
  role       = aws_iam_role.pds_nucleus_archive_replication_role.name
  policy_arn = aws_iam_policy.pds_nucleus_archive_replication_policy.arn
}

resource "aws_s3_bucket_replication_configuration" "pds_nucleus_s3_bucket_replication_configuration" {

  count = length(var.pds_node_names)

  role   = aws_iam_role.pds_nucleus_archive_replication_role.arn
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
