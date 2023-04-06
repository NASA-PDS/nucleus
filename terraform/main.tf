# The Terraform module to create the PDS Nucleus Baseline System (without any project specific components)
module "mwaa-env" {
  source = "./terraform-modules/mwaa-env"
}


# The following modules are specific to PDS Registry and are under development. These modules are currently
# capable of successfully deploying some ECS tasks related with PDS Registry. However, these modules
# are currently disabled to keep the PDS Nucleus Baseline System clean and to avoid confusions.

#module "efs" {
#  source = "./terraform-modules/efs"
#}
#
#module "ecs" {
#  source = "./terraform-modules/ecs"
#}
