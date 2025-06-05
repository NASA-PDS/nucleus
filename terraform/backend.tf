terraform {
  backend "s3" {
    bucket = "pds-nucleus-tf-state"
    key    = "nucleus_infra.tfstate"
    region = "us-west-2"
  }
}
