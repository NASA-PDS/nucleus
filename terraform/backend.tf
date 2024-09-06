terraform {
  backend "s3" {
    bucket = "pds-nucleus-tf-state"
    key    = "dev/nucleus_infra.tfstate"
    region = "us-west-2"
  }
}
