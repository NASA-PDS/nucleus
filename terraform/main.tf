# Terraform script to create the common resources for PDS Nucleus
module "common" {
  source = "./terraform-modules/common"

  vpc_id                              = var.vpc_id
  vpc_cidr                            = var.vpc_cidr
  nucleus_security_group_ingress_cidr = var.nucleus_security_group_ingress_cidr
#  subnet_ids                          = var.subnet_ids
  mwaa_dag_s3_bucket_name             = var.mwaa_dag_s3_bucket_name
}

# The Terraform module to create the PDS Nucleus Baseline System (without any project specific components)
module "mwaa-env" {
  source = "./terraform-modules/mwaa-env"

  vpc_id                              = var.vpc_id
  vpc_cidr                            = var.vpc_cidr
#  nucleus_security_group_ingress_cidr = var.nucleus_security_group_ingress_cidr
  subnet_ids                          = var.subnet_ids
#  mwaa_dag_s3_bucket_name             = var.mwaa_dag_s3_bucket_name
#  mwaa_execution_role_arn             = module.common.pds_nucleus_mwaa_execution_role_arn
  nucleus_security_group_id           = module.common.pds_nucleus_security_group_id
  airflow_dags_bucket_arn             = module.common.pds_nucleus_airflow_dags_bucket_arn

  depends_on = [module.common]
}

# The following modules are specific to PDS Registry and are under development. These modules are currently
# capable of successfully deploying some ECS tasks related with PDS Registry. However, these modules
# can be disabled (comment-out) to keep the PDS Nucleus Baseline System clean and to avoid confusions.

module "efs" {
 source = "./terraform-modules/efs"

  depends_on = [module.common]
}

module "ecs" {
  source = "./terraform-modules/ecs"

  efs_file_system_id                              = module.efs.efs_file_system_id
#  registry_loader_scripts_access_point_id         = module.efs.efs_file_system_id
#  registry_loader_default_configs_access_point_id = module.efs.efs_file_system_id
  pds_data_access_point_id                        = module.efs.efs_access_point_id_pds-data
#  ecs_task_role_arn                               = module.mwaa-env.pds_nucleus_mwaa_execution_role_arn
  ecs_task_role_arn                               = "arn:aws:iam::102440278396:role/pds_nucleus_mwaa_execution_role"
#  ecs_task_execution_role_arn                     = module.mwaa-env.pds_nucleus_mwaa_execution_role_arn
  ecs_task_execution_role_arn                     = "arn:aws:iam::102440278396:role/pds_nucleus_mwaa_execution_role"

  pds_registry_loader_harvest_ecr_image_path = var.pds_registry_loader_harvest_ecr_image_path
  pds_registry_loader_harvest_cloudwatch_logs_group = var.pds_registry_loader_harvest_cloudwatch_logs_group
  pds_registry_loader_harvest_cloudwatch_logs_region = var.pds_registry_loader_harvest_cloudwatch_logs_region
#  pds_registry_loader_harvest_data_access_point_id = module.efs.efs_access_point_id_pds-data

  pds_validate_ecr_image_path = var.pds_validate_ecr_image_path
  pds_validate_cloudwatch_logs_group = var.pds_validate_cloudwatch_logs_group
  pds_validate_cloudwatch_logs_region = var.pds_validate_cloudwatch_logs_region
#  pds_validate_data_access_point_id = module.efs.efs_access_point_id_pds-data

  pds_validate_ref_cloudwatch_logs_group = var.pds_validate_ref_cloudwatch_logs_group
  pds_validate_ref_cloudwatch_logs_region = var.pds_validate_ref_cloudwatch_logs_region

  depends_on = [module.common, module.efs, module.mwaa-env]
}

module "product-copy-completion-checker" {
 source = "./terraform-modules/product-copy-completion-checker"
}

