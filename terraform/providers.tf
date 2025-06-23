terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
      configuration_aliases = [ aws.secondary ]
    }
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      product     = "PDS Nucleus"
    }
  }
}

provider "aws" {
  region = var.region_secondary
  alias = "secondary"

  default_tags {
    tags = {
      product     = "PDS Nucleus"
    }
  }
}
