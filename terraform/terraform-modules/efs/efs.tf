# Terraform script to create a EFS file system to be used for file exchange between containers

resource "aws_efs_file_system" "nucleus_efs" {
  creation_token = "nucleus_efs_token"

  tags = {
    Name = "Nucleus"
  }
}

resource "aws_efs_access_point" "root" {

  file_system_id = aws_efs_file_system.nucleus_efs.id

  root_directory {
    path = "/"
  }

  tags = {
    Name = "root access point"
  }
}

resource "aws_efs_access_point" "scripts" {

  file_system_id = aws_efs_file_system.nucleus_efs.id

  root_directory {
    path = "/registry/docker/scripts"
  }

  tags = {
    Name = "scripts access point"
  }
}

resource "aws_efs_access_point" "registry-loader-waits-for-elasticsearch" {

  file_system_id = aws_efs_file_system.nucleus_efs.id

  root_directory {
    path = "/registry/docker/scripts/registry-loader-waits-for-elasticsearch.sh"
  }

  tags = {
    Name = "registry-loader-waits-for-elasticsearch access point"
  }
}

resource "aws_efs_access_point" "default-config" {

  file_system_id = aws_efs_file_system.nucleus_efs.id

  root_directory {
    path = "/registry/docker/default-config"
  }

  tags = {
    Name = "default-config access point"
  }
}
