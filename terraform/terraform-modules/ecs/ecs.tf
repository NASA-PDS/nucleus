# Terraform script to create the use case specific ECS task definitions

resource "aws_ecs_cluster" "main" {
  name = "pds-nucleus-ecc-tf"
}

resource "aws_ecs_task_definition" "pds-s3-to-efs-data-move-terraform" {
  family                   = "pds-s3-to-efs-data-move-terraform"
  requires_compatibilities = ["EC2", "FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 4096
  memory                   = 8192
  runtime_platform {
    operating_system_family = "LINUX"
  }

  volume {
    name = "pds-airflow-efs-registry-loader-scripts"

    efs_volume_configuration {
      file_system_id     = var.efs_file_system_id
      root_directory     = "/"
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = var.registry_loader_scripts_access_point_id
        iam             = "ENABLED"
      }
    }
  }

  volume {
    name = "pds-airflow-efs-registry-loader-default-configs"

    efs_volume_configuration {
      file_system_id     = var.efs_file_system_id
      root_directory     = "/"
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = var.registry_loader_default_configs_access_point_id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = file("terraform-modules/ecs/container-definitions/pds-s3-to-efs-data-mover.json")
  task_role_arn         = var.task_role_arn
  execution_role_arn    = var.execution_role_arn

}

resource "aws_ecs_task_definition" "pds-airflow-registry-loader-terraform" {
  family                   = "pds-airflow-registry-loader-terraform"
  requires_compatibilities = ["EC2", "FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 4096
  memory                   = 8192
  runtime_platform {
    operating_system_family = "LINUX"
  }

  volume {
    name = "pds-airflow-efs-registry-loader-scripts"

    efs_volume_configuration {
      file_system_id     = var.efs_file_system_id
      root_directory     = "/"
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = var.registry_loader_scripts_access_point_id
        iam             = "ENABLED"
      }
    }
  }

  volume {
    name = "pds-airflow-efs-registry-loader-default-configs"

    efs_volume_configuration {
      file_system_id     = var.efs_file_system_id
      root_directory     = "/"
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = var.registry_loader_default_configs_access_point_id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = file("terraform-modules/ecs/container-definitions/pds-airflow-registry-loader-containers.json")
  task_role_arn         = var.task_role_arn
  execution_role_arn    = var.execution_role_arn

}

resource "aws_ecs_task_definition" "pds-airflow-integration-test-terraform" {
  family                   = "pds-airflow-integration-test-terraform"
  requires_compatibilities = ["EC2", "FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 4096
  memory                   = 8192
  runtime_platform {
    operating_system_family = "LINUX"
  }

  volume {
    name = "pds-airflow-efs"

    efs_volume_configuration {
      file_system_id     = var.efs_file_system_id
      root_directory     = "/"
      transit_encryption = "DISABLED"
    }
  }

  volume {
    name = "pds-airflow-efs-registry-loader-scripts"

    efs_volume_configuration {
      file_system_id     = var.efs_file_system_id
      root_directory     = "/"
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = var.registry_loader_scripts_access_point_id
        iam             = "ENABLED"
      }
    }
  }

  volume {
    name = "pds-airflow-efs-registry-loader-default-configs"

    efs_volume_configuration {
      file_system_id     = var.efs_file_system_id
      root_directory     = "/"
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = var.registry_loader_default_configs_access_point_id
        iam             = "ENABLED"
      }
    }
  }

  container_definitions = file("terraform-modules/ecs/container-definitions/pds-airflow-integration-test-containers.json")
  task_role_arn         = var.task_role_arn
  execution_role_arn    = var.execution_role_arn
}
