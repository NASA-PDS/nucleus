# Terraform script to create the use case specific ECS task definitions

resource "aws_ecs_cluster" "main" {
  name = "pds-nucleus-ecs"
}

# The Policy for Permission Boundary
data "aws_iam_policy" "mcp_operator_policy" {
  name = var.permission_boundary_for_iam_role
}

#-------------------------------------
# ECS Task Role
#-------------------------------------


# IAM Policy Document for Inline Policy
data "aws_iam_policy_document" "ecs_task_role_inline_policy" {
  source_policy_documents =  [file("${path.module}/ecs_task_role_iam_policy.json")]
}

# IAM Policy Document for Assume Role
data "aws_iam_policy_document" "ecs_task_role_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = [ "ecs-tasks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "pds_nucleus_ecs_task_role" {
  name                  = "pds_nucleus_ecs_task_role"
  inline_policy {
    name   = "pds-nucleus-ecs-task-role-inline-policy"
    policy = data.aws_iam_policy_document.ecs_task_role_inline_policy.json
  }
  assume_role_policy = data.aws_iam_policy_document.ecs_task_role_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}


#-------------------------------------
# ECS Task Execution Role
#-------------------------------------

# IAM Policy Document for Inline Policy
data "aws_iam_policy_document" "ecs_task_execution_role_inline_policy" {
  source_policy_documents =  [file("${path.module}/ecs_task_execution_role_iam_policy.json")]
}

## IAM Policy Document for Assume Role
#data "aws_iam_policy_document" "ecs_task_execution_role_assume_role" {
#  statement {
#    effect = "Allow"
#    principals {
#      type        = "Service"
#      identifiers = [ "airflow-env.amazonaws.com", "airflow.amazonaws.com"]
#    }
#    actions = ["sts:AssumeRole"]
#  }
#}

resource "aws_iam_role" "pds_nucleus_ecs_task_execution_role" {
  name                  = "pds_nucleus_ecs_task_execution_role"
  inline_policy {
    name   = "pds-nucleus-ecs-task-execution-role-inline-policy"
    policy = data.aws_iam_policy_document.ecs_task_execution_role_inline_policy.json
  }
  assume_role_policy = data.aws_iam_policy_document.ecs_task_role_assume_role.json
  permissions_boundary = data.aws_iam_policy.mcp_operator_policy.arn
}


#-------------------------------------
# PDS Registry Loader Harvest ECS Task
#-------------------------------------

# CloudWatch Log Group for PDS Registry Loader Harvest ECS Task
resource "aws_cloudwatch_log_group" "pds-registry-loader-harvest-log-group" {
  name = var.pds_registry_loader_harvest_cloudwatch_logs_group
}

# Replace PDS Registry Loader Harvest ECR Image Path in pds-airflow-registry-loader-harvest-containers.json
data "template_file" "pds-registry-loader-harvest-containers-json-template" {
  template = file("terraform-modules/ecs/container-definitions/pds-airflow-registry-loader-harvest-containers.json")
  vars = {
    pds_registry_loader_harvest_ecr_image_path = var.pds_registry_loader_harvest_ecr_image_path
    pds_registry_loader_harvest_cloudwatch_logs_group = var.pds_registry_loader_harvest_cloudwatch_logs_group
    pds_registry_loader_harvest_cloudwatch_logs_region = var.pds_registry_loader_harvest_cloudwatch_logs_region
  }
}

# PDS Registry Loader Harvest Task Definition
resource "aws_ecs_task_definition" "pds-registry-loader-harvest" {
  family                   = "pds-airflow-registry-loader-harvest-task-definition"
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
      file_system_id      = var.efs_file_system_id
      root_directory      = "/"
      transit_encryption  = "ENABLED"
      authorization_config {
        access_point_id   = var.pds_data_access_point_id
        iam               = "ENABLED"
      }
    }
  }

  container_definitions       = data.template_file.pds-validate-containers-json-template.rendered
  task_role_arn               = aws_iam_role.pds_nucleus_ecs_task_role.arn
  execution_role_arn          = aws_iam_role.pds_nucleus_ecs_task_execution_role.arn

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
  template = file("terraform-modules/ecs/container-definitions/pds-validate-containers.json")
  vars = {
    pds_validate_ecr_image_path = var.pds_validate_ecr_image_path
    pds_validate_cloudwatch_logs_group = var.pds_validate_cloudwatch_logs_group
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
      file_system_id      = var.efs_file_system_id
      root_directory      = "/"
      transit_encryption  = "ENABLED"
      authorization_config {
        access_point_id   = var.pds_data_access_point_id
        iam               = "ENABLED"
      }
    }
  }

  container_definitions       = data.template_file.pds-validate-containers-json-template.rendered
  task_role_arn               = aws_iam_role.pds_nucleus_ecs_task_role.arn
  execution_role_arn          = aws_iam_role.pds_nucleus_ecs_task_execution_role.arn

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
  template = file("terraform-modules/ecs/container-definitions/pds-validate-refs-containers.json")
  vars = {
    pds_validate_ref_ecr_image_path = var.pds_validate_ecr_image_path # Validate image is reused
    pds_validate_ref_cloudwatch_logs_group = var.pds_validate_ref_cloudwatch_logs_group
    pds_validate_ref_cloudwatch_logs_region = var.pds_validate_ref_cloudwatch_logs_region
  }
}
#
## PDS Validate Ref ECS Task Definition
#resource "aws_ecs_task_definition" "pds-validate-ref-task-definition" {
#  family                   = "pds-validate-refs-task-definition"
#  requires_compatibilities = ["EC2", "FARGATE"]
#  network_mode             = "awsvpc"
#  cpu                      = 2048
#  memory                   = 8192
#  runtime_platform {
#    operating_system_family = "LINUX"
#  }
#
#  volume {
#    name = "pds-data"
#
#    efs_volume_configuration {
#      file_system_id     = var.efs_file_system_id
#      root_directory     = "/"
#      transit_encryption = "ENABLED"
#      authorization_config {
#        access_point_id  = var.pds_data_access_point_id
#        iam              = "ENABLED"
#      }
#    }
#  }
#
#  container_definitions = file("terraform-modules/ecs/container-definitions/pds-validate-refs-containers.json")
#  task_role_arn               = aws_iam_role.pds_nucleus_ecs_task_role.arn
#  execution_role_arn          = aws_iam_role.pds_nucleus_ecs_task_execution_role.arn
#}
