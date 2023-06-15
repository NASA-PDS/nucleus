terraform {
  backend "s3" {
    bucket = "pds-en-tf-state"
    key    = "infra/nucleus/nucleus.tfstate"
    region = "us-west-2"
  }
}
