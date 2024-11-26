# Terraform script to create the use case specific ECS task definitions

resource "aws_ecs_cluster" "pds_nucleus_ecs_cluster" {
  name = var.pds_nucleus_ecs_cluster_name
}

# The Policy for Permission Boundary
data "aws_iam_policy" "mcp_operator_policy" {
  name = var.permission_boundary_for_iam_roles
}


# Add account ID to templates
data "aws_caller_identity" "current" {}

data "template_file" "deploy_ecr_images_script_template" {
  template = file("terraform-modules/ecs-ecr/docker/template-deploy-ecr-images.sh")
  vars = {
    pds_nucleus_aws_account_id = data.aws_caller_identity.current.account_id
  }
  depends_on = [data.aws_caller_identity.current]
}

resource "local_file" "deploy_ecr_images_script_file" {
  content  = data.template_file.deploy_ecr_images_script_template.rendered
  filename = "terraform-modules/ecs-ecr/docker/deploy-ecr-images.sh"

  depends_on = [data.template_file.deploy_ecr_images_script_template]
}

#-------------------------------------
# ECS Task Role
#-------------------------------------

# IAM Policy Document for Inline Policy
data "aws_iam_policy_document" "ecs_task_role_inline_policy" {
  statement {
    effect = "Allow"
    actions = [
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:BatchCheckLayerAvailability"
    ]
    resources = [
      "arn:aws:ecr:*:${data.aws_caller_identity.current.account_id}:repository/pds*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "elasticfilesystem:DescribeMountTargets",
      "elasticfilesystem:ClientMount",
      "elasticfilesystem:ClientWrite",
      "elasticfilesystem:ClientRootAccess"
    ]
    resources = [
      "arn:aws:elasticfilesystem:*:${data.aws_caller_identity.current.account_id}:access-point/*",
      "arn:aws:elasticfilesystem:*:${data.aws_caller_identity.current.account_id}:file-system/pds-nucleus*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:CreateLogGroup",
      "logs:PutLogEvents"
    ]
    resources = [
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:*:log-stream:*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken"
    ]
    resources = [
      "arn:aws:ecr:*:${data.aws_caller_identity.current.account_id}:repository/pds*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "s3:GetBucket*",
      "s3:GetObject*",
      "s3:List*",
      "s3:PutObject"
    ]
    resources = [
      "arn:aws:s3:::pds-nucleus*",
      "arn:aws:s3:::pds-nucleus*/*",
      "arn:aws:s3:::pds-*-staging*",
      "arn:aws:s3:::pds-*-staging*/*",
      "arn:aws:s3:::pds-*-archive*",
      "arn:aws:s3:::pds-*-archive*/*"
    ]
  }
}


# TODO: Restrict to PDS accounts in future

# IAM Policy Document for Assume Role
data "aws_iam_policy_document" "ecs_task_role_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "pds_nucleus_ecs_task_role" {
  name = "pds_nucleus_ecs_task_role"
  inline_policy {
    name   = "pds-nucleus-ecs-task-role-inline-policy"
    policy = data.aws_iam_policy_document.ecs_task_role_inline_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.ecs_task_role_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}


#-------------------------------------
# ECS Task Execution Role
#-------------------------------------

# IAM Policy Document for Inline Policy
data "aws_iam_policy_document" "ecs_task_execution_role_inline_policy" {
  statement {
    effect = "Allow"
    actions = [
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
      "ecr:BatchCheckLayerAvailability"
    ]
    resources = [
      "arn:aws:ecr:*:${data.aws_caller_identity.current.account_id}:repository/pds*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "ecr:GetAuthorizationToken"
    ]
    resources = [
      "*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:CreateLogGroup"
    ]
    resources = [
      "arn:aws:logs:*:${data.aws_caller_identity.current.account_id}:log-group:*:log-stream:*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "ecs:stopTask"
    ]
    resources = [
      "arn:aws:ecs:*:${data.aws_caller_identity.current.account_id}:task/pds-nucleus-ecs/*"
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "kms:Decrypt"
    ]
    resources = [
      "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:pds/nucleus/opensearch/creds/*",
      var.aws_secretmanager_key_arn
    ]
  }

  statement {
    effect = "Allow"
    actions = [
      "secretsmanager:GetSecretValue",
      "kms:Decrypt"
    ]
    resources = [
      "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:pds/nucleus/opensearch/creds/*",
      var.aws_secretmanager_key_arn
    ]
  }
}

resource "aws_iam_role" "pds_nucleus_ecs_task_execution_role" {
  name = "pds_nucleus_ecs_task_execution_role"
  inline_policy {
    name   = "pds-nucleus-ecs-task-execution-role-inline-policy"
    policy = data.aws_iam_policy_document.ecs_task_execution_role_inline_policy.json
  }
  assume_role_policy   = data.aws_iam_policy_document.ecs_task_role_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}

#------------------------------------
# ECR Repositories
#------------------------------------

resource "aws_ecr_repository" "pds_nucleus_config_init" {
  name                 = "pds-nucleus-config-init"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "pds_nucleus_s3_to_efs_copy" {
  name                 = "pds-nucleus-s3-to-efs-copy"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "pds_registry_loader_harvest" {
  name                 = "pds-registry-loader-harvest"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "pds_validate" {
  name                 = "pds-validate"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}



#-------------------------------------
# PDS Registry Loader Harvest ECS Task
#-------------------------------------

# CloudWatch Log Group for PDS Registry Loader Harvest ECS Task
resource "aws_cloudwatch_log_group" "pds-registry-loader-harvest-log-group" {
  name = var.pds_registry_loader_harvest_cloudwatch_logs_group
}

# Create secrets to keep usernames for each PDS Node
resource "aws_secretsmanager_secret" "opensearch_user" {
  count                   = length(var.pds_node_names)
  name                    = "pds/nucleus/opensearch/creds/${var.pds_node_names[count.index]}/user"
  description             = "PDS Nucleus Opensearch username for ${var.pds_node_names[count.index]}"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "opensearch_user_version" {
  count         = length(var.pds_node_names)
  secret_id     = aws_secretsmanager_secret.opensearch_user[count.index].id
  secret_string = "Replace this with Opensearch username of PDS Node: ${var.pds_node_names[count.index]}"
}

# Create secrets to keep passwords for each PDS Node
resource "aws_secretsmanager_secret" "opensearch_password" {
  count                   = length(var.pds_node_names)
  name                    = "pds/nucleus/opensearch/creds/${var.pds_node_names[count.index]}/password"
  description             = "PDS Nucleus Opensearch password for ${var.pds_node_names[count.index]}"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "opensearch_password_version" {
  count         = length(var.pds_node_names)
  secret_id     = aws_secretsmanager_secret.opensearch_password[count.index].id
  secret_string = "Replace this with Opensearch password of PDS Node: ${var.pds_node_names[count.index]}"
}

# Replace PDS Registry Loader Harvest related variables in pds-airflow-registry-loader-harvest-containers.json
data "template_file" "pds-registry-loader-harvest-containers-json-template" {
  count    = length(var.pds_node_names)
  template = file("terraform-modules/ecs-ecr/container-definitions/pds-airflow-registry-loader-harvest-containers.json")
  vars = {
    pds_registry_loader_harvest_ecs_task_name          = "pds-registry-loader-harvest-${var.pds_node_names[count.index]}"
    pds_registry_loader_harvest_ecr_image_path         = aws_ecr_repository.pds_registry_loader_harvest.repository_url
    pds_registry_loader_harvest_cloudwatch_logs_group  = var.pds_registry_loader_harvest_cloudwatch_logs_group
    pds_registry_loader_harvest_cloudwatch_logs_region = var.pds_registry_loader_harvest_cloudwatch_logs_region
    opensearch_user_secretmanager_arn                  = aws_secretsmanager_secret_version.opensearch_user_version[count.index].arn
    opensearch_password_secretmanager_arn              = aws_secretsmanager_secret_version.opensearch_password_version[count.index].arn
  }
}

# PDS Registry Loader Harvest Task Definition
resource "aws_ecs_task_definition" "pds-registry-loader-harvest" {
  count                    = length(var.pds_node_names)
  family                   = "pds-airflow-registry-loader-harvest-task-definition-${var.pds_node_names[count.index]}"
  requires_compatibilities = ["EC2", "FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 4096
  memory                   = 8192
  runtime_platform {
    operating_system_family = "LINUX"
  }

  volume {
    name = "pds-data"

    efs_volume_configuration {
      file_system_id     = var.efs_file_system_id
      root_directory     = "/"
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = var.pds_data_access_point_id
        iam             = "ENABLED"
      }
    }
  }


  container_definitions = data.template_file.pds-registry-loader-harvest-containers-json-template[count.index].rendered
  task_role_arn         = var.pds_registry_loader_harvest_task_role_arn
  execution_role_arn    = aws_iam_role.pds_nucleus_ecs_task_execution_role.arn

  depends_on = [data.template_file.pds-validate-containers-json-template]

}


#-------------------------------------
# PDS Validate ECS Task
#-------------------------------------

# CloudWatch Log Group for PDS Validate ECS Task
resource "aws_cloudwatch_log_group" "pds-validate-log-group" {
  name = var.pds_validate_cloudwatch_logs_group
}

# Replace PDS Validate ECR Image Path in pds-validate-containers.json
data "template_file" "pds-validate-containers-json-template" {
  template = file("terraform-modules/ecs-ecr/container-definitions/pds-validate-containers.json")
  vars = {
    pds_validate_ecr_image_path         = aws_ecr_repository.pds_validate.repository_url
    pds_validate_cloudwatch_logs_group  = var.pds_validate_cloudwatch_logs_group
    pds_validate_cloudwatch_logs_region = var.pds_validate_cloudwatch_logs_region
  }
}

# PDS Validate ECS Task Definition
resource "aws_ecs_task_definition" "pds-validate-task-definition" {
  family                   = "pds-validate-task-definition"
  requires_compatibilities = ["EC2", "FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 4096
  memory                   = 8192
  runtime_platform {
    operating_system_family = "LINUX"
  }

  volume {
    name = "pds-data"

    efs_volume_configuration {
      file_system_id     = var.efs_file_system_id
      root_directory     = "/"
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = var.pds_data_access_point_id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = data.template_file.pds-validate-containers-json-template.rendered
  task_role_arn         = aws_iam_role.pds_nucleus_ecs_task_role.arn
  execution_role_arn    = aws_iam_role.pds_nucleus_ecs_task_execution_role.arn

  depends_on = [data.template_file.pds-validate-containers-json-template]
}


#-------------------------------------
# PDS Validate Ref ECS Task
#-------------------------------------

# CloudWatch Log Group for PDS Validate Ref ECS Task
resource "aws_cloudwatch_log_group" "pds-validate-ref-log-group" {
  name = var.pds_validate_ref_cloudwatch_logs_group
}

# Replace PDS Validate Ref ECR Image Path in pds-validate-refs-containers.json
data "template_file" "pds-validate-ref-containers-json-template" {
  template = file("terraform-modules/ecs-ecr/container-definitions/pds-validate-refs-containers.json")
  vars = {
    pds_validate_ref_ecr_image_path = aws_ecr_repository.pds_validate.repository_url
    # Validate image is reused
    pds_validate_ref_cloudwatch_logs_group  = var.pds_validate_ref_cloudwatch_logs_group
    pds_validate_ref_cloudwatch_logs_region = var.region
  }
}


#---------------------------------------------
# PDS Nucleus Config Init ECS Task Definition
#---------------------------------------------

# CloudWatch Log Group for PDS Nucleus Config Init ECS Task
resource "aws_cloudwatch_log_group" "pds-nucleus-config-init-log-group" {
  name = var.pds_nucleus_config_init_cloudwatch_logs_group
}

# Replace PDS Nucleus Config Init ECR Image Path in pds-nucleus-config-init-containers.json
data "template_file" "pds-nucleus-config-init-containers-json-template" {
  template = file("terraform-modules/ecs-ecr/container-definitions/pds-nucleus-config-init-containers.json")
  vars = {
    pds_nucleus_config_init_ecr_image_path         = aws_ecr_repository.pds_nucleus_config_init.repository_url
    pds_nucleus_config_init_cloudwatch_logs_group  = var.pds_nucleus_config_init_cloudwatch_logs_group
    pds_nucleus_config_init_cloudwatch_logs_region = var.region
  }
}

# PDS Nucleus Config Init Task Definition
resource "aws_ecs_task_definition" "pds-nucleus-config-init-task-definition" {
  family                   = "pds-nucleus-config-init-task-definition"
  requires_compatibilities = ["EC2", "FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 4096
  memory                   = 8192
  runtime_platform {
    operating_system_family = "LINUX"
  }

  volume {
    name = "pds-data"

    efs_volume_configuration {
      file_system_id     = var.efs_file_system_id
      root_directory     = "/"
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = var.pds_data_access_point_id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = data.template_file.pds-nucleus-config-init-containers-json-template.rendered
  task_role_arn         = aws_iam_role.pds_nucleus_ecs_task_role.arn
  execution_role_arn    = aws_iam_role.pds_nucleus_ecs_task_execution_role.arn

  depends_on = [data.template_file.pds-nucleus-config-init-containers-json-template]
}


#---------------------------------------------
# PDS Nucleus S3 to EFS Copy ECS Task Definition
#---------------------------------------------

# Replace PDS Nucleus S3 to EFS Copy ECR Image Path in pds-nucleus-s3-to-efs-copy-containers.json
data "template_file" "pds-nucleus-s3-to-efs-copy-containers-json-template" {
  template = file("terraform-modules/ecs-ecr/container-definitions/pds-nucleus-s3-to-efs-copy-containers.json")
  vars = {
    pds_nucleus_s3_to_efs_copy_ecr_image_path         = aws_ecr_repository.pds_nucleus_s3_to_efs_copy.repository_url
    pds_nucleus_s3_to_efs_copy_cloudwatch_logs_group  = var.pds_nucleus_s3_to_efs_copy_cloudwatch_logs_group
    pds_nucleus_s3_to_efs_copy_cloudwatch_logs_region = var.region
  }
}

# PDS Nucleus S3 to EFS Copy Task Definition
resource "aws_ecs_task_definition" "pds-nucleus-s3-to-efs-copy-task-definition" {
  family                   = "pds-nucleus-s3-to-efs-copy-task-definition"
  requires_compatibilities = ["EC2", "FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 4096
  memory                   = 8192
  runtime_platform {
    operating_system_family = "LINUX"
  }

  volume {
    name = "pds-data"

    efs_volume_configuration {
      file_system_id     = var.efs_file_system_id
      root_directory     = "/"
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = var.pds_data_access_point_id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = data.template_file.pds-nucleus-s3-to-efs-copy-containers-json-template.rendered
  task_role_arn         = aws_iam_role.pds_nucleus_ecs_task_role.arn
  execution_role_arn    = aws_iam_role.pds_nucleus_ecs_task_execution_role.arn

  depends_on = [data.template_file.pds-nucleus-s3-to-efs-copy-containers-json-template]
}

resource "null_resource" "deploy_ecr_images" {
  provisioner "local-exec" {
    command = "./terraform-modules/ecs-ecr/docker/deploy-ecr-images.sh"
  }
}

output "pds_nucleus_ecs_cluster_name" {
  value = aws_ecs_cluster.pds_nucleus_ecs_cluster.name
}

output "pds_nucleus_ecs_subnets" {
  value = aws_ecs_cluster.pds_nucleus_ecs_cluster
}
