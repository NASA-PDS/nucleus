# Terraform script to create the use case specific ECS task definitions

resource "aws_ecs_cluster" "pds_nucleus_ecs_cluster" {
  name = var.pds_nucleus_ecs_cluster_name
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
  source_policy_documents = [file("${path.module}/ecs_task_role_iam_policy.json")]
}

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
  source_policy_documents = [file("${path.module}/ecs_task_execution_role_iam_policy.json")]
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
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "pds_nucleus_s3_to_efs_copy" {
  name                 = "pds-nucleus-s3-to-efs-copy"
  image_tag_mutability = "MUTABLE"
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "pds_registry_loader_harvest" {
  name                 = "pds-registry-loader-harvest"
  image_tag_mutability = "MUTABLE"
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "pds_validate" {
  name                 = "pds-validate"
  image_tag_mutability = "MUTABLE"
  force_delete = true

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

# Replace PDS Registry Loader Harvest ECR Image Path in pds-airflow-registry-loader-harvest-containers.json
data "template_file" "pds-registry-loader-harvest-containers-json-template" {
  template = file("terraform-modules/ecs-ecr/container-definitions/pds-airflow-registry-loader-harvest-containers.json")
  vars = {
    pds_registry_loader_harvest_ecr_image_path         = aws_ecr_repository.pds_registry_loader_harvest.repository_url
    pds_registry_loader_harvest_cloudwatch_logs_group  = var.pds_registry_loader_harvest_cloudwatch_logs_group
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
      file_system_id     = var.efs_file_system_id
      root_directory     = "/"
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = var.pds_data_access_point_id
        iam             = "ENABLED"
      }
    }
  }


  container_definitions = data.template_file.pds-registry-loader-harvest-containers-json-template.rendered
  task_role_arn         = aws_iam_role.pds_nucleus_ecs_task_role.arn
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

# CloudWatch Log Group for PDS Nucleus S3 to EFS Copy ECS Task
resource "aws_cloudwatch_log_group" "pds-nucleus-s3-to-efs-copy-log-group" {
  name = var.pds_nucleus_s3_to_efs_copy_cloudwatch_logs_group
}

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
