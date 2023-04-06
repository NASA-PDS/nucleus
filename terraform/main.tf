
module "efs" {
  source = "./terraform-modules/efs"
}

module "mwaa-env" {
  source = "./terraform-modules/mwaa-env"
}

module "ecs" {
  source = "./terraform-modules/ecs"
}
