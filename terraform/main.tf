# The Terraform module to create the PDS Nucleus Baseline System (without any project specific components)
module "mwaa-env" {
  source = "./terraform-modules/mwaa-env"

  vpc_id                              = var.vpc_id
  vpc_cidr                            = var.vpc_cidr
  nucleus_security_group_ingress_cidr = var.nucleus_security_group_ingress_cidr
  subnet_ids                          = var.subnet_ids
  airflow_execution_role              = var.airflow_execution_role
}

# The following modules are specific to PDS Registry and are under development. These modules are currently
# capable of successfully deploying some ECS tasks related with PDS Registry. However, these modules
# are currently disabled to keep the PDS Nucleus Baseline System clean and to avoid confusions.

# module "efs" {
#   source = "./terraform-modules/efs"
# }

# module "ecs" {
#   source = "./terraform-modules/ecs"

#   efs_file_system_id                              = var.efs_file_system_id
#   registry_loader_scripts_access_point_id         = var.registry_loader_scripts_access_point_id
#   registry_loader_default_configs_access_point_id = var.registry_loader_default_configs_access_point_id
#   task_role_arn                                   = var.task_role_arn
#   execution_role_arn                              = var.execution_role_arn
# }
