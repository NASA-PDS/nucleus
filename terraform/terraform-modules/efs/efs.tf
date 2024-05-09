# Terraform script to create a EFS file system to be used for file exchange between containers

resource "aws_efs_file_system" "nucleus_efs" {
  creation_token = "nucleus_efs_token"

  tags = {
    Name = "Nucleus EFS"
  }
}

resource "aws_efs_mount_target" "pds_nucleus_efs_mount_target" {
  file_system_id  = aws_efs_file_system.nucleus_efs.id
  subnet_id       = var.subnet_ids[0]
  security_groups = [var.nucleus_security_group_id]
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


resource "aws_efs_access_point" "pds-data" {

  file_system_id = aws_efs_file_system.nucleus_efs.id

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


output "efs_file_system_id" {
  value = aws_efs_file_system.nucleus_efs.id
}

output "efs_access_point_id_root" {
  value = aws_efs_access_point.root.id
}

output "efs_access_point_id_pds-data" {
  value = aws_efs_access_point.pds-data.id
}
