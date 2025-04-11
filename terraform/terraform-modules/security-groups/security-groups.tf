# Terraform script to create a security groups to be used in Nucleus


data "aws_caller_identity" "current" {}

data "aws_region" "current" {}


########################################################

# Security groups used by MWAA

########################################################

resource "aws_security_group" "nucleus_security_group" {
  name        = var.nucleus_security_group_name
  description = "PDS Nucleus security group"
  vpc_id      = var.vpc_id

  ingress {
    from_port = 2049
    to_port   = 2049
    protocol  = "tcp"
    self      = true
  }

  ingress {
    from_port = 5432
    to_port   = 5432
    protocol  = "tcp"
    self      = true
  }

  ingress {
    from_port = 443
    to_port   = 443
    protocol  = "tcp"
    self      = true
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
}


#########################################################
#
# Security groups used by cognito-auth terraform module
#
#########################################################

resource "aws_security_group" "nucleus_alb_security_group" {
  name        = var.nucleus_auth_alb_security_group_name
  description = "PDS Nucleus ALB security group"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = var.auth_alb_listener_port
    to_port     = var.auth_alb_listener_port
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port        = 0
    to_port          = 0
    protocol         = "-1"
    cidr_blocks      = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }
}


output "nucleus_security_group_id" {
  value = aws_security_group.nucleus_security_group.id
}

output "nucleus_alb_security_group_id" {
  value = aws_security_group.nucleus_alb_security_group.id
}