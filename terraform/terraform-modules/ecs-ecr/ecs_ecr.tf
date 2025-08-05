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
    aws_region = var.region
    ecs_registry = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.region}.amazonaws.com"
  }
  depends_on = [data.aws_caller_identity.current]
}

resource "local_file" "deploy_ecr_images_script_file" {
  content  = data.template_file.deploy_ecr_images_script_template.rendered
  filename = "terraform-modules/ecs-ecr/docker/deploy-ecr-images.sh"

  depends_on = [data.template_file.deploy_ecr_images_script_template]
}

#------------------------------------
# EFS Volumes
#------------------------------------

# Terraform script to create a EFS file system to be used for file exchange between containers

resource "aws_efs_file_system" "nucleus_efs" {
  count = length(var.pds_node_names)

  creation_token = "pds-nucleus-efs-${var.pds_node_names[count.index]}"
  encrypted      = true
  tags = {
    Name = "pds-nucleus-efs-${var.pds_node_names[count.index]}"
  }
}

resource "aws_efs_mount_target" "pds_nucleus_efs_mount_target_0" {
  count = length(var.pds_node_names)

  file_system_id  = aws_efs_file_system.nucleus_efs[count.index].id
  subnet_id       = var.subnet_ids[0]
  security_groups = [var.nucleus_security_group_id]
}

resource "aws_efs_mount_target" "pds_nucleus_efs_mount_target_1" {
  count = length(var.pds_node_names)

  file_system_id  = aws_efs_file_system.nucleus_efs[count.index].id
  subnet_id       = var.subnet_ids[1]
  security_groups = [var.nucleus_security_group_id]
}

resource "aws_efs_access_point" "pds-data" {

  count = length(var.pds_node_names)

  file_system_id = aws_efs_file_system.nucleus_efs[count.index].id

  root_directory {
    path = "/pds-data"

    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = 0755
    }
  }


  tags = {
    Name = "PDS Data access point"
  }
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

resource "aws_ecr_repository" "pds_nucleus_tools_java" {
  name                 = "pds-nucleus-tools-java"
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
  count = length(var.pds_node_names)
  name  = "${var.pds_registry_loader_harvest_cloudwatch_logs_group}-${var.pds_node_names[count.index]}"
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

# Replace PDS Registry Loader Harvest related variables in pds-registry-loader-harvest-containers.json
data "template_file" "pds-registry-loader-harvest-containers-json-template" {
  count    = length(var.pds_node_names)
  template = file("terraform-modules/ecs-ecr/container-definitions/pds-registry-loader-harvest-containers.json")
  vars = {
    pds_registry_loader_harvest_ecr_image_path         = aws_ecr_repository.pds_registry_loader_harvest.repository_url
    pds_registry_loader_harvest_cloudwatch_logs_group  = "${var.pds_registry_loader_harvest_cloudwatch_logs_group}-${var.pds_node_names[count.index]}"
    pds_registry_loader_harvest_cloudwatch_logs_region = var.pds_registry_loader_harvest_cloudwatch_logs_region
    opensearch_user_secretmanager_arn                  = aws_secretsmanager_secret_version.opensearch_user_version[count.index].arn
    opensearch_password_secretmanager_arn              = aws_secretsmanager_secret_version.opensearch_password_version[count.index].arn
  }
}

# PDS Registry Loader Harvest Task Definition
resource "aws_ecs_task_definition" "pds-registry-loader-harvest" {
  count                    = length(var.pds_node_names)
  family                   = "pds-registry-loader-harvest-task-definition-${var.pds_node_names[count.index]}"
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
      file_system_id     = aws_efs_file_system.nucleus_efs[count.index].id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.pds-data[count.index].id
        iam             = "ENABLED"
      }
    }
  }


  container_definitions = data.template_file.pds-registry-loader-harvest-containers-json-template[count.index].rendered
  task_role_arn         = var.pds_nucleus_harvest_ecs_task_role_arns[count.index]
  execution_role_arn    = var.pds_nucleus_ecs_task_execution_role_arn

  depends_on = [data.template_file.pds-validate-containers-json-template]

}


#-------------------------------------
# PDS Validate ECS Task
#-------------------------------------

# CloudWatch Log Group for PDS Validate ECS Task
resource "aws_cloudwatch_log_group" "pds-validate-log-group" {
  count    = length(var.pds_node_names)
  name = "${var.pds_validate_cloudwatch_logs_group}-${var.pds_node_names[count.index]}"
}

# Replace PDS Validate ECR Image Path in pds-validate-containers.json
data "template_file" "pds-validate-containers-json-template" {
  count    = length(var.pds_node_names)
  template = file("terraform-modules/ecs-ecr/container-definitions/pds-validate-containers.json")
  vars = {
    pds_validate_ecr_image_path         = aws_ecr_repository.pds_validate.repository_url
    pds_validate_cloudwatch_logs_group  = "${var.pds_validate_cloudwatch_logs_group}-${var.pds_node_names[count.index]}"
    pds_validate_cloudwatch_logs_region = var.pds_validate_cloudwatch_logs_region
  }
}

# PDS Validate ECS Task Definition
resource "aws_ecs_task_definition" "pds-validate-task-definition" {
  count                    = length(var.pds_node_names)
  family                   = "pds-validate-task-definition-${var.pds_node_names[count.index]}"
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
      file_system_id     = aws_efs_file_system.nucleus_efs[count.index].id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.pds-data[count.index].id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = data.template_file.pds-validate-containers-json-template[count.index].rendered
  task_role_arn         = var.pds_nucleus_ecs_task_role_arns[count.index]
  execution_role_arn    = var.pds_nucleus_ecs_task_execution_role_arn

  depends_on = [data.template_file.pds-validate-containers-json-template]
}


#-------------------------------------
# PDS Validate Ref ECS Task
#-------------------------------------

# CloudWatch Log Group for PDS Validate Ref ECS Task
resource "aws_cloudwatch_log_group" "pds-validate-ref-log-group" {
  count    = length(var.pds_node_names)
  name = "${var.pds_validate_ref_cloudwatch_logs_group}-${var.pds_node_names[count.index]}"
}

# Replace PDS Validate Ref ECR Image Path in pds-validate-refs-containers.json
data "template_file" "pds-validate-ref-containers-json-template" {
  count = length(var.pds_node_names)

  template = file("terraform-modules/ecs-ecr/container-definitions/pds-validate-refs-containers.json")
  vars = {
    pds_validate_ref_ecr_image_path = aws_ecr_repository.pds_validate.repository_url
    # Validate image is reused
    pds_validate_ref_cloudwatch_logs_group  = "${var.pds_validate_ref_cloudwatch_logs_group}-${var.pds_node_names[count.index]}"
    pds_validate_ref_cloudwatch_logs_region = var.region
  }
}


#---------------------------------------------
# PDS Nucleus Config Init ECS Task Definition
#---------------------------------------------

# CloudWatch Log Group for PDS Nucleus Config Init ECS Task
resource "aws_cloudwatch_log_group" "pds-nucleus-config-init-log-group" {
  count = length(var.pds_node_names)
  name = "${var.pds_nucleus_config_init_cloudwatch_logs_group}-${var.pds_node_names[count.index]}"
}

# Replace PDS Nucleus Config Init ECR Image Path in pds-nucleus-config-init-containers.json
data "template_file" "pds-nucleus-config-init-containers-json-template" {
  count = length(var.pds_node_names)

  template = file("terraform-modules/ecs-ecr/container-definitions/pds-nucleus-config-init-containers.json")
  vars = {
    pds_nucleus_config_init_ecr_image_path         = aws_ecr_repository.pds_nucleus_config_init.repository_url
    pds_nucleus_config_init_cloudwatch_logs_group  = "${var.pds_nucleus_config_init_cloudwatch_logs_group}-${var.pds_node_names[count.index]}"
    pds_nucleus_config_init_cloudwatch_logs_region = var.region
  }
}

# PDS Nucleus Config Init Task Definition
resource "aws_ecs_task_definition" "pds-nucleus-config-init-task-definition" {
  count                    = length(var.pds_node_names)
  family                   = "pds-nucleus-config-init-task-definition-${var.pds_node_names[count.index]}"
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
      file_system_id     = aws_efs_file_system.nucleus_efs[count.index].id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.pds-data[count.index].id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = data.template_file.pds-nucleus-config-init-containers-json-template[count.index].rendered
  task_role_arn         = var.pds_nucleus_ecs_task_role_arns[count.index]
  execution_role_arn    = var.pds_nucleus_ecs_task_execution_role_arn

  depends_on = [data.template_file.pds-nucleus-config-init-containers-json-template]
}


#---------------------------------------------
# PDS Nucleus S3 to EFS Copy ECS Task Definition
#---------------------------------------------

# Replace PDS Nucleus S3 to EFS Copy ECR Image Path in pds-nucleus-s3-to-efs-copy-containers.json
data "template_file" "pds-nucleus-s3-to-efs-copy-containers-json-template" {
  count    = length(var.pds_node_names)
  template = file("terraform-modules/ecs-ecr/container-definitions/pds-nucleus-s3-to-efs-copy-containers.json")
  vars = {
    pds_nucleus_s3_to_efs_copy_ecr_image_path         = aws_ecr_repository.pds_nucleus_s3_to_efs_copy.repository_url
    pds_nucleus_s3_to_efs_copy_cloudwatch_logs_group  = "${var.pds_nucleus_s3_to_efs_copy_cloudwatch_logs_group}-${var.pds_node_names[count.index]}"
    pds_nucleus_s3_to_efs_copy_cloudwatch_logs_region = var.region
  }
}

# PDS Nucleus S3 to EFS Copy Task Definition
resource "aws_ecs_task_definition" "pds-nucleus-s3-to-efs-copy-task-definition" {
  count                    = length(var.pds_node_names)
  family                   = "pds-nucleus-s3-to-efs-copy-task-definition-${var.pds_node_names[count.index]}"
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
      file_system_id     = aws_efs_file_system.nucleus_efs[count.index].id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.pds-data[count.index].id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = data.template_file.pds-nucleus-s3-to-efs-copy-containers-json-template[count.index].rendered
  task_role_arn         = var.pds_nucleus_ecs_task_role_arns[count.index]
  execution_role_arn    = var.pds_nucleus_ecs_task_execution_role_arn

  depends_on = [data.template_file.pds-nucleus-s3-to-efs-copy-containers-json-template]
}


#---------------------------------------------
# PDS Nucleus S3 Backlog Processor ECS Task Definition
#---------------------------------------------

# CloudWatch Log Group for PDS Nucleus S3 Backlog Processor ECS Task
resource "aws_cloudwatch_log_group" "pds-nucleus-s3-backlog-processor-log-group" {
  count             = length(var.pds_node_names)
  name              = "${var.pds_nucleus_s3_backlog_processor_cloudwatch_logs_group}-${var.pds_node_names[count.index]}"
  retention_in_days = 30
}

# Replace PDS Nucleus S3 Backlog Processor Image Path in pds-nucleus-s3-backlog-processor-containers.json
data "template_file" "pds-nucleus-s3-backlog-processor-containers-json-template" {
  count    = length(var.pds_node_names)
  template = file("terraform-modules/ecs-ecr/container-definitions/pds-nucleus-s3-backlog-processor-containers.json")
  vars = {
    pds_nucleus_tools_java_ecr_image_path                   = aws_ecr_repository.pds_nucleus_tools_java.repository_url
    pds_nucleus_s3_backlog_processor_cloudwatch_logs_group  = "${var.pds_nucleus_s3_backlog_processor_cloudwatch_logs_group}-${var.pds_node_names[count.index]}"
    pds_nucleus_s3_backlog_processor_cloudwatch_logs_region = var.region
  }
}

# PDS Nucleus S3 to EFS Copy Task Definition
resource "aws_ecs_task_definition" "pds-nucleus-s3-backlog-processor-task-definition" {
  count                    = length(var.pds_node_names)
  family                   = "pds-nucleus-s3-backlog-processor-task-definition-${var.pds_node_names[count.index]}"
  requires_compatibilities = ["EC2", "FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 4096
  memory                   = 8192

  runtime_platform {
    operating_system_family = "LINUX"
  }

  container_definitions = data.template_file.pds-nucleus-s3-backlog-processor-containers-json-template[count.index].rendered
  task_role_arn         = var.pds_nucleus_ecs_task_role_arns[count.index]
  execution_role_arn    = var.pds_nucleus_ecs_task_execution_role_arn

  depends_on = [data.template_file.pds-nucleus-s3-backlog-processor-containers-json-template]
}




# Deploy ECR images
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
